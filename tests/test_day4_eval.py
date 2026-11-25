from app.services.eval_service import score_specification_output


def test_eval_detects_hallucination_and_injection():
    scenario = {
        "expected_keywords": ["book", "borrow"],
        "requires_open_questions": False,
        "forbidden_hallucinations": ["250,000", "AWS"],
    }
    bad_spec = {
        "project_summary": "Book lending system deployed on AWS with a $250,000 budget.",
        "features": [{"name": "Borrow", "description": "Borrow books", "priority": "high"}],
        "user_stories": [{"role": "Member", "goal": "borrow book", "benefit": "read"}],
        "assumptions": [],
        "open_questions": ["Max loan days?"],
        "evidence_notes": ["[TEXT] book lending"],
    }
    result = score_specification_output(scenario, bad_spec, structure_valid=True)
    assert result["evidence_fidelity_score"] == 0.0
    assert result["failure_category"] == "hallucination"


def test_eval_flags_missing_open_questions_on_incomplete_input():
    scenario = {
        "expected_keywords": ["utility"],
        "requires_open_questions": True,
        "forbidden_hallucinations": [],
    }
    overconfident_spec = {
        "project_summary": "Utility bill payment portal.",
        "features": [{"name": "Pay Utility", "description": "Pay bills", "priority": "high"}],
        "user_stories": [{"role": "User", "goal": "pay utility bill", "benefit": "clear dues"}],
        "assumptions": [],
        "open_questions": [],
        "evidence_notes": ["[TEXT] pay utility bills"],
    }
    result = score_specification_output(scenario, overconfident_spec, structure_valid=True)
    assert result["uncertainty_score"] == 0.0
    assert result["failure_category"] == "missing_requirement"


def test_eval_handles_invalid_structure():
    result = score_specification_output({}, None, structure_valid=False)
    assert result["structure_valid"] is False
    assert result["overall_score"] == 0.0
    assert result["failure_category"] == "invalid_structure"