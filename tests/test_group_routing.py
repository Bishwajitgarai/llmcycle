import pytest
import asyncio
from llmcycle.client import LLMCycle
from llmcycle.core.router import RoutingStrategy

@pytest.mark.asyncio
async def test_client_complete_with_group_only():
    client = LLMCycle(groups={"my_test_group": ["openai/gpt-4o-mini"]})
    
    # We should be able to call complete with just group
    # Since we are not actually hitting the network, we can use a mock or just expect it to attempt the call
    try:
        await client.complete(group="my_test_group", prompt="Hello")
    except Exception as e:
        # It might fail with auth/network error, but it shouldn't fail with routing/validation errors
        assert "Must provide" not in str(e)
        assert "No route" not in str(e)

@pytest.mark.asyncio
async def test_client_stream_with_group_only():
    client = LLMCycle(groups={"my_test_group": ["openai/gpt-4o-mini"]})
    
    try:
        async for chunk in client.stream(group="my_test_group", prompt="Hello"):
            pass
    except Exception as e:
        assert "Must provide" not in str(e)
        assert "No route" not in str(e)
