import ollama
from pydantic import ValidationError
from app.core.config import OLLAMA_MODEL_NAME
from app.schemas.spec_schema import ProjectSpecification

class GenerationError(Exception):
    def __init__(self, message: str, error_type: str = "runtime_error"):
        super().__init__(message)
        self.error_type = error_type

def generate_specification(raw_text: str, system_prompt: str, model_name: str = OLLAMA_MODEL_NAME) -> ProjectSpecification:
    cleaned = raw_text.strip()
    if len(cleaned) < 10:
        raise GenerationError(
            "Input text is too short (minimum 10 meaningful characters required).",
            error_type="input_error",
        )

    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Client Input:\n{cleaned}"},
            ],
            format=ProjectSpecification.model_json_schema(),
            think=False,
            options={"temperature": 0.1,
                     "num_ctx": 2048
                     },
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