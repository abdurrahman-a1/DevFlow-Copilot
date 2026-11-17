from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import OLLAMA_MODEL_NAME, PROMPT_VERSION
from app.core.database import get_db
from app.models.db_models import Artifact, GenerationRun, InputDocument, Project
from app.schemas.spec_schema import GenerateRequest, GenerateResponse
from app.services.ollama_service import GenerationError, generate_specification
from app.services.prompt_loader import load_prompt

router = APIRouter(prefix="/api/v1", tags=["DevFlow Copilot"])

@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "model": OLLAMA_MODEL_NAME,
        "prompt_version": PROMPT_VERSION,
    }

@router.post("/generate", response_model=GenerateResponse)
def create_and_generate_spec(payload: GenerateRequest, db: Session = Depends(get_db)):
    # 1. Create Project and store raw InputDocument before transformation
    project = Project(name=payload.project_name.strip(), description=payload.project_description)
    db.add(project)
    db.flush()

    input_doc = InputDocument(
        project_id=project.project_id,
        input_type="text",
        source_text=payload.raw_text,
    )
    db.add(input_doc)
    db.flush()

    # 2. Load versioned prompt and call local Ollama model
    system_prompt = load_prompt(PROMPT_VERSION)
    try:
        spec = generate_specification(
            raw_text=payload.raw_text,
            system_prompt=system_prompt,
            model_name=OLLAMA_MODEL_NAME,
        )
    except GenerationError as exc:
        failed_run = GenerationRun(
            project_id=project.project_id,
            model_name=OLLAMA_MODEL_NAME,
            prompt_version=PROMPT_VERSION,
            status=f"failed:{exc.error_type}",
        )
        db.add(failed_run)
        db.commit()

        status_code = 422 if exc.error_type in ("input_error", "validation_error") else 503
        raise HTTPException(status_code=status_code, detail=str(exc))

    # 3. Record GenerationRun and save Artifact as draft
    run = GenerationRun(
        project_id=project.project_id,
        model_name=OLLAMA_MODEL_NAME,
        prompt_version=PROMPT_VERSION,
        status="completed",
    )
    db.add(run)
    db.flush()

    artifact = Artifact(
        run_id=run.run_id,
        type="specification",
        content_json=spec.model_dump_json(indent=2),
        review_status="draft",
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    return GenerateResponse(
        project_id=project.project_id,
        input_id=input_doc.input_id,
        run_id=run.run_id,
        artifact_id=artifact.artifact_id,
        model_name=OLLAMA_MODEL_NAME,
        prompt_version=PROMPT_VERSION,
        review_status=artifact.review_status,
        specification=spec,
    )