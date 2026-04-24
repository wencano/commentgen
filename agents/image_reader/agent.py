from pathlib import Path
import asyncio

from agents.guardrails import (
    clip_extracted_image_text,
    contains_strict_disallowed,
)
from app.llm_client import LLMClient


class ImageReaderAgent:
    agent_name = "image_reader"

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        prompt_path = Path(__file__).resolve().parent / "prompt.md"
        return prompt_path.read_text()

    async def extract_text(self, image_data_url: str) -> str:
        if not image_data_url:
            return ""
        # No provider key means no multimodal extraction available.
        if not self.llm.is_configured():
            await asyncio.sleep(0.45)
            return ""
        text = await self.llm.extract_text_from_image(
            image_data_url=image_data_url,
            prompt=self.prompt_template,
            temperature=0.2,
            top_p=0.95,
        )
        if not text:
            await asyncio.sleep(0.25)
        t = " ".join(text.strip().split())
        t = clip_extracted_image_text(t)
        if contains_strict_disallowed(t):
            return ""
        return t
