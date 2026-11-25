import json
from pathlib import Path
from app.core.config import OLLAMA_MODEL_NAME
from app.core.database import Base, SessionLocal, engine
from app.models.db_models import EvaluationTest
from app.services.eval_service import score_specification_output
from app.services.ollama_service import GenerationError, generate_specification
from app.services.prompt_loader import load_prompt

Base.metadata.create_all(bind=engine)

DATASET_PATH = Path("eval/eval_dataset_30.json")
RESULTS_JSON_PATH = Path("docs/day4_eval_results.json")
REPORT_MD_PATH = Path("docs/evaluation_report.md")


def run_prompt_benchmark(dataset: list[dict], prompt_version: str, db) -> list[dict]:
    system_prompt = load_prompt(prompt_version)
    records = []

    for item in dataset:
        print(f"[{prompt_version}] Running {item['id']} ({item['category']}): {item['project_name']}...")
        context = f"SOURCE_TYPE: TEXT\n\nCLIENT_TEXT:\n{item['raw_text']}"
        try:
            spec = generate_specification(
                normalized_context=context,
                system_prompt=system_prompt,
                model_name=OLLAMA_MODEL_NAME,
            )
            spec_dict = spec.model_dump()
            struct_ok = True
        except GenerationError as exc:
            spec_dict = None
            struct_ok = False
            print(f"  -> Generation/Validation failed: {exc}")

        scores = score_specification_output(item, spec_dict, struct_ok)

        db_row = EvaluationTest(
            scenario_id=item["id"],
            category=item["category"],
            prompt_version=prompt_version,
            model_name=OLLAMA_MODEL_NAME,
            scenario=item["raw_text"],
            expected_fields=json.dumps(item.get("expected_keywords", [])),
            structure_valid=1 if scores["structure_valid"] else 0,
            completeness_score=scores["completeness_score"],
            evidence_fidelity_score=scores["evidence_fidelity_score"],
            uncertainty_score=scores["uncertainty_score"],
            usefulness_score=scores["usefulness_score"],
            overall_score=scores["overall_score"],
            failure_category=scores["failure_category"],
            notes=scores["notes"],
        )
        db.add(db_row)
        db.commit()

        records.append(
            {
                "scenario_id": item["id"],
                "category": item["category"],
                "project_name": item["project_name"],
                "prompt_version": prompt_version,
                **scores,
            }
        )
        print(f"  -> Overall: {scores['overall_score']}/5.0 | Failure: {scores['failure_category']}")

    return records


def summarize_prompt(records: list[dict]) -> dict:
    total = len(records)
    avg = lambda key: round(sum(r[key] for r in records) / total, 2) if total else 0.0
    pass_rate = round((sum(1 for r in records if r["structure_valid"]) / total) * 100, 1) if total else 0.0
    failures = {}
    for r in records:
        fc = r["failure_category"]
        if fc != "none":
            failures[fc] = failures.get(fc, 0) + 1
    return {
        "total_cases": total,
        "structure_pass_rate_pct": pass_rate,
        "avg_completeness": avg("completeness_score"),
        "avg_evidence_fidelity": avg("evidence_fidelity_score"),
        "avg_uncertainty": avg("uncertainty_score"),
        "avg_usefulness": avg("usefulness_score"),
        "avg_overall": avg("overall_score"),
        "failure_breakdown": failures,
    }


