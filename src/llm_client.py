from __future__ import annotations

import json
import os
from typing import TypeVar

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
from pydantic import BaseModel

from src.constants import DEFAULT_API_TIMEOUT_SECONDS, DEFAULT_MODEL, DEFAULT_TEMPERATURE

load_dotenv()

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self._client = OpenAI(api_key=self.api_key, timeout=DEFAULT_API_TIMEOUT_SECONDS)

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> T:
        messages: list[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam] = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt),
            ChatCompletionUserMessageParam(role="user", content=user_prompt),
        ]
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=messages,
            )
        except BadRequestError as exc:
            if exc.code != "unsupported_value" or exc.param != "temperature":
                raise
            response = self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=messages,
            )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("LLM returned an empty response.")
        payload = json.loads(content)
        return response_model.model_validate(payload)
