from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'devflow.db'}"

# Local Ollama settings (matched for 8GB RAM hardware)
OLLAMA_MODEL_NAME = "qwen3:4b"  # Change to "qwen3:1.7b" if RAM feels tight
PROMPT_VERSION = "spec_v1"
PROMPTS_DIR = BASE_DIR / "app" / "prompts"