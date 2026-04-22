import json
import asyncio
from pathlib import Path
from typing import List, Tuple

from app.llm_client import LLMClient
from app.schemas import CommentRunRequest


class CommentReplyAgent:
    agent_name = "comment_reply"

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client
        self.prompt_template = self._load_prompt_template()

    async def generate(self, req: CommentRunRequest) -> Tuple[List[str], str, str]:
        # Keep the app usable offline or without provider keys.
        if not self.llm.is_configured():
            await asyncio.sleep(1.0)
            return self._fallback(req), "local-fallback", "deterministic-template"

        comments = await self._generate_with_llm(req)
        if comments:
            return (
                comments[: req.variants],
                self.llm.active_provider_label(),
                self.llm.active_model(),
            )
        # Simulate graceful degradation when provider returns unusable output.
        await asyncio.sleep(0.6)
        return self._fallback(req), "local-fallback", "deterministic-template"

    def _load_prompt_template(self) -> str:
        prompt_path = Path(__file__).resolve().parent / "prompt.md"
        return prompt_path.read_text()

    async def _generate_with_llm(self, req: CommentRunRequest) -> List[str]:
        prompt = self._build_prompt(req)
        # Provider is selected centrally by LLMClient (gemini/openrouter).
        text = await self.llm.generate_text(
            prompt=prompt,
            temperature=req.temperature,
            top_p=req.top_p,
        )
        if not text:
            return []
        return self._parse_comments_json(text)

    def _build_prompt(self, req: CommentRunRequest) -> str:
        return (
            f"{self.prompt_template}\n\n"
            "Runtime request:\n"
            f"Intent: {req.intent}\n"
            f"Tone: {req.tone}\n"
            f"Length: {req.length}\n"
            f"Count: {req.variants}\n"
            "Source post:\n"
            f"{req.source_post_text}\n"
        )

    def _parse_comments_json(self, text: str) -> List[str]:
        candidate = text.strip()
        # Some models wrap JSON in fenced code blocks; strip wrappers first.
        if "```" in candidate:
            candidate = candidate.replace("```json", "").replace("```", "").strip()

        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            # Best-effort recovery when extra text appears around JSON.
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return []
            try:
                obj = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                return []

        comments = obj.get("comments", [])
        if not isinstance(comments, list):
            return []
        return [c.strip() for c in comments if isinstance(c, str) and c.strip()]

    def _fallback(self, req: CommentRunRequest) -> List[str]:
        # Deterministic templates keep tests/harness stable without external LLMs.
        base = [
            (
                "Love this direction. "
                f"{req.source_post_text[:80].rstrip()}... looking forward to seeing how it evolves."
            ),
            "Strong update. The positioning is clear and practical-great work shipping this.",
            "Nice launch. This addresses a real need and the message is easy to understand.",
            "This is useful and well explained. Curious to hear what users ask for next.",
            "Great momentum here. The value proposition comes through clearly.",
        ]
        return base[: req.variants]
