import json
from typing import Any, Optional


def render_run_markdown(
    project_name: str,
    run_id: int,
    model_name: str,
    prompt_version: str,
    spec: dict[str, Any],
    artifacts: Optional[dict[str, Any]] = None,
) -> str:
    lines = [
        f"# DevFlow Copilot Delivery Package — {project_name}",
        "",
        f"- **Run ID:** `{run_id}`",
        f"- **Model:** `{model_name}`",
        f"- **Prompt Version:** `{prompt_version}`",
        "- **Status:** `AI-generated draft - requires human review`",
        "",
        "## 1. Project Summary",
        spec.get("project_summary", ""),
        "",
        "## 2. Features",
    ]
    for feat in spec.get("features", []):
        lines.append(f"- **{feat['name']}** (`{feat['priority']}`): {feat['description']}")

    lines.extend(["", "## 3. User Stories"])
    for idx, us in enumerate(spec.get("user_stories", []), 1):
        lines.append(f"- **US-{idx:03d}:** As a **{us['role']}**, I want to **{us['goal']}**, so that **{us['benefit']}**.")

    lines.extend(["", "## 4. Observed Evidence, Assumptions & Open Questions"])
    lines.append("### Observed Evidence")
    for ev in spec.get("evidence_notes", []):
        lines.append(f"- {ev}")
    lines.append("### Assumptions")
    for item in spec.get("assumptions", []):
        lines.append(f"- {item}")
    lines.append("### Open Questions")
    for q in spec.get("open_questions", []):
        lines.append(f"- {q}")

    if artifacts:
        lines.extend(["", "## 5. Acceptance Criteria (Given / When / Then)"])
        for ac in artifacts.get("acceptance_criteria", []):
            lines.append(
                f"- **{ac['story_id']}:** **Given** {ac['given']}, **When** {ac['when']}, **Then** {ac['then']}."
            )

        plan = artifacts.get("implementation_plan", {})
        lines.extend(["", "## 6. Implementation Plan"])
        for section in ["frontend", "backend", "data", "apis", "dependencies", "risks"]:
            lines.append(f"### {section.capitalize()}")
            for entry in plan.get(section, []):
                lines.append(f"- {entry}")

        lines.extend(["", "## 7. QA Test Cases"])
        for tc in artifacts.get("qa_test_cases", []):
            steps_str = " -> ".join(tc.get("steps", []))
            lines.append(
                f"- **{tc['test_id']}** (`{tc['category']}`) — **{tc['title']}**: {steps_str} | **Expected:** {tc['expected_result']}"
            )

        lines.extend(
            [
                "",
                "## 8. Context-Rich Developer Prompt",
                "```text",
                artifacts.get("developer_prompt", ""),
                "```",
                "",
                "## 9. Client Progress Update",
                artifacts.get("client_update", ""),
                "",
                "## 10. Draft Release Notes",
                artifacts.get("release_notes", ""),
            ]
        )

    return "\n".join(lines)


def render_run_json(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, indent=2)