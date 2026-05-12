# dns_briefing/bedrock.py
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
        client = boto3.client("bedrock-runtime", region_name=region)
        return cls(client, model_id)

    def generate_report(
        self,
        messages: list[dict[str, str]],
        system: str = SYSTEM_PROMPT,
    ) -> str:
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": MAX_TOKENS,
                "system": system,
                "messages": messages,
            }
        )
        response = self._client.invoke_model(
            modelId=self._model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result: dict[str, Any] = json.loads(response["body"].read())
        stop_reason = result.get("stop_reason")
        if stop_reason == "max_tokens":
            raise RuntimeError(
                f"Briefing truncated: model hit max_tokens={MAX_TOKENS}. "
                "Increase MAX_TOKENS or split the prompt."
            )
        return str(result["content"][0]["text"])
