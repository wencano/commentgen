from datetime import datetime, timezone
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse

from agents.image_reader.agent import ImageReaderAgent
from agents.session_title.agent import SessionTitleAgent
from app.db import init_db
from app.schemas import (
    ChatMessage,
    CommentArtifactResponse,
    CommentRunCreateResponse,
    CommentRunRequest,
    CommentRunStatusResponse,
    SessionCreateRequest,
    SessionDetail,
    SessionIterateRequest,
    SessionIterateResponse,
    SessionSummary,
)
from app.services.comment_generator import CommentGenerator
from app.store import (
    add_message,
    create_session,
    get_session,
    list_messages,
    list_sessions,
    load_run,
    save_run,
    touch_session,
    update_session_title,
)


app = FastAPI(title="commentgen", version="0.1.0")
generator = CommentGenerator()
title_agent = SessionTitleAgent(llm_client=generator.llm)
image_reader = ImageReaderAgent(llm_client=generator.llm)
STATIC_CHAT = Path(__file__).resolve().parent / "static" / "index.html"


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def home_ui() -> FileResponse:
    return FileResponse(STATIC_CHAT)


@app.get("/chat")
def chat_ui() -> FileResponse:
    return FileResponse(STATIC_CHAT)


@app.post("/runs", response_model=CommentRunCreateResponse)
async def create_run(req: CommentRunRequest) -> CommentRunCreateResponse:
    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc)
    source_text, extracted_image_text = await _resolve_source_text(
        req.source_post_text,
        req.image_data_url,
    )
    if len(source_text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Provide source_post_text or a readable image screenshot.",
        )
    normalized_req = CommentRunRequest(
        source_post_text=source_text,
        image_data_url=req.image_data_url,
        intent=req.intent,
        tone=req.tone,
        length=req.length,
        variants=req.variants,
        temperature=req.temperature,
        top_p=req.top_p,
    )

    running_payload = {
        "run_id": run_id,
        "status": "running",
        "agent_name": generator.agent_name,
        "request": normalized_req.model_dump(),
        "comments": [],
        "provider": "pending",
        "model": "pending",
        "extracted_image_text": extracted_image_text,
        "created_at": created_at.isoformat(),
        "completed_at": None,
    }
    save_run(run_id, running_payload)

    try:
        comments, provider, model = await generator.generate(normalized_req)
        completed_at = datetime.now(timezone.utc)
        completed_payload = {
            **running_payload,
            "status": "completed",
            "comments": comments,
            "provider": provider,
            "model": model,
            "completed_at": completed_at.isoformat(),
        }
        save_run(run_id, completed_payload)
    except Exception as exc:  # noqa: BLE001
        failed_payload = {
            **running_payload,
            "status": "failed",
            "error": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        save_run(run_id, failed_payload)
        raise HTTPException(status_code=500, detail="Run failed") from exc

    return CommentRunCreateResponse(
        run_id=run_id,
        status="completed",
        created_at=created_at,
    )


@app.get("/api/sessions", response_model=list[SessionSummary])
def api_list_sessions() -> list[SessionSummary]:
    sessions = list_sessions()
    return [
        SessionSummary(
            session_id=item["session_id"],
            title=item["title"],
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )
        for item in sessions
    ]


@app.post("/api/sessions", response_model=SessionDetail)
async def api_create_session(req: SessionCreateRequest) -> SessionDetail:
    now = datetime.now(timezone.utc)
    session_id = str(uuid4())
    first_message = req.first_message.strip()
    title = "New chat"
    if first_message:
        title = await title_agent.generate_title(first_message)

    create_session(session_id=session_id, title=title, created_at=now.isoformat())

    if first_message:
        add_message(
            message_id=str(uuid4()),
            session_id=session_id,
            role="user",
            content=first_message,
            created_at=now.isoformat(),
        )
        touch_session(session_id=session_id, updated_at=now.isoformat())

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=500, detail="Session creation failed")
    messages = list_messages(session_id)
    return _build_session_detail(session, messages)


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
def api_get_session(session_id: str) -> SessionDetail:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = list_messages(session_id)
    return _build_session_detail(session, messages)


