from __future__ import annotations

import argparse
import json
import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise endpoints in the UI's order")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--workspace-id")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        health = client.get("/health"); health.raise_for_status()
        rows = client.get("/workspaces"); rows.raise_for_status()
        workspace_id = args.workspace_id or (rows.json()[0]["id"] if rows.json() else None)
        if not workspace_id:
            created = client.post("/workspaces", json={"name": "Smoke test workspace"}); created.raise_for_status(); workspace_id = created.json()["id"]
        results = {"health": health.json(), "workspaceId": workspace_id}
        for name, path in (("documents", f"/workspaces/{workspace_id}/documents"), ("graph", f"/workspaces/{workspace_id}/graph"), ("conflicts", f"/workspaces/{workspace_id}/conflicts"), ("timeline", f"/workspaces/{workspace_id}/timeline"), ("audit", f"/workspaces/{workspace_id}/audit")):
            response = client.get(path); response.raise_for_status(); results[name] = response.json()
        answer = client.post(f"/workspaces/{workspace_id}/ask", json={"question": "What budget was discussed for this project?"}); answer.raise_for_status(); results["answer"] = answer.json()
        evidence_ids = [citation["passageId"] for citation in results["answer"]["citations"]]
        evidence_ids += [pid for rel in results["graph"]["relationships"] for pid in rel["evidencePassageIds"]]
        evidence_ids += [event["passageId"] for event in results["timeline"]]
        for passage_id in evidence_ids:
            client.get(f"/passages/{passage_id}").raise_for_status()
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

