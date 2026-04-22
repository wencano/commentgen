#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8010}"

echo "Running commentgen harness against: ${BASE_URL}"
python harness/runner.py --base-url "${BASE_URL}" --agent comment_reply
