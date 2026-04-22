#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


HARNESS_DIR = Path(__file__).resolve().parent
CASES_DIR = HARNESS_DIR / "cases"
REPORT_DIR = HARNESS_DIR / "report"


def post_json(url: str, payload: Dict) -> Dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str) -> Dict:
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def run_case(base_url: str, case_path: Path) -> Dict:
    case = json.loads(case_path.read_text())
    case_name = case.get("name", case_path.stem)
    request_payload = case["request"]
    checks = case.get("checks", {})

    result = {
        "case_name": case_name,
        "case_file": str(case_path),
        "passed": False,
        "messages": [],
        "run_id": None,
        "status": None,
    }

    try:
        create_resp = post_json(f"{base_url}/runs", request_payload)
        run_id = create_resp["run_id"]
        result["run_id"] = run_id

        artifacts = get_json(f"{base_url}/runs/{run_id}/artifacts")
        status = artifacts.get("status")
        result["status"] = status
        comments = artifacts.get("comments", [])

        if status != "completed":
            result["messages"].append("Run did not complete.")
            return result

        min_comments = int(checks.get("min_comments", 1))
        if len(comments) < min_comments:
            result["messages"].append(
                "Expected at least %d comments, got %d." % (min_comments, len(comments))
            )

        must_include_any = [s.lower() for s in checks.get("must_include_any", [])]
        if must_include_any:
            combined = " ".join(comments).lower()
            if not any(token in combined for token in must_include_any):
                result["messages"].append(
                    "None of required phrases found: %s"
                    % ", ".join(checks.get("must_include_any", []))
                )

        forbid_any = [s.lower() for s in checks.get("forbid_any", [])]
        if forbid_any:
            combined = " ".join(comments).lower()
            blocked = [token for token in forbid_any if token in combined]
            if blocked:
                result["messages"].append(
                    "Forbidden phrases found: %s" % ", ".join(blocked)
                )

        if not result["messages"]:
            result["passed"] = True
            result["messages"].append("All checks passed.")

        return result

    except urllib.error.HTTPError as exc:
        result["messages"].append("HTTP error: %s" % exc)
        return result
    except Exception as exc:  # noqa: BLE001
        result["messages"].append("Unexpected error: %s" % exc)
        return result


def discover_cases(agent: str = "") -> List[Path]:
    if not CASES_DIR.exists():
        return []
    pattern = "**/*.json" if not agent else "%s/*.json" % agent
    return sorted(CASES_DIR.glob(pattern))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run commentgen harness cases")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8010",
        help="Base URL for project API",
    )
    parser.add_argument(
        "--agent",
        default="",
        help="Optional agent case folder name (e.g. comment_reply)",
    )
    args = parser.parse_args()

    cases = discover_cases(args.agent)
    if not cases:
        print("No harness cases found.")
        return 1

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()

    results = [run_case(args.base_url.rstrip("/"), case) for case in cases]
    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed

    report = {
        "started_at": started_at,
        "base_url": args.base_url,
        "agent_filter": args.agent or None,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORT_DIR / ("report-%s.json" % stamp)
    report_path.write_text(json.dumps(report, indent=2))

    print("Harness complete: %d passed, %d failed, total %d" % (passed, failed, len(results)))
    print("Report: %s" % report_path)

    if failed > 0:
        for item in results:
            if not item["passed"]:
                print("- FAIL %s: %s" % (item["case_name"], "; ".join(item["messages"])))
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
