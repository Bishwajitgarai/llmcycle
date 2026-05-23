"""
Tests for complete_structured() — tool-calling mode (default) and
JSON-prompt fallback mode.

All tests mock the underlying complete() call — no real API calls.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel, Field
from typing import List

from llmcycle import LLMCycle
from llmcycle.schema import CompletionResponse
from llmcycle.core.errors import StructuredOutputError


# ─── Shared schema ─────────────────────────────────────────────────────────────

class City(BaseModel):
    name: str = Field(description="City name")
    population: int = Field(description="City population")
    country: str = Field(description="Country the city is in")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_client() -> LLMCycle:
    """Return a bare LLMCycle client with no env keys loaded."""
    with patch.object(LLMCycle, "_auto_load_from_env", return_value=None):
        return LLMCycle()


def _tool_response(schema_cls: type, data: dict) -> CompletionResponse:
    """Build a CompletionResponse that looks like a tool-call reply."""
    tool_name = f"extract_{schema_cls.__name__.lower()}"
    return CompletionResponse(
        id="tc-test",
        model="gpt-4o-mini",
        provider="openai",
        content="",                 # content is empty when only tool_calls returned
        tool_calls=[
            {
                "id": "call_abc",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(data),
                },
            }
        ],
    )


def _text_response(content: str) -> CompletionResponse:
    """Build a CompletionResponse with plain text content (JSON-prompt mode)."""
    return CompletionResponse(
        id="txt-test",
        model="gpt-4o-mini",
        provider="openai",
        content=content,
        tool_calls=None,
    )


# ─── Tool-calling mode (default) ──────────────────────────────────────────────

class TestToolCallingMode:
    """Tests for use_tool_format=True (default)."""

    @pytest.mark.asyncio
    async def test_tool_calling_returns_pydantic_model(self):
        client = _make_client()
        expected = {"name": "Tokyo", "population": 13960000, "country": "Japan"}
        mock_resp = _tool_response(City, expected)

        with patch.object(client, "complete", new=AsyncMock(return_value=mock_resp)):
            result = await client.complete_structured(
                "openai/gpt-4o-mini",
                prompt="Tell me about Tokyo.",
                schema=City,
                use_tool_format=True,
            )

        assert isinstance(result, City)
        assert result.name == "Tokyo"
        assert result.population == 13960000
        assert result.country == "Japan"

    @pytest.mark.asyncio
    async def test_tool_calling_is_default(self):
        """use_tool_format=True should be the default when not specified."""
        client = _make_client()
        expected = {"name": "Paris", "population": 2161000, "country": "France"}
        mock_resp = _tool_response(City, expected)

        calls = []

        async def capture_complete(model, **kwargs):
            calls.append(kwargs)
            return mock_resp

        with patch.object(client, "complete", new=capture_complete):
            result = await client.complete_structured(
                "openai/gpt-4o-mini",
                prompt="Tell me about Paris.",
                schema=City,
                # use_tool_format NOT passed — should default to True
            )

        assert isinstance(result, City)
        # Verify that tools= was passed to complete() → confirms tool mode was used
        assert "tools" in calls[0]
        assert calls[0]["tools"][0]["function"]["name"] == "extract_city"

    @pytest.mark.asyncio
    async def test_tool_format_falls_back_to_json_when_no_tool_calls(self):
        """If the provider returns no tool_calls, must fall back to JSON-prompt mode."""
        client = _make_client()
        json_text = '{"name": "Berlin", "population": 3645000, "country": "Germany"}'
        empty_tool_resp = _text_response("")      # tool attempt — no tool_calls
        json_resp = _text_response(json_text)     # fallback JSON response

        responses = iter([empty_tool_resp, json_resp])

        async def side_effect(model, **kwargs):
            return next(responses)

        with patch.object(client, "complete", new=side_effect):
            result = await client.complete_structured(
                "openai/gpt-4o-mini",
                prompt="Tell me about Berlin.",
                schema=City,
                use_tool_format=True,
            )

        assert isinstance(result, City)
        assert result.name == "Berlin"

    @pytest.mark.asyncio
    async def test_tool_calling_passes_tool_choice_required(self):
        """The tool_choice dict must force the model to call our extraction tool."""
        client = _make_client()
        expected = {"name": "Seoul", "population": 9776000, "country": "South Korea"}
        mock_resp = _tool_response(City, expected)

        captured = {}

        async def capture_complete(model, **kwargs):
            captured.update(kwargs)
            return mock_resp

        with patch.object(client, "complete", new=capture_complete):
            await client.complete_structured(
                "openai/gpt-4o-mini",
                prompt="Tell me about Seoul.",
                schema=City,
            )

        # tool_choice must be the specific-function dict, not just "auto"
        tc = captured.get("tool_choice", {})
        assert isinstance(tc, dict)
        assert tc.get("type") == "function"
        assert tc["function"]["name"] == "extract_city"


# ─── JSON-prompt fallback mode ────────────────────────────────────────────────

class TestJsonPromptMode:
    """Tests for use_tool_format=False (legacy mode)."""

    @pytest.mark.asyncio
    async def test_json_prompt_parses_plain_json(self):
        client = _make_client()
        json_text = '{"name": "Mumbai", "population": 12478447, "country": "India"}'
        mock_resp = _text_response(json_text)

        with patch.object(client, "complete", new=AsyncMock(return_value=mock_resp)):
            result = await client.complete_structured(
                "openai/gpt-4o-mini",
                prompt="Tell me about Mumbai.",
                schema=City,
                use_tool_format=False,
            )

        assert isinstance(result, City)
        assert result.name == "Mumbai"

    @pytest.mark.asyncio
    async def test_json_prompt_strips_markdown_fences(self):
        client = _make_client()
        fenced = '```json\n{"name": "Lagos", "population": 15000000, "country": "Nigeria"}\n```'
        mock_resp = _text_response(fenced)

        with patch.object(client, "complete", new=AsyncMock(return_value=mock_resp)):
            result = await client.complete_structured(
                "openai/gpt-4o-mini",
                prompt="Tell me about Lagos.",
                schema=City,
                use_tool_format=False,
            )

        assert isinstance(result, City)
        assert result.name == "Lagos"

    @pytest.mark.asyncio
    async def test_json_prompt_retries_on_parse_failure(self):
        """Should retry with self-correction feedback on bad JSON, then succeed."""
        client = _make_client()
        bad = "Sorry, I cannot provide that information."
        good = '{"name": "Cairo", "population": 10100000, "country": "Egypt"}'
        responses = iter([_text_response(bad), _text_response(good)])

        async def side_effect(model, **kwargs):
            return next(responses)

        with patch.object(client, "complete", new=side_effect):
            result = await client.complete_structured(
                "openai/gpt-4o-mini",
                prompt="Tell me about Cairo.",
                schema=City,
                use_tool_format=False,
                max_retries_parse=1,
            )

        assert isinstance(result, City)
        assert result.name == "Cairo"

    @pytest.mark.asyncio
    async def test_json_prompt_raises_structured_output_error_after_all_retries(self):
        """Should raise StructuredOutputError when all parse retries fail."""
        client = _make_client()
        bad_resp = _text_response("not valid json at all!")

        with patch.object(client, "complete", new=AsyncMock(return_value=bad_resp)):
            with pytest.raises(StructuredOutputError):
                await client.complete_structured(
                    "openai/gpt-4o-mini",
                    prompt="Tell me about nowhere.",
                    schema=City,
                    use_tool_format=False,
                    max_retries_parse=1,
                )

    @pytest.mark.asyncio
    async def test_json_prompt_no_tools_sent(self):
        """In JSON-prompt mode, complete() must NOT be called with tools=."""
        client = _make_client()
        mock_resp = _text_response('{"name": "Nairobi", "population": 4397073, "country": "Kenya"}')

        captured = {}

        async def capture_complete(model, **kwargs):
            captured.update(kwargs)
            return mock_resp

        with patch.object(client, "complete", new=capture_complete):
            await client.complete_structured(
                "openai/gpt-4o-mini",
                prompt="Tell me about Nairobi.",
                schema=City,
                use_tool_format=False,
            )

        assert "tools" not in captured


# ─── Edge cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_raises_if_schema_missing(self):
        client = _make_client()
        with pytest.raises(ValueError, match="schema="):
            await client.complete_structured(
                "openai/gpt-4o-mini",
                prompt="Hello.",
                schema=None,
            )

    @pytest.mark.asyncio
    async def test_raises_if_neither_prompt_nor_messages(self):
        client = _make_client()
        with pytest.raises(ValueError, match="prompt.*messages"):
            await client.complete_structured(
                "openai/gpt-4o-mini",
                schema=City,
            )

    @pytest.mark.asyncio
    async def test_messages_list_is_accepted(self):
        client = _make_client()
        expected = {"name": "Dhaka", "population": 21006000, "country": "Bangladesh"}
        mock_resp = _tool_response(City, expected)

        with patch.object(client, "complete", new=AsyncMock(return_value=mock_resp)):
            result = await client.complete_structured(
                "openai/gpt-4o-mini",
                messages=[{"role": "user", "content": "Tell me about Dhaka."}],
                schema=City,
            )

        assert isinstance(result, City)
        assert result.name == "Dhaka"
