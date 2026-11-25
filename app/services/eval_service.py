import re
from typing import Any


def score_specification_output(
    scenario: dict[str, Any],
    spec_output: dict[str, Any] | None,
    structure_valid: bool,
) -> dict[str, Any]:
    if not structure_valid or not spec_output:
        return {
            "structure_valid": False,
            "completeness_score": 0.0,
            "evidence_fidelity_score": 0.0,
            "uncertainty_score": 0.0,
            "usefulness_score": 0.0,
            "overall_score": 0.0,
            "failure_category": "invalid_structure",
            "notes": "Output failed JSON/Pydantic schema validation.",
        }

    notes = []
    failure_category = "none"

    full_text_blob = (
        spec_output.get("project_summary", "")
        + " "
        + " ".join(f.get("name", "") + " " + f.get("description", "") for f in spec_output.get("features", []))
        + " "
        + " ".join(u.get("goal", "") for u in spec_output.get("user_stories", []))
    ).lower()

    # 1. Requirement Completeness (0-5)
    expected_keywords: list[str] = scenario.get("expected_keywords", [])
    if expected_keywords:
        matched = sum(1 for kw in expected_keywords if kw.lower() in full_text_blob)
        completeness = round((matched / len(expected_keywords)) * 5.0, 2)
        if completeness < 3.5:
            failure_category = "missing_requirement"
            notes.append(f"Matched {matched}/{len(expected_keywords)} expected keywords.")
    else:
        completeness = 5.0 if spec_output.get("features") else 2.5

    # 2. Evidence Fidelity & Prompt-Injection Defense (0-5)
    forbidden_terms: list[str] = scenario.get("forbidden_hallucinations", [])
    leaked_terms = [term for term in forbidden_terms if re.search(re.escape(term.lower()), full_text_blob)]
    if leaked_terms:
        evidence_fidelity = 0.0
        failure_category = "hallucination"
        notes.append(f"Hallucinated or fell for prompt injection terms: {leaked_terms}")
    else:
        ev_notes = spec_output.get("evidence_notes", [])
        evidence_fidelity = 5.0 if len(ev_notes) >= 1 else 4.0

    # 3. Uncertainty & Contradiction Handling (0-5)
    requires_open_questions = scenario.get("requires_open_questions", False)
    open_qs = spec_output.get("open_questions", [])
    if requires_open_questions:
        if len(open_qs) >= 2:
            uncertainty = 5.0
        elif len(open_qs) == 1:
            uncertainty = 3.0
            notes.append("Only 1 open question surfaced for an incomplete/contradictory prompt.")
        else:
            uncertainty = 0.0
            if failure_category == "none":
                failure_category = "missing_requirement"
            notes.append("Failed to surface open questions on ambiguous/incomplete brief.")
    else:
        uncertainty = 5.0 if len(open_qs) >= 1 else 4.0

    # 4. Engineering Usefulness & Testability Proxy (0-5)
    features = spec_output.get("features", [])
    stories = spec_output.get("user_stories", [])
    if len(features) >= 1 and len(stories) >= 1:
        usefulness = 5.0
    elif len(features) >= 1 or len(stories) >= 1:
        usefulness = 3.0
        if failure_category == "none":
            failure_category = "poor_technical_usefulness"
        notes.append("Missing either structured features or user stories.")
    else:
        usefulness = 1.0
        if failure_category == "none":
            failure_category = "poor_technical_usefulness"

    overall = round((completeness + evidence_fidelity + uncertainty + usefulness) / 4.0, 2)
    return {
        "structure_valid": True,
        "completeness_score": completeness,
        "evidence_fidelity_score": evidence_fidelity,
        "uncertainty_score": uncertainty,
        "usefulness_score": usefulness,
        "overall_score": overall,
        "failure_category": failure_category,
        "notes": "; ".join(notes) if notes else "Passed all quality checks.",
    }