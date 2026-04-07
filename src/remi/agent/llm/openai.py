"""OpenAI adapter for the LLM provider port.

Also serves as the base for any OpenAI-compatible API (Ollama, vLLM,
Together, Groq, etc.) by passing a custom ``base_url`` in ProviderConfig.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from remi.agent.llm.types import (
    LLMProvider,
    LLMResponse,
    Message,
    ModelCapabilities,
    ModelPricing,
    ProviderConfig,
    StreamChunk,
    TokenUsage,
    ToolCallRequest,
    ToolDefinition,
)
from remi.types.errors import LLMConnectionError, LLMRateLimitError, LLMTimeoutError

_MODEL_REGISTRY: dict[str, ModelCapabilities] = {
    "gpt-4o": ModelCapabilities(
        context_window=128_000,
        max_output_tokens=16_384,
        supports_vision=True,
        pricing=ModelPricing(2.5, 10.0),
    ),
    "gpt-4o-mini": ModelCapabilities(
        context_window=128_000,
        max_output_tokens=16_384,
        supports_vision=True,
        pricing=ModelPricing(0.15, 0.6),
    ),
    "gpt-4-turbo": ModelCapabilities(
        context_window=128_000,
        max_output_tokens=4_096,
        supports_vision=True,
        pricing=ModelPricing(10.0, 30.0),
    ),
    "gpt-4.1": ModelCapabilities(
        context_window=1_047_576,
        max_output_tokens=32_768,
        supports_vision=True,
        pricing=ModelPricing(2.0, 8.0),
    ),
    "gpt-4.1-mini": ModelCapabilities(
        context_window=1_047_576,
        max_output_tokens=32_768,
        supports_vision=True,
        pricing=ModelPricing(0.4, 1.6),
    ),
    "gpt-4.1-nano": ModelCapabilities(
        context_window=1_047_576,
        max_output_tokens=32_768,
        supports_vision=True,
        pricing=ModelPricing(0.1, 0.4),
    ),
    "o3-mini": ModelCapabilities(
        context_window=200_000,
        max_output_tokens=100_000,
        supports_vision=False,
        pricing=ModelPricing(1.1, 4.4),
    ),
}

_DEFAULT_CAPABILITIES = ModelCapabilities(
    context_window=128_000,
    max_output_tokens=4_096,
)


def _wrap_openai_error(exc: Exception) -> None:
    """Re-raise OpenAI SDK errors as provider-agnostic core types."""
    import openai

    if isinstance(exc, openai.APIConnectionError):
        raise LLMConnectionError(str(exc), provider="openai") from exc
    if isinstance(exc, openai.APITimeoutError):
        raise LLMTimeoutError(str(exc), provider="openai") from exc
    if isinstance(exc, openai.RateLimitError):
        raise LLMRateLimitError(str(exc), provider="openai") from exc
    raise exc


_TIKTOKEN_ENCODING = "cl100k_base"


class OpenAIProvider(LLMProvider):
    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._client: Any = None
        self._encoding: Any = None

    @staticmethod
    def _message_to_openai(msg: Message) -> dict[str, Any]:
        entry: dict[str, Any] = {"role": msg.role}
        if isinstance(msg.content, str):
            entry["content"] = msg.content
        else:
            entry["content"] = json.dumps(msg.content, default=str)
        if msg.name:
            entry["name"] = msg.name
        if msg.tool_call_id:
            entry["tool_call_id"] = msg.tool_call_id
        if msg.role == "assistant" and msg.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, default=str),
                    },
                }
                for tc in msg.tool_calls
            ]
        return entry

    @staticmethod
    def _tool_to_openai(defn: ToolDefinition) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": defn.name,
                "description": defn.description,
                "parameters": defn.to_json_schema(),
            },
        }

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import openai
            except ImportError as exc:
                raise RuntimeError(
                    "OpenAI provider requires the 'openai' package: pip install 'remi[openai]'"
                ) from exc
            self._client = openai.AsyncOpenAI(
                api_key=self._config.api_key,
                base_url=self._config.base_url,
            )
        return self._client

    def _get_encoding(self) -> Any:
        if self._encoding is None:
            try:
                import tiktoken
            except ImportError as exc:
                raise RuntimeError(
                    "Token counting requires the 'tiktoken' package: pip install tiktoken"
                ) from exc
            self._encoding = tiktoken.get_encoding(_TIKTOKEN_ENCODING)
        return self._encoding

    async def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        client = self._get_client()
        openai_messages = [self._message_to_openai(m) for m in messages]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = [self._tool_to_openai(t) for t in tools]

        try:
            resp = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            _wrap_openai_error(exc)

        choice = resp.choices[0]

        usage = (
            TokenUsage(
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
                total_tokens=resp.usage.total_tokens,
            )
            if resp.usage
            else TokenUsage()
        )

        tool_calls: list[ToolCallRequest] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {"raw": tc.function.arguments}
                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        return LLMResponse(
            content=choice.message.content,
            model=resp.model,
            usage=usage,
            tool_calls=tool_calls,
        )

    async def stream(
        self,
        *,
        model: str,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        client = self._get_client()
        openai_messages = [self._message_to_openai(m) for m in messages]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = [self._tool_to_openai(t) for t in tools]

        active_tool_calls: dict[int, dict[str, str]] = {}
        try:
            response_stream = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            _wrap_openai_error(exc)

        async for chunk in response_stream:
            choice = chunk.choices[0] if chunk.choices else None
            if choice and choice.delta:
                delta = choice.delta
                if delta.content:
                    yield StreamChunk(type="content_delta", content=delta.content)
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in active_tool_calls:
                            active_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "name": tc_delta.function.name
                                if tc_delta.function and tc_delta.function.name
                                else "",
                                "arguments": "",
                            }
                            if active_tool_calls[idx]["id"]:
                                yield StreamChunk(
                                    type="tool_call_start",
                                    tool_call_id=active_tool_calls[idx]["id"],
                                    tool_name=active_tool_calls[idx]["name"],
                                )
                        if tc_delta.function and tc_delta.function.arguments:
                            active_tool_calls[idx]["arguments"] += tc_delta.function.arguments
                            yield StreamChunk(
                                type="tool_call_delta",
                                tool_call_id=active_tool_calls[idx]["id"],
                                tool_arguments_delta=tc_delta.function.arguments,
                            )

            if chunk.usage:
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                )
                for tc_data in active_tool_calls.values():
                    yield StreamChunk(type="tool_call_end", tool_call_id=tc_data["id"])
                yield StreamChunk(type="done", usage=usage)

    def count_tokens(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[ToolDefinition] | None = None,
    ) -> int:
        enc = self._get_encoding()
        tokens_per_message = 3
        total = 0
        for msg in messages:
            total += tokens_per_message
            text = (
                msg.content
                if isinstance(msg.content, str)
                else json.dumps(msg.content, default=str)
            )
            total += len(enc.encode(text))
            if msg.role:
                total += len(enc.encode(msg.role))
            if msg.name:
                total += len(enc.encode(msg.name)) + 1
        total += 3
        if tools:
            for tool in tools:
                schema_text = json.dumps(tool.to_json_schema(), separators=(",", ":"))
                total += len(enc.encode(tool.name))
                total += len(enc.encode(tool.description))
                total += len(enc.encode(schema_text))
                total += 5
        return total

    def model_capabilities(self, model: str) -> ModelCapabilities:
        if model in _MODEL_REGISTRY:
            return _MODEL_REGISTRY[model]
        for prefix, caps in _MODEL_REGISTRY.items():
            if model.startswith(prefix):
                return caps
        return _DEFAULT_CAPABILITIES
