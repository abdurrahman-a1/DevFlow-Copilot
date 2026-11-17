import json
from pathlib import Path
import requests

API_URL = "http://127.0.0.1:8000/api/v1/generate"
SAMPLES_PATH = Path("tests/sample_inputs.json")
OUTPUT_PATH = Path("docs/day1_test_results.json")


def main():
    samples = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    results = []

    for item in samples:
        print(f"Running {item['id']}: {item['project_name']}...")
        resp = requests.post(
            API_URL,
            json={
                "project_name": item["project_name"],
                "raw_text": item["raw_text"],
            },
            timeout=300,
        )
        results.append(
            {
                "id": item["id"],
                "project_name": item["project_name"],
                "status_code": resp.status_code,
                "response": resp.json(),
            }
        )
        print(f"  -> HTTP {resp.status_code}")

    OUTPUT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved {len(results)} results to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()