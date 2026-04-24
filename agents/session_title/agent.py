from pathlib import Path
import asyncio

from agents.guardrails import (
    clip_for_session_title_seed,
    contains_strict_disallowed,
    looks_like_injection_attack,
    sanitize_title_text,
)
from app.llm_client import LLMClient


class SessionTitleAgent:
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        prompt_path = Path(__file__).resolve().parent / "prompt.md"
        return prompt_path.read_text()

    async def generate_title(self, message: str) -> str:
        message = clip_for_session_title_seed((message or "").strip())
        if not message:
            return "New chat"
        if contains_strict_disallowed(message) or looks_like_injection_attack(message):
            return "New chat"
        # Fall back locally so session creation never blocks on provider availability.
        if not self.llm.is_configured():
            await asyncio.sleep(0.25)
            return sanitize_title_text(self._fallback_title(message))

        title = await self._generate_with_llm(message)
        if not title:
            await asyncio.sleep(0.15)
        return sanitize_title_text(title or self._fallback_title(message))

    async def _generate_with_llm(self, message: str) -> str:
        prompt = (
            f"{self.prompt_template}\n\n"
            "User message:\n"
            f"{message}\n"
        )
        text = await self.llm.generate_text(prompt=prompt, temperature=0.2, top_p=0.95)
        # Normalize whitespace; length cap is enforced in sanitize_title_text.
        clean = " ".join(text.strip().split())
        return clean[:200]

    def _fallback_title(self, message: str) -> str:
        words = [w.strip(".,!?;:") for w in message.split() if w.strip(".,!?;:")]
        if not words:
            return "New chat"
        return " ".join(words[:6])
