"""
LLMService supports both Ollama (local) and Gemini (cloud).

Agents only call LLMService, so we can change the model provider
without changing the agent code.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5-coder:7b"
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

DEFAULT_TIMEOUT = int(
    os.getenv("LLM_TIMEOUT_SECONDS", "120")
)


# ---------------------------------------------------------
# Classes
# ---------------------------------------------------------

class LLMServiceError(RuntimeError):
    """Raised when the LLM backend cannot be reached."""


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

        self.provider = LLM_PROVIDER
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    # -----------------------------------------------------
    # Check whether the LLM is available
    # -----------------------------------------------------

    def is_reachable(self) -> bool:

        if self.provider == "gemini":

            return bool(GEMINI_API_KEY)

        try:

            r = requests.get(
                f"{self.base_url}/api/tags",
                timeout=3
            )

            return r.status_code == 200

        except requests.RequestException:

            return False

    # -----------------------------------------------------
    # Generate response
    # -----------------------------------------------------

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2
    ) -> LLMResponse:

        if self.provider == "gemini":

            return self._generate_gemini(
                prompt,
                system,
                temperature
            )

        return self._generate_ollama(
            prompt,
            system,
            temperature
        )

    # -----------------------------------------------------
    # Ollama
    # -----------------------------------------------------

    def _generate_ollama(
        self,
        prompt: str,
        system: Optional[str],
        temperature: float
    ) -> LLMResponse:

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": temperature
            },
        }

        try:

            r = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )

            r.raise_for_status()

        except requests.RequestException as e:

            raise LLMServiceError(
                f"Could not reach Ollama at "
                f"{self.base_url}: {e}"
            ) from e

        data = r.json()

        return LLMResponse(
            text=data.get("response", ""),
            raw=data
        )

    # -----------------------------------------------------
    # Gemini
    # -----------------------------------------------------

    def _generate_gemini(
        self,
        prompt: str,
        system: Optional[str],
        temperature: float
    ) -> LLMResponse:

        if not GEMINI_API_KEY:

            raise LLMServiceError(
                "GEMINI_API_KEY is not configured."
            )

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{GEMINI_MODEL}:generateContent"
            f"?key={GEMINI_API_KEY}"
        )

        contents = []

        if system:
            contents.append({
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "System instructions:\n"
                            + system
                        )
                    }
                ]
            })

        contents.append({
            "role": "user",
            "parts": [
                {
                    "text": prompt
                }
            ]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature
            }
        }

        try:

            r = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )

            r.raise_for_status()

        except requests.RequestException as e:

            raise LLMServiceError(
                f"Could not reach Gemini API: {e}"
            ) from e

        data = r.json()

        try:

            text = data["candidates"][0]["content"]["parts"][0]["text"]

        except (KeyError, IndexError, TypeError):

            raise LLMServiceError(
                f"Unexpected Gemini response: {data}"
            )

        return LLMResponse(
            text=text,
            raw=data
        )

    # -----------------------------------------------------
    # Generate JSON
    # -----------------------------------------------------

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None
    ) -> dict:

        response = self.generate(
            prompt,
            system=system,
            temperature=0.0
        )

        return extract_json(response.text)


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def extract_json(text: str) -> dict:

    fenced = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.DOTALL
    )

    candidate = (
        fenced.group(1)
        if fenced
        else None
    )

    if candidate is None:

        brace = re.search(
            r"\{.*\}",
            text,
            re.DOTALL
        )

        candidate = (
            brace.group(0)
            if brace
            else text
        )

    try:

        return json.loads(candidate)

    except json.JSONDecodeError as e:

        raise LLMServiceError(
            "Model did not return valid JSON: "
            f"{e}\nRaw text: {text[:500]}"
        )


def extract_code(
    text: str,
    language_hint: str = "python"
) -> str:

    fenced = re.search(
        rf"```(?:{language_hint})?\s*(.*?)```",
        text,
        re.DOTALL
    )

    if fenced:

        return fenced.group(1).strip()

    return text.strip()