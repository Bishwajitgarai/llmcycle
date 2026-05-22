import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from llmcycle.schema import CompletionRequest, CompletionResponse, Message


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_openai_compatible_provider_get_models_data_format(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__aenter__.return_value = mock_client

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {"id": "gpt-4o-mini"},
            {"id": "gpt-4o"},
        ]
    }
    mock_client.get = AsyncMock(return_value=mock_resp)

    from llmcycle.providers.openai_compatible import OpenAICompatibleProvider
    provider = OpenAICompatibleProvider(base_url="https://api.openai.com/v1", provider_name="openai")

    # Call get_models (it will sort them inside the provider)
    models = await provider.get_models("sk-test-key")
    assert models == ["gpt-4o", "gpt-4o-mini"]
    mock_client.get.assert_called_once_with(
        "https://api.openai.com/v1/models",
        headers={"Authorization": "Bearer sk-test-key", "Content-Type": "application/json"},
    )


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_openai_compatible_provider_get_models_models_format(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__aenter__.return_value = mock_client

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [
            "claude-3-opus",
            "claude-3-sonnet",
        ]
    }
    mock_client.get = AsyncMock(return_value=mock_resp)

    from llmcycle.providers.openai_compatible import OpenAICompatibleProvider
    provider = OpenAICompatibleProvider(base_url="https://api.anthropic.com/v1", provider_name="anthropic")

    models = await provider.get_models("sk-anthropic")
    assert models == ["claude-3-opus", "claude-3-sonnet"]


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_openai_compatible_provider_get_models_failed(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__aenter__.return_value = mock_client

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client.get = AsyncMock(return_value=mock_resp)

    from llmcycle.providers.openai_compatible import OpenAICompatibleProvider
    provider = OpenAICompatibleProvider(base_url="https://api.groq.com/openai/v1", provider_name="groq")

    models = await provider.get_models("gsk-test")
    assert models == []


@pytest.mark.asyncio
async def test_llmcycle_get_models_and_get_all_live_models():
    # Patch environment variables to trigger loaded providers
    with patch.dict(os.environ, {"OPENAI_API_KEYS": "sk-openai", "GROQ_API_KEYS": "gsk-groq"}):
        from llmcycle import LLMCycle
        client = LLMCycle()

        assert "openai" in client._providers
        assert "groq" in client._providers

        # Mock the get_models call on provider instances
        client._providers["openai"].get_models = AsyncMock(return_value=["gpt-4o", "gpt-4o-mini"])
        client._providers["groq"].get_models = AsyncMock(return_value=["llama3-70b", "llama3-8b"])

        # Test client.get_models for a specific provider
        openai_models = await client.get_models("openai")
        assert openai_models == ["gpt-4o", "gpt-4o-mini"]

        # Test parallel fetching of all live models
        all_models = await client.get_all_live_models()
        assert all_models["openai"] == ["gpt-4o", "gpt-4o-mini"]
        assert all_models["groq"] == ["llama3-70b", "llama3-8b"]


@pytest.mark.asyncio
async def test_llmcycle_get_models_no_key():
    with patch.dict(os.environ, {"OPENAI_API_KEYS": ""}):
        from llmcycle import LLMCycle
        client = LLMCycle()
        
        # Test client.get_models for nonexistent/unloaded provider
        models = await client.get_models("openai")
        assert models == []


def test_cli_models_command_all_providers():
    from llmcycle.cli import cmd_models

    class Args:
        provider = None

    args = Args()

    with patch("llmcycle.LLMCycle") as mock_llmcycle_class:
        mock_client = MagicMock()
        mock_llmcycle_class.return_value = mock_client
        mock_client.get_providers.return_value = ["openai", "groq"]

        mock_client.get_all_live_models = AsyncMock(return_value={
            "openai": ["gpt-4o", "gpt-4o-mini"],
            "groq": ["llama3-70b"],
        })

        with patch("sys.stdout") as mock_stdout:
            cmd_models(args)

        mock_client.get_all_live_models.assert_called_once()


def test_cli_models_command_single_provider():
    from llmcycle.cli import cmd_models

    class Args:
        provider = "openai"

    args = Args()

    with patch("llmcycle.LLMCycle") as mock_llmcycle_class:
        mock_client = MagicMock()
        mock_llmcycle_class.return_value = mock_client
        mock_client.get_providers.return_value = ["openai", "groq"]

        mock_client.get_models = AsyncMock(return_value=["gpt-4o", "gpt-4o-mini"])

        with patch("sys.stdout") as mock_stdout:
            cmd_models(args)

        mock_client.get_models.assert_called_once_with("openai")


def test_cli_models_command_unloaded_provider():
    from llmcycle.cli import cmd_models

    class Args:
        provider = "nonexistent"

    args = Args()

    with patch("llmcycle.LLMCycle") as mock_llmcycle_class:
        mock_client = MagicMock()
        mock_llmcycle_class.return_value = mock_client
        mock_client.get_providers.return_value = ["openai"]

        with patch("sys.stdout") as mock_stdout:
            cmd_models(args)

        mock_client.get_models.assert_not_called()
