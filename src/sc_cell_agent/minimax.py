from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib import request

from .env import load_env_file

Transport = Callable[[str, dict[str, str], dict[str, Any]], Any]


@dataclass(slots=True)
class MiniMaxSettings:
    api_key: str
    text_model: str
    vision_model: str
    text_api_url: str
    vision_api_url: str

    @classmethod
    def from_env(cls, env_path: str | Path = ".env", override: bool = False) -> "MiniMaxSettings":
        load_env_file(env_path, override=override)
        required = {
            "api_key": "MINIMAX_API_KEY",
            "text_model": "MINIMAX_TEXT_MODEL",
            "vision_model": "MINIMAX_VISION_MODEL",
            "text_api_url": "MINIMAX_TEXT_API_URL",
            "vision_api_url": "MINIMAX_VISION_API_URL",
        }
        missing = [name for name in required.values() if not os.environ.get(name)]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"Missing MiniMax environment variables: {missing_text}")
        return cls(
            api_key=os.environ[required["api_key"]],
            text_model=os.environ[required["text_model"]],
            vision_model=os.environ[required["vision_model"]],
            text_api_url=os.environ[required["text_api_url"]],
            vision_api_url=os.environ[required["vision_api_url"]],
        )


class MiniMaxBaseClient:
    def __init__(self, settings: MiniMaxSettings, transport: Transport | None = None) -> None:
        self.settings = settings
        self.transport = transport or self._default_transport

    @staticmethod
    def _default_transport(url: str, headers: dict[str, str], payload: dict[str, Any]) -> Any:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url=url, data=body, headers=headers, method="POST")
        with request.urlopen(req) as response:  # noqa: S310
            text = response.read().decode("utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }


class MiniMaxTextClient(MiniMaxBaseClient):
    @classmethod
    def from_env(
        cls,
        env_path: str | Path = ".env",
        override: bool = False,
        transport: Transport | None = None,
    ) -> "MiniMaxTextClient":
        return cls(MiniMaxSettings.from_env(env_path, override=override), transport=transport)

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.settings.text_model,
            "input": {"prompt": prompt},
        }
        response = self.transport(self.settings.text_api_url, self._headers(), payload)
        if isinstance(response, dict):
            return str(response.get("output_text") or response.get("text") or response)
        return str(response)


class MiniMaxVisionClient(MiniMaxBaseClient):
    @classmethod
    def from_env(
        cls,
        env_path: str | Path = ".env",
        override: bool = False,
        transport: Transport | None = None,
    ) -> "MiniMaxVisionClient":
        return cls(MiniMaxSettings.from_env(env_path, override=override), transport=transport)

    def review_image(self, prompt: str, image_path: Path) -> str:
        image_bytes = image_path.read_bytes()
        payload = {
            "model": self.settings.vision_model,
            "input": {
                "prompt": prompt,
                "image_base64": base64.b64encode(image_bytes).decode("utf-8"),
                "image_name": image_path.name,
            },
        }
        response = self.transport(self.settings.vision_api_url, self._headers(), payload)
        if isinstance(response, dict):
            return str(response.get("output_text") or response.get("text") or response)
        return str(response)
