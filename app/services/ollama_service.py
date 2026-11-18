from pathlib import Path
from typing import Optional

import ollama
from pydantic import ValidationError

from app.core.config import OLLAMA_MODEL_NAME, OLLAMA_VISION_MODEL_NAME
from app.schemas.spec_schema import (
    CoreEngineeringPack,
    DeliveryCommsPack,
    EngineeringArtifactsBundle,
    ImageEvidence,
    ProjectSpecification,
)


class GenerationError(Exception):
    def __init__(self, message: str, error_type: str = "runtime_error"):
        super().__init__(message)
        self.error_type = error_type


def analyze_screenshot(
    image_path: Path,
    vision_prompt: str,
    vision_model: str = OLLAMA_VISION_MODEL_NAME,
) -> ImageEvidence:
    if not image_path.exists():
        raise GenerationError(f"Uploaded image file missing: {image_path}", error_type="input_error")

    try:
        response = ollama.chat(
            model=vision_model,
            messages=[
                {"role": "system", "content": vision_prompt},
                {
                    "role": "user",
                    "content": "Extract all observed UI components, states, interactions, and absent details from this screenshot.",
                    "images": [str(image_path)],
                },
            ],
            format=ImageEvidence.model_json_schema(),
            options={"temperature": 0.1, "num_ctx": 2048},
        )
    except Exception as exc:
        raise GenerationError(
            f"Local vision runtime error ({vision_model}). Ensure Ollama is running and vision model is pulled. Details: {exc}",
            error_type="runtime_error",
        ) from exc

    raw_content = response.message.content if response and response.message else ""
    if not raw_content:
        raise GenerationError("Vision model returned an empty response.", error_type="validation_error")

    try:
        return ImageEvidence.model_validate_json(raw_content)
    except ValidationError as exc:
        raise GenerationError(
            f"Vision output failed schema validation: {exc}",
            error_type="validation_error",
        ) from exc


def build_normalized_context(
    raw_text: Optional[str],
    image_evidence: Optional[ImageEvidence],
) -> tuple[str, str]:
    has_text = bool(raw_text and len(raw_text.strip()) >= 10)
    has_image = image_evidence is not None

    if not has_text and not has_image:
        raise GenerationError(
            "Provide either meaningful requirement text (min 10 chars), a valid screenshot, or both.",
            error_type="input_error",
        )

    if has_text and has_image:
        input_type = "combined"
    elif has_image:
        input_type = "image"
    else:
        input_type = "text"

    sections = [f"SOURCE_TYPE: {input_type.upper()}"]
    if has_text:
        sections.append(f"CLIENT_TEXT:\n{raw_text.strip()}")
    if has_image:
        sections.append(f"SCREENSHOT_OBSERVED_EVIDENCE (JSON):\n{image_evidence.model_dump_json(indent=2)}")

    return input_type, "\n\n".join(sections)


def generate_specification(
    normalized_context: str,
    system_prompt: str,
    model_name: str = OLLAMA_MODEL_NAME,
) -> ProjectSpecification:
    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": normalized_context},
            ],
            format=ProjectSpecification.model_json_schema(),
            think=False,
            options={"temperature": 0.1, "num_ctx": 2048},
        )
    except Exception as exc:
        raise GenerationError(
            f"Local Ollama runtime error ({model_name}). Ensure Ollama is running and model is pulled. Details: {exc}",
            error_type="runtime_error",
        ) from exc

    raw_content = response.message.content if response and response.message else ""
    if not raw_content:
        raise GenerationError("Model returned an empty response.", error_type="validation_error")

    try:
        return ProjectSpecification.model_validate_json(raw_content)
    except ValidationError as exc:
        raise GenerationError(
            f"Model output failed JSON schema validation: {exc}",
            error_type="validation_error",
        ) from exc


def _call_structured_llm(system_prompt: str, user_content: str, schema_cls, model_name: str):
    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            format=schema_cls.model_json_schema(),
            think=False,
            options={"temperature": 0.1, "num_ctx": 3072},
        )
    except Exception as exc:
        raise GenerationError(
            f"Local Ollama runtime error ({model_name}): {exc}",
            error_type="runtime_error",
        ) from exc

    raw_content = response.message.content if response and response.message else ""
    if not raw_content:
        raise GenerationError("Model returned an empty response.", error_type="validation_error")

    try:
        return schema_cls.model_validate_json(raw_content)
    except ValidationError as exc:
        raise GenerationError(
            f"Model output failed JSON schema validation: {exc}",
            error_type="validation_error",
        ) from exc


def generate_engineering_artifacts(
    spec: ProjectSpecification,
    core_prompt: str,
    comms_prompt: str,
    model_name: str = OLLAMA_MODEL_NAME,
) -> EngineeringArtifactsBundle:
    spec_json = spec.model_dump_json(indent=2)

    core_pack: CoreEngineeringPack = _call_structured_llm(
        system_prompt=core_prompt,
        user_content=f"Project Specification (JSON):\n{spec_json}",
        schema_cls=CoreEngineeringPack,
        model_name=model_name,
    )

    comms_input = (
        f"Project Specification (JSON):\n{spec_json}\n\n"
        f"Implementation Plan & Acceptance Criteria (JSON):\n{core_pack.model_dump_json(indent=2)}"
    )
    comms_pack: DeliveryCommsPack = _call_structured_llm(
        system_prompt=comms_prompt,
        user_content=comms_input,
        schema_cls=DeliveryCommsPack,
        model_name=model_name,
    )

    return EngineeringArtifactsBundle(
        acceptance_criteria=core_pack.acceptance_criteria,
        implementation_plan=core_pack.implementation_plan,
        qa_test_cases=core_pack.qa_test_cases,
        developer_prompt=comms_pack.developer_prompt,
        client_update=comms_pack.client_update,
        release_notes=comms_pack.release_notes,
    )