from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Load the generated DocTrace development corpus")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--name", default="DocTrace generated demo")
    parser.add_argument("--timeout", type=float, default=240.0)
    args = parser.parse_args()
    data_dir = Path(__file__).resolve().parents[1] / "tests" / "data"
    truth_path = data_dir / "ground_truth.json"
    if not truth_path.exists():
        print("Generate the corpus first: python tests/make_test_data.py", file=sys.stderr)
        return 2
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    files = [data_dir / item["path"] for item in truth["files"] if item["set"] == "dev"]
    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        response = client.post("/workspaces", json={"name": args.name})
        if response.status_code == 409:
            workspaces = client.get("/workspaces").raise_for_status().json()
            workspace = next(row for row in workspaces if row["name"] == args.name)
        else:
            response.raise_for_status(); workspace = response.json()
        workspace_id = workspace["id"]
        existing = {row["filename"] for row in client.get(f"/workspaces/{workspace_id}/documents").json()}
        deadline = time.monotonic() + args.timeout
        for path in files:
            if path.name in existing:
                continue
            while True:
                with path.open("rb") as handle:
                    uploaded = client.post(
                        f"/workspaces/{workspace_id}/documents",
                        files={"file": (path.name, handle, "application/octet-stream")},
                    )
                if uploaded.status_code != 503:
                    uploaded.raise_for_status()
                    print(f"queued {path.name}")
                    break
                if time.monotonic() >= deadline:
                    print(f"Timed out waiting for queue capacity before {path.name}", file=sys.stderr)
                    return 1
                time.sleep(0.25)
        while time.monotonic() < deadline:
            docs = client.get(f"/workspaces/{workspace_id}/documents").raise_for_status().json()
            if docs and all(d["status"] in {"ready", "failed"} for d in docs):
                print(json.dumps({"workspaceId": workspace_id, "documents": docs}, indent=2))
                return 1 if any(d["status"] == "failed" for d in docs) else 0
            time.sleep(0.5)
    print("Timed out waiting for document processing", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

