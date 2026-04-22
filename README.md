# commentgen

Minimal FastAPI project for generating social post comments.

Assigned port: `8010` (root convention starts at `8010` and increments by `1` per project).
Base URL: `http://127.0.0.1:8010`

## Features

- SQLite for all runtime data storage (runs, sessions, messages)
- `POST /runs` to generate comments
- `GET /runs/{id}/status` to check run status
- `GET /runs/{id}/artifacts` to fetch the saved run report
- `GET /health` for health checks
- Provider abstraction: `gemini` or `openrouter` with local fallback when keys are missing
- Agent-first layout under `agents/{agentname}/` with prompt + Python logic
- Chat UI at `/` with sidebar sessions + main conversation pane
- Iterative comment workflow per session (`/api/sessions/{id}/iterate`)
- Auto session title generation via `agents/session_title`
- Screenshot-based comment generation via `agents/image_reader`
- Decoding controls in UI/API (`temperature`, `top_p`)

## Project layout

```text
commentgen/
  app/                    # FastAPI wrapper and run storage
    static/index.html     # Chat UI (Claude-like layout)
  agents/
    comment_reply/
      prompt.md           # Agent prompt contract
      agent.py            # Agent runtime logic
    session_title/
      prompt.md
      agent.py
    image_reader/
      prompt.md
      agent.py
  harness/
    cases/comment_reply/  # Agent-scoped harness cases
    runner.py             # Shared project harness runner
```

## Harness quick run

```bash
python harness/runner.py --base-url http://127.0.0.1:8010 --agent comment_reply
```

## Chat endpoints

- `GET /` home page
- `GET /chat` chat interface
- `GET /api/sessions`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/iterate`

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8010
```

Provider config examples:

```bash
# Gemini
export LLM_PROVIDER=gemini
export GOOGLE_API_KEY=...

# OpenRouter
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY=...
export OPENROUTER_MODEL=openai/gpt-4o-mini
```

## Example request

```bash
curl -X POST "http://127.0.0.1:8010/runs" \
  -H "Content-Type: application/json" \
  -d '{
    "source_post_text": "We just launched a lightweight analytics plugin for WordPress.",
    "intent": "supportive",
    "tone": "professional",
    "length": "short",
    "variants": 3
  }'
```

## Notes

- When provider keys are missing, comment generation falls back to deterministic local variants.
- Runtime data is stored in SQLite (`commentgen.db`).
