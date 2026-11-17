from app.core.config import PROMPTS_DIR

def load_prompt(version: str) -> str:
    prompt_path = PROMPTS_DIR / f"{version}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")