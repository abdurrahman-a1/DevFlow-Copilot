# Hardware Constraints & Day 1 Engineering Notes

## Assigned Machine Specifications
- **Laptop:** Dell Latitude 5401
- **CPU:** Intel Core i5-9400H
- **RAM:** 8GB DDR4
- **GPU:** Nvidia MX150 (2GB VRAM)

## Model Selection & Latency Trade-Offs
- **Selected Model:** `qwen3:4b` running locally via Ollama (`format=<Pydantic JSON Schema>`, `temperature=0.1`).
- **Optimization Applied:** Disabled Qwen3's default `<think>` chain (`think=False`) and capped context length (`num_ctx=2048`) to keep memory footprint within 8GB system RAM and prevent HTTP read timeouts.
- **Fallback Option:** `qwen3:1.7b` can be swapped in `app/core/config.py` if memory pressure increases during Day 2 multimodal tasks.

## Tested Failure & Edge Cases
1. **Short/Empty Input (`REQ` < 10 chars):** Rejected cleanly at service layer with HTTP `422` and logged as `failed:input_error` in `generation_runs`.
2. **Invalid JSON Schema Output:** Verified via `pytest` (`test_schema.py`) that missing required fields or invalid priority enums raise Pydantic `ValidationError`.
3. **Ollama Daemon Offline:** Simulated via `monkeypatch` in `test_schema.py`; returns HTTP `503` without crashing FastAPI.
4. **Vague Input (`REQ-09`) & Prompt Injection (`REQ-10`):** Tested in the 10-case batch; model surfaces missing details in `open_questions` and ignores injected budget fabrication instructions.