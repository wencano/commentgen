import base64
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import (
    GOOGLE_API_KEY,
    GOOGLE_MODEL,
    LLM_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_MODEL,
    OPENROUTER_SITE_URL,
)


class LLMClient:
    def __init__(self) -> None:
        self.provider = LLM_PROVIDER if LLM_PROVIDER in ("gemini", "openrouter") else "gemini"
        self.gemini_key = GOOGLE_API_KEY
        self.gemini_model = GOOGLE_MODEL
        self.openrouter_key = OPENROUTER_API_KEY
        self.openrouter_model = OPENROUTER_MODEL
        self.openrouter_site = OPENROUTER_SITE_URL
        self.openrouter_app = OPENROUTER_APP_NAME

    def is_configured(self) -> bool:
        if self.provider == "openrouter":
            return bool(self.openrouter_key)
        return bool(self.gemini_key)

    def active_model(self) -> str:
        if self.provider == "openrouter":
            return self.openrouter_model
        return self.gemini_model

    def active_provider_label(self) -> str:
        if self.provider == "openrouter":
            return "openrouter"
        return "google-ai-studio"

    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        top_p: float = 0.95,
    ) -> str:
        if not self.is_configured():
            return ""
        if self.provider == "openrouter":
            return await self._openrouter_text(prompt, temperature, top_p)
        return await self._gemini_text(prompt, temperature, top_p)

    async def extract_text_from_image(
        self,
        image_data_url: str,
        prompt: str,
        temperature: float = 0.2,
        top_p: float = 0.95,
    ) -> str:
        if not self.is_configured():
            return ""
        if self.provider == "openrouter":
            return await self._openrouter_image_text(
                image_data_url=image_data_url,
                prompt=prompt,
                temperature=temperature,
                top_p=top_p,
            )
        return await self._gemini_image_text(
            image_data_url=image_data_url,
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
        )

    async def _gemini_text(self, prompt: str, temperature: float, top_p: float) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={self.gemini_key}"
        )
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "topP": top_p},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                return ""
            data = resp.json()
        return self._extract_gemini_text(data)

    async def _gemini_image_text(
        self,
        image_data_url: str,
        prompt: str,
        temperature: float,
        top_p: float,
    ) -> str:
        mime_type, image_b64 = self._split_data_url(image_data_url)
        if not mime_type or not image_b64:
            return ""
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={self.gemini_key}"
        )
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                    ]
                }
            ],
            "generationConfig": {"temperature": temperature, "topP": top_p},
        }
        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                return ""
            data = resp.json()
        return self._extract_gemini_text(data)

    async def _openrouter_text(self, prompt: str, temperature: float, top_p: float) -> str:
        payload: Dict[str, Any] = {
            "model": self.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "top_p": top_p,
        }
        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=self._openrouter_headers(),
            )
            if resp.status_code >= 400:
                return ""
            data = resp.json()
        return self._extract_openrouter_text(data)

    async def _openrouter_image_text(
        self,
        image_data_url: str,
        prompt: str,
        temperature: float,
        top_p: float,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.openrouter_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
            "temperature": temperature,
            "top_p": top_p,
        }
        async with httpx.AsyncClient(timeout=50) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=self._openrouter_headers(),
            )
            if resp.status_code >= 400:
                return ""
            data = resp.json()
        return self._extract_openrouter_text(data)

    def _openrouter_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": self.openrouter_site,
            "X-Title": self.openrouter_app,
            "Content-Type": "application/json",
        }

    def _extract_gemini_text(self, data: Dict[str, Any]) -> str:
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return ""

    def _extract_openrouter_text(self, data: Dict[str, Any]) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    if isinstance(text, str):
                        chunks.append(text)
            return "\n".join(chunks).strip()
        return ""

    def _split_data_url(self, data_url: str) -> Tuple[Optional[str], Optional[str]]:
        if not data_url.startswith("data:") or ";base64," not in data_url:
            return None, None
        header, encoded = data_url.split(";base64,", 1)
        mime = header.replace("data:", "").strip()
        if not mime:
            return None, None
        try:
            base64.b64decode(encoded, validate=True)
        except Exception:  # noqa: BLE001
            return None, None
        return mime, encoded
