"""
LLMService is the single place that talks to a model. Agents call
`LLMService.generate(...)` and never touch Ollama (or whatever backend is
configured) directly. That indirection is what lets us swap Ollama for
OpenAI, Anthropic, etc. later without touching agent code.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
DEFAULT_TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))


class LLMServiceError(RuntimeError):
    """Raised when the underlying model backend is unreachable or errors out."""


@dataclass
class LLMResponse:
    text: str
    raw: dict


class LLMService:
    def __init__(
        self,
        base_url: str = OLLAMA_URL,
        model: str = OLLAMA_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def is_reachable(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def generate(self, prompt: str, system: Optional[str] = None, temperature: float = 0.2) -> LLMResponse:
        """Single-shot generation against Ollama's /api/generate endpoint."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": temperature},
        }
        try:
            r = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            r.raise_for_status()
        except requests.RequestException as e:
            raise LLMServiceError(f"Could not reach Ollama at {self.base_url}: {e}") from e

        data = r.json()
        return LLMResponse(text=data.get("response", ""), raw=data)

    def generate_json(self, prompt: str, system: Optional[str] = None) -> dict:
        """Generate and parse a JSON object out of the response, tolerating
        markdown code fences or stray text around the JSON payload."""
        response = self.generate(prompt, system=system, temperature=0.0)
        return extract_json(response.text)


def extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None

    if candidate is None:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        candidate = brace.group(0) if brace else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise LLMServiceError(f"Model did not return valid JSON: {e}\nRaw text: {text[:500]}") from e


def extract_code(text: str, language_hint: str = "python") -> str:
    """Pull code out of a model response, preferring a fenced code block."""
    fenced = re.search(rf"```(?:{language_hint})?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return text.strip()
