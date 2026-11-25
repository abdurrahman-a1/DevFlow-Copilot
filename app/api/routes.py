import json
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import (
    ALLOWED_IMAGE_EXTENSIONS,
    ARTIFACTS_COMMS_PROMPT_VERSION,
    ARTIFACTS_CORE_PROMPT_VERSION,
    MAX_IMAGE_SIZE_BYTES,
    OLLAMA_MODEL_NAME,
    OLLAMA_VISION_MODEL_NAME,
    PROMPT_VERSION,
    UPLOADS_DIR,
    VISION_PROMPT_VERSION,
)
from app.core.database import get_db
from app.models.db_models import (
    Artifact,
    EvaluationTest,
    GenerationRun,
    InputDocument,
    Project,
    ReviewFeedback,
)
from app.schemas.spec_schema import (
    GenerateArtifactsResponse,
    GenerateRequest,
    GenerateResponse,
    ProjectSpecification,
)
from app.services.export_service import render_run_json, render_run_markdown
from app.services.ollama_service import (
    GenerationError,
    analyze_screenshot,
    build_normalized_context,
    generate_engineering_artifacts,
    generate_specification,
)
from app.services.prompt_loader import load_prompt

router = APIRouter(prefix="/api/v1", tags=["DevFlow Copilot"])


class ReviewActionRequest(BaseModel):
    action: str  # "approved" | "edited" | "rejected"
    reviewer_note: Optional[str] = None
    edited_json: Optional[str] = None


class RegenerateRequest(BaseModel):
    reviewer_feedback: str


def _sanitize_and_save_upload(upload: UploadFile) -> Path:
    original_name = upload.filename or "upload.png"
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_IMAGE_EXTENSIONS)}",
        )

    content = upload.file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded image file is empty.")
    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"Image exceeds max size of {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(original_name).stem)[:50]
    unique_name = f"{safe_stem}_{uuid.uuid4().hex[:8]}{ext}"
    dest_path = UPLOADS_DIR / unique_name
    dest_path.write_bytes(content)
    return dest_path


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "model": OLLAMA_MODEL_NAME,
        "vision_model": OLLAMA_VISION_MODEL_NAME,
        "prompt_version": PROMPT_VERSION,
        "vision_prompt_version": VISION_PROMPT_VERSION,
        "artifacts_prompt_versions": [
            ARTIFACTS_CORE_PROMPT_VERSION,
            ARTIFACTS_COMMS_PROMPT_VERSION,
        ],
    }


@router.post("/generate", response_model=GenerateResponse)
def create_and_generate_spec(payload: GenerateRequest, db: Session = Depends(get_db)):
    return _run_generation_pipeline(
        db=db,
        project_name=payload.project_name,
        project_description=payload.project_description,
        raw_text=payload.raw_text,
        saved_image_path=None,
    )


