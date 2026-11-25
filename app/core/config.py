from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'devflow.db'}"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Local Ollama settings (matched for 8GB RAM hardware)
OLLAMA_MODEL_NAME = "qwen3:4b"
OLLAMA_VISION_MODEL_NAME = "qwen2.5vl:3b"
PROMPT_VERSION = "spec_v3"
VISION_PROMPT_VERSION = "vision_v1"
ARTIFACTS_CORE_PROMPT_VERSION = "artifacts_core_v1"
ARTIFACTS_COMMS_PROMPT_VERSION = "artifacts_comms_v1"
PROMPTS_DIR = BASE_DIR / "app" / "prompts"

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB limit per SRS security rules