@app.post("/api/sessions/{session_id}/iterate", response_model=SessionIterateResponse)
async def api_iterate_session(
    session_id: str,
    req: SessionIterateRequest,
) -> SessionIterateResponse:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    now = datetime.now(timezone.utc)
    user_text = req.message.strip()
    source_text, extracted_image_text = await _resolve_source_text(
        user_text,
        req.image_data_url,
    )
    if not source_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Provide message text or a readable image screenshot.",
        )

    add_message(
        message_id=str(uuid4()),
        session_id=session_id,
        role="user",
        content=_user_message_display_text(user_text, extracted_image_text),
        created_at=now.isoformat(),
    )

    if session["title"] == "New chat":
        title_seed = user_text if user_text else extracted_image_text
        new_title = await title_agent.generate_title(title_seed)
        update_session_title(
            session_id=session_id,
            title=new_title,
            updated_at=now.isoformat(),
        )
        session["title"] = new_title

    run_request = CommentRunRequest(
        source_post_text=source_text,
        image_data_url=req.image_data_url,
        intent="supportive",
        tone="professional",
        length="short",
        variants=1,
        temperature=0.7,
        top_p=0.95,
    )
    comments, provider, model = await generator.generate(run_request)
    assistant_text = comments[0] if comments else "No reply generated."
    assistant_id = str(uuid4())
    add_message(
        message_id=assistant_id,
        session_id=session_id,
        role="assistant",
        content=assistant_text,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    touch_session(session_id=session_id, updated_at=datetime.now(timezone.utc).isoformat())

    assistant_message = ChatMessage(
        message_id=assistant_id,
        session_id=session_id,
        role="assistant",
        content=assistant_text,
        created_at=datetime.now(timezone.utc),
    )
    return SessionIterateResponse(
        session_id=session_id,
        title=session["title"],
        assistant_message=assistant_message,
        comments=comments[:1],
        extracted_image_text=extracted_image_text,
    )


@app.post("/api/sessions/{session_id}/iterate/stream")
async def api_iterate_session_stream(
    session_id: str,
    req: SessionIterateRequest,
) -> StreamingResponse:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_stream():
        try:
            now = datetime.now(timezone.utc)
            user_text = req.message.strip()
            extracted_image_text = ""

            if req.image_data_url:
                yield _sse("status", {"agent": "image_reader", "message": "Reading screenshot..."})
                extracted_image_text = await image_reader.extract_text(req.image_data_url)

            source_text, extracted_image_text_final = _merge_source_text(
                user_text,
                extracted_image_text,
            )
            if not source_text.strip():
                yield _sse("error", {"message": "Provide message text or a readable image screenshot."})
                return

            add_message(
                message_id=str(uuid4()),
                session_id=session_id,
                role="user",
                content=_user_message_display_text(user_text, extracted_image_text_final),
                created_at=now.isoformat(),
            )

            title = session["title"]
            if title == "New chat":
                yield _sse("status", {"agent": "session_title", "message": "Generating session title..."})
                title_seed = user_text if user_text else extracted_image_text_final
                title = await title_agent.generate_title(title_seed)
                update_session_title(session_id=session_id, title=title, updated_at=now.isoformat())

            run_request = CommentRunRequest(
                source_post_text=source_text,
                image_data_url=req.image_data_url,
                intent="supportive",
                tone="professional",
                length="short",
                variants=1,
                temperature=0.7,
                top_p=0.95,
            )
            yield _sse("status", {"agent": "comment_reply", "message": "Generating reply..."})
            comments, provider, model = await generator.generate(run_request)
            assistant_text = comments[0] if comments else "No reply generated."

            # Simulate token-like chunk streaming from final response.
            # Fallback is intentionally slower to visualize local generation work.
            chunk_delay = 0.09 if provider == "local-fallback" else 0.025
            partial = ""
            for token in assistant_text.split(" "):
                partial = token if not partial else f"{partial} {token}"
                yield _sse("chunk", {"text": partial})
                await asyncio.sleep(chunk_delay)

            assistant_id = str(uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            add_message(
                message_id=assistant_id,
                session_id=session_id,
                role="assistant",
                content=assistant_text,
                created_at=created_at,
            )
            touch_session(session_id=session_id, updated_at=created_at)

            done_payload = {
                "session_id": session_id,
                "title": title,
                "assistant_message": {
                    "message_id": assistant_id,
                    "session_id": session_id,
                    "role": "assistant",
                    "content": assistant_text,
                    "created_at": created_at,
                },
                "comments": comments[:1],
                "extracted_image_text": extracted_image_text_final,
                "provider": provider,
                "model": model,
            }
            yield _sse("done", done_payload)
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/runs/{run_id}/status", response_model=CommentRunStatusResponse)
def get_run_status(run_id: str) -> CommentRunStatusResponse:
    payload = load_run(run_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Run not found")

    return CommentRunStatusResponse(
        run_id=payload["run_id"],
        status=payload["status"],
        created_at=datetime.fromisoformat(payload["created_at"]),
        completed_at=datetime.fromisoformat(payload["completed_at"])
        if payload.get("completed_at")
        else None,
        comment_count=len(payload.get("comments", [])),
        agent_name=payload.get("agent_name", "comment_reply"),
    )


@app.get("/runs/{run_id}/artifacts", response_model=CommentArtifactResponse)
def get_run_artifacts(run_id: str) -> CommentArtifactResponse:
    payload = load_run(run_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Run not found")

    return CommentArtifactResponse(
        run_id=payload["run_id"],
        status=payload["status"],
        request=CommentRunRequest(**payload["request"]),
        comments=payload.get("comments", []),
        agent_name=payload.get("agent_name", "comment_reply"),
        provider=payload.get("provider", "unknown"),
        model=payload.get("model", "unknown"),
        created_at=datetime.fromisoformat(payload["created_at"]),
        completed_at=datetime.fromisoformat(payload["completed_at"])
        if payload.get("completed_at")
        else None,
    )


def _build_session_detail(session: dict, messages: list[dict]) -> SessionDetail:
    return SessionDetail(
        session_id=session["session_id"],
        title=session["title"],
        created_at=datetime.fromisoformat(session["created_at"]),
        updated_at=datetime.fromisoformat(session["updated_at"]),
        messages=[
            ChatMessage(
                message_id=item["message_id"],
                session_id=item["session_id"],
                role=item["role"],
                content=item["content"],
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in messages
        ],
    )


async def _resolve_source_text(user_text: str, image_data_url: str = None):
    text = (user_text or "").strip()
    extracted = ""
    if image_data_url:
        extracted = await image_reader.extract_text(image_data_url)

    if text and extracted:
        return f"{text}\n\nExtracted screenshot text:\n{extracted}", extracted
    if text:
        return text, extracted
    if extracted:
        return extracted, extracted
    return "", ""


def _merge_source_text(user_text: str, extracted: str):
    text = (user_text or "").strip()
    extracted_text = (extracted or "").strip()
    if text and extracted_text:
        return f"{text}\n\nExtracted screenshot text:\n{extracted_text}", extracted_text
    if text:
        return text, extracted_text
    if extracted_text:
        return extracted_text, extracted_text
    return "", ""


def _user_message_display_text(user_text: str, extracted_image_text: str) -> str:
    text = (user_text or "").strip()
    extracted = (extracted_image_text or "").strip()
    if text and extracted:
        return f"{text}\n\n[Extracted from image]\n{extracted}"
    if text:
        return text
    if extracted:
        return f"[Image message]\n{extracted}"
    return ""


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"