@router.post("/generate-multimodal", response_model=GenerateResponse)
def create_and_generate_multimodal_spec(
    project_name: str = Form(..., min_length=1, max_length=200),
    project_description: Optional[str] = Form(None),
    raw_text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    saved_image_path: Optional[Path] = None
    if image is not None and image.filename:
        saved_image_path = _sanitize_and_save_upload(image)

    return _run_generation_pipeline(
        db=db,
        project_name=project_name,
        project_description=project_description,
        raw_text=raw_text,
        saved_image_path=saved_image_path,
    )


def _run_generation_pipeline(
    db: Session,
    project_name: str,
    project_description: Optional[str],
    raw_text: Optional[str],
    saved_image_path: Optional[Path],
) -> GenerateResponse:
    has_text = bool(raw_text and raw_text.strip())
    has_image = saved_image_path is not None

    if has_text and has_image:
        input_type = "combined"
    elif has_image:
        input_type = "image"
    else:
        input_type = "text"

    # 1. Store Project and raw InputDocument before transformation
    project = Project(name=project_name.strip(), description=project_description)
    db.add(project)
    db.flush()

    input_doc = InputDocument(
        project_id=project.project_id,
        input_type=input_type,
        source_text=raw_text.strip() if has_text else "[IMAGE-ONLY INPUT]",
        file_path=str(saved_image_path) if saved_image_path else None,
    )
    db.add(input_doc)
    db.flush()

    used_models = (
        f"{OLLAMA_VISION_MODEL_NAME} + {OLLAMA_MODEL_NAME}"
        if has_image
        else OLLAMA_MODEL_NAME
    )

    try:
        # 2. Optional Stage 1: Vision evidence extraction
        image_evidence = None
        if saved_image_path is not None:
            vision_prompt = load_prompt(VISION_PROMPT_VERSION)
            image_evidence = analyze_screenshot(
                image_path=saved_image_path,
                vision_prompt=vision_prompt,
                vision_model=OLLAMA_VISION_MODEL_NAME,
            )

        # 3. Build normalized context and run Stage 2 specification generation
        _, normalized_context = build_normalized_context(raw_text, image_evidence)
        system_prompt = load_prompt(PROMPT_VERSION)
        spec = generate_specification(
            normalized_context=normalized_context,
            system_prompt=system_prompt,
            model_name=OLLAMA_MODEL_NAME,
        )
    except GenerationError as exc:
        failed_run = GenerationRun(
            project_id=project.project_id,
            model_name=used_models,
            prompt_version=PROMPT_VERSION,
            status=f"failed:{exc.error_type}",
        )
        db.add(failed_run)
        db.commit()

        status_code = 422 if exc.error_type in ("input_error", "validation_error") else 503
        raise HTTPException(status_code=status_code, detail=str(exc))

    # 4. Save GenerationRun and draft Artifact
    run = GenerationRun(
        project_id=project.project_id,
        model_name=used_models,
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
        input_type=input_type,
        model_name=used_models,
        prompt_version=PROMPT_VERSION,
        review_status=artifact.review_status,
        image_evidence=image_evidence,
        specification=spec,
    )


@router.post("/runs/{run_id}/artifacts", response_model=GenerateArtifactsResponse)
def create_engineering_artifacts_for_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"GenerationRun {run_id} not found.")

    spec_artifact = (
        db.query(Artifact)
        .filter(Artifact.run_id == run_id, Artifact.type == "specification")
        .first()
    )
    if not spec_artifact:
        raise HTTPException(status_code=404, detail=f"No specification artifact found for run {run_id}.")

    spec = ProjectSpecification.model_validate_json(spec_artifact.content_json)
    core_prompt = load_prompt(ARTIFACTS_CORE_PROMPT_VERSION)
    comms_prompt = load_prompt(ARTIFACTS_COMMS_PROMPT_VERSION)

    try:
        bundle = generate_engineering_artifacts(
            spec=spec,
            core_prompt=core_prompt,
            comms_prompt=comms_prompt,
            model_name=OLLAMA_MODEL_NAME,
        )
    except GenerationError as exc:
        status_code = 422 if exc.error_type in ("input_error", "validation_error") else 503
        raise HTTPException(status_code=status_code, detail=str(exc))

    # Remove prior draft engineering artifacts for this run if regenerated
    db.query(Artifact).filter(
        Artifact.run_id == run_id,
        Artifact.type != "specification",
    ).delete()

    artifact_map = {
        "acceptance_criteria": [item.model_dump() for item in bundle.acceptance_criteria],
        "implementation_plan": bundle.implementation_plan.model_dump(),
        "qa_test_cases": [item.model_dump() for item in bundle.qa_test_cases],
        "developer_prompt": {"prompt": bundle.developer_prompt},
        "client_update": {"summary": bundle.client_update},
        "release_notes": {"notes": bundle.release_notes},
    }

    for art_type, payload_obj in artifact_map.items():
        db.add(
            Artifact(
                run_id=run_id,
                type=art_type,
                content_json=json.dumps(payload_obj, indent=2),
                review_status="draft",
            )
        )
    db.commit()

    return GenerateArtifactsResponse(
        run_id=run_id,
        project_id=run.project_id,
        model_name=OLLAMA_MODEL_NAME,
        prompt_versions=[ARTIFACTS_CORE_PROMPT_VERSION, ARTIFACTS_COMMS_PROMPT_VERSION],
        review_status="draft",
        artifacts=bundle,
    )


@router.get("/runs/{run_id}/export")
def export_run_package(run_id: int, format: str = "markdown", db: Session = Depends(get_db)):
    run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"GenerationRun {run_id} not found.")

    project = db.query(Project).filter(Project.project_id == run.project_id).first()
    artifacts = db.query(Artifact).filter(Artifact.run_id == run_id).all()
    if not artifacts:
        raise HTTPException(status_code=404, detail=f"No artifacts stored for run {run_id}.")

    spec_data = {}
    eng_data = {}
    for art in artifacts:
        parsed = json.loads(art.content_json)
        if art.type == "specification":
            spec_data = parsed
        elif art.type == "developer_prompt":
            eng_data["developer_prompt"] = parsed.get("prompt", "")
        elif art.type == "client_update":
            eng_data["client_update"] = parsed.get("summary", "")
        elif art.type == "release_notes":
            eng_data["release_notes"] = parsed.get("notes", "")
        else:
            eng_data[art.type] = parsed

    if format.lower() == "json":
        payload = {
            "project_name": project.name if project else f"Project-{run.project_id}",
            "run_id": run.run_id,
            "model_name": run.model_name,
            "prompt_version": run.prompt_version,
            "specification": spec_data,
            "engineering_artifacts": eng_data,
        }
        return Response(
            content=render_run_json(payload),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=devflow_run_{run_id}.json"},
        )

    md_text = render_run_markdown(
        project_name=project.name if project else f"Project-{run.project_id}",
        run_id=run.run_id,
        model_name=run.model_name,
        prompt_version=run.prompt_version,
        spec=spec_data,
        artifacts=eng_data if eng_data else None,
    )
    return Response(
        content=md_text,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=devflow_run_{run_id}.md"},
    )


@router.get("/projects")
def list_projects_and_runs(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    history = []
    for proj in projects:
        runs = db.query(GenerationRun).filter(GenerationRun.project_id == proj.project_id).all()
        for r in runs:
            spec_art = (
                db.query(Artifact)
                .filter(Artifact.run_id == r.run_id, Artifact.type == "specification")
                .first()
            )
            history.append(
                {
                    "project_id": proj.project_id,
                    "project_name": proj.name,
                    "run_id": r.run_id,
                    "model_name": r.model_name,
                    "prompt_version": r.prompt_version,
                    "run_status": r.status,
                    "review_status": spec_art.review_status if spec_art else "none",
                    "artifact_id": spec_art.artifact_id if spec_art else None,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
            )
    return {"runs": history}


@router.get("/runs/{run_id}")
def get_run_details(run_id: int, db: Session = Depends(get_db)):
    run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    project = db.query(Project).filter(Project.project_id == run.project_id).first()
    input_doc = db.query(InputDocument).filter(InputDocument.project_id == run.project_id).first()
    artifacts = db.query(Artifact).filter(Artifact.run_id == run_id).all()

    spec_data = {}
    spec_artifact_id = None
    review_status = "draft"
    eng_data = {}

    for art in artifacts:
        parsed = json.loads(art.content_json)
        if art.type == "specification":
            spec_data = parsed
            spec_artifact_id = art.artifact_id
            review_status = art.review_status
        elif art.type == "developer_prompt":
            eng_data["developer_prompt"] = parsed.get("prompt", "")
        elif art.type == "client_update":
            eng_data["client_update"] = parsed.get("summary", "")
        elif art.type == "release_notes":
            eng_data["release_notes"] = parsed.get("notes", "")
        else:
            eng_data[art.type] = parsed

    feedbacks = []
    if spec_artifact_id:
        fb_rows = (
            db.query(ReviewFeedback)
            .filter(ReviewFeedback.artifact_id == spec_artifact_id)
            .order_by(ReviewFeedback.created_at.desc())
            .all()
        )
        feedbacks = [
            {"label": f.label, "reviewer_note": f.reviewer_note, "created_at": f.created_at.isoformat()}
            for f in fb_rows
        ]

    return {
        "project_id": run.project_id,
        "project_name": project.name if project else "",
        "input_type": input_doc.input_type if input_doc else "text",
        "source_text": input_doc.source_text if input_doc else "",
        "run_id": run.run_id,
        "artifact_id": spec_artifact_id,
        "model_name": run.model_name,
        "prompt_version": run.prompt_version,
        "review_status": review_status,
        "specification": spec_data,
        "engineering_artifacts": eng_data if eng_data else None,
        "review_history": feedbacks,
    }


@router.post("/artifacts/{artifact_id}/review")
def review_artifact(artifact_id: int, payload: ReviewActionRequest, db: Session = Depends(get_db)):
    action = payload.action.strip().lower()
    if action not in ("approved", "edited", "rejected"):
        raise HTTPException(status_code=422, detail="Action must be 'approved', 'edited', or 'rejected'.")

    artifact = db.query(Artifact).filter(Artifact.artifact_id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found.")

    if action == "edited":
        if not payload.edited_json:
            raise HTTPException(status_code=422, detail="edited_json is required when action is 'edited'.")
        try:
            validated = ProjectSpecification.model_validate_json(payload.edited_json)
            artifact.content_json = validated.model_dump_json(indent=2)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Edited JSON failed schema validation: {exc}")

    # Update status across all artifacts belonging to the same run
    db.query(Artifact).filter(Artifact.run_id == artifact.run_id).update({"review_status": action})

    fb = ReviewFeedback(
        artifact_id=artifact_id,
        reviewer_note=payload.reviewer_note,
        label=action,
    )
    db.add(fb)
    db.commit()

    return {
        "artifact_id": artifact_id,
        "run_id": artifact.run_id,
        "review_status": action,
        "reviewer_note": payload.reviewer_note,
    }


@router.post("/runs/{run_id}/regenerate", response_model=GenerateResponse)
def regenerate_with_feedback(run_id: int, payload: RegenerateRequest, db: Session = Depends(get_db)):
    run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    project = db.query(Project).filter(Project.project_id == run.project_id).first()
    input_doc = db.query(InputDocument).filter(InputDocument.project_id == run.project_id).first()
    if not input_doc:
        raise HTTPException(status_code=404, detail="Original input document not found for regeneration.")

    combined_text = (
        f"{input_doc.source_text}\n\n"
        f"[HUMAN REVIEWER FEEDBACK FOR REVISION]:\n{payload.reviewer_feedback.strip()}"
    )
    saved_path = Path(input_doc.file_path) if input_doc.file_path else None

    return _run_generation_pipeline(
        db=db,
        project_name=project.name if project else f"Project-{run.project_id}",
        project_description=project.description if project else None,
        raw_text=combined_text,
        saved_image_path=saved_path if (saved_path and saved_path.exists()) else None,
    )


@router.get("/evaluation/summary")
def get_evaluation_summary(db: Session = Depends(get_db)):
    rows = db.query(EvaluationTest).all()
    if not rows:
        return {"total_records": 0, "by_prompt": {}}

    by_prompt: dict[str, list[EvaluationTest]] = {}
    for r in rows:
        by_prompt.setdefault(r.prompt_version, []).append(r)

    summary = {}
    for pv, items in by_prompt.items():
        n = len(items)
        summary[pv] = {
            "count": n,
            "pass_rate_pct": round(sum(i.structure_valid for i in items) / n * 100, 1),
            "avg_completeness": round(sum(i.completeness_score for i in items) / n, 2),
            "avg_evidence_fidelity": round(sum(i.evidence_fidelity_score for i in items) / n, 2),
            "avg_uncertainty": round(sum(i.uncertainty_score for i in items) / n, 2),
            "avg_usefulness": round(sum(i.usefulness_score for i in items) / n, 2),
            "avg_overall": round(sum(i.overall_score for i in items) / n, 2),
        }
    return {"total_records": len(rows), "by_prompt": summary}