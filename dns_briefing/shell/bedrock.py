from __future__ import annotations

import json
import logging
from typing import Any

import boto3

from dns_briefing.core.prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MAX_TOKENS = 32768


class BedrockClient:
    def __init__(self, boto_client: Any, model_id: str) -> None:
        self._client = boto_client
        self._model_id = model_id

    @classmethod
    def from_config(cls, region: str, model_id: str) -> BedrockClient:
        return cls(boto3.client("bedrock-runtime", region_name=region), model_id)

    def generate_report(
        self,
        messages: list[dict[str, str]],
        system: str = SYSTEM_PROMPT,
    ) -> str:
        response = self._client.invoke_model_with_response_stream(
            modelId=self._model_id,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": MAX_TOKENS,
                    "system": system,
                    "messages": messages,
                }
            ),
            contentType="application/json",
            accept="application/json",
        )
        return self._collect_stream(response["body"])

    def _collect_stream(self, stream: Any) -> str:
        parts: list[str] = []
        stop_reason: str | None = None

        for event in stream:
            chunk = json.loads(event["chunk"]["bytes"])
            match chunk.get("type"):
                case "content_block_delta":
                    parts.append(chunk["delta"]["text"])
                case "message_delta":
                    stop_reason = chunk["delta"].get("stop_reason")

        if stop_reason == "max_tokens":
            raise RuntimeError(
                f"Briefing truncated: model hit max_tokens={MAX_TOKENS}. "
                "Increase MAX_TOKENS or split the prompt."
            )
        return "".join(parts)