def write_markdown_report(v1_summary: dict, v3_summary: dict, v3_records: list[dict]) -> None:
    lines = [
        "# DevFlow Copilot — Day 4 Evaluation & Reliability Report",
        "",
        f"- **Model Evaluated:** `{OLLAMA_MODEL_NAME}` (Local via Ollama)",
        "- **Evaluation Dataset Size:** 30 scenarios (`eval/eval_dataset_30.json`)",
        "- **Prompt Versions Compared:** `spec_v1` (Day 1 baseline) vs. `spec_v3` (hardened grounding, contradiction & injection defense)",
        "",
        "## 1. Prompt Comparison Summary (`spec_v1` vs. `spec_v3`)",
        "",
        "| Metric | `spec_v1` | `spec_v3` | Delta |",
        "| :--- | :---: | :---: | :---: |",
        f"| Structure Validity Pass Rate | {v1_summary['structure_pass_rate_pct']}% | {v3_summary['structure_pass_rate_pct']}% | {round(v3_summary['structure_pass_rate_pct'] - v1_summary['structure_pass_rate_pct'], 1)}% |",
        f"| Requirement Completeness (0-5) | {v1_summary['avg_completeness']} | {v3_summary['avg_completeness']} | {round(v3_summary['avg_completeness'] - v1_summary['avg_completeness'], 2)} |",
        f"| Evidence Fidelity (0-5) | {v1_summary['avg_evidence_fidelity']} | {v3_summary['avg_evidence_fidelity']} | {round(v3_summary['avg_evidence_fidelity'] - v1_summary['avg_evidence_fidelity'], 2)} |",
        f"| Uncertainty Handling (0-5) | {v1_summary['avg_uncertainty']} | {v3_summary['avg_uncertainty']} | {round(v3_summary['avg_uncertainty'] - v1_summary['avg_uncertainty'], 2)} |",
        f"| Engineering Usefulness (0-5) | {v1_summary['avg_usefulness']} | {v3_summary['avg_usefulness']} | {round(v3_summary['avg_usefulness'] - v1_summary['avg_usefulness'], 2)} |",
        f"| **Overall Average Score (0-5)** | **{v1_summary['avg_overall']}** | **{v3_summary['avg_overall']}** | **{round(v3_summary['avg_overall'] - v1_summary['avg_overall'], 2)}** |",
        "",
        "## 2. Failure Categorization",
        f"- **`spec_v1` Failures:** `{v1_summary['failure_breakdown']}`",
        f"- **`spec_v3` Failures:** `{v3_summary['failure_breakdown']}`",
        "",
        "## 3. Scenario-by-Scenario Results (`spec_v3`)",
        "",
        "| ID | Category | Project | Struct | Complete | Fidelity | Uncert | Useful | Overall | Failure |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]
    for r in v3_records:
        st_lbl = "PASS" if r["structure_valid"] else "FAIL"
        lines.append(
            f"| {r['scenario_id']} | {r['category']} | {r['project_name']} | {st_lbl} | "
            f"{r['completeness_score']} | {r['evidence_fidelity_score']} | {r['uncertainty_score']} | "
            f"{r['usefulness_score']} | **{r['overall_score']}** | `{r['failure_category']}` |"
        )

    lines.extend(
        [
            "",
            "## 4. Known Limitations & Mitigations",
            "- **Compact Model Nuance (`qwen3:4b`):** On subtle logical contradictions (e.g., `EVAL-26`, `EVAL-27`), a 4B local model occasionally treats both conflicting statements as separate features instead of explicitly flagging the contradiction unless prompted strongly.",
            "- **Context Window Cap (`num_ctx=2048`):** Kept at 2048 tokens to stay within 8GB system RAM; multi-page RFPs require chunking or retrieval in future iterations.",
            "- **Mandatory Human Gate:** Automated checks catch schema errors and keyword omissions, but a human reviewer must still approve every draft before export.",
        ]
    )
    REPORT_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main():
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        db.query(EvaluationTest).delete()
        db.commit()

        v1_records = run_prompt_benchmark(dataset, "spec_v1", db)
        v3_records = run_prompt_benchmark(dataset, "spec_v3", db)

        v1_summary = summarize_prompt(v1_records)
        v3_summary = summarize_prompt(v3_records)

        RESULTS_JSON_PATH.write_text(
            json.dumps(
                {
                    "summary": {"spec_v1": v1_summary, "spec_v3": v3_summary},
                    "records": {"spec_v1": v1_records, "spec_v3": v3_records},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        write_markdown_report(v1_summary, v3_summary, v3_records)
        print(f"\nEvaluation complete! Report saved to {REPORT_MD_PATH}")
    finally:
        db.close()


if __name__ == "__main__":
    main()