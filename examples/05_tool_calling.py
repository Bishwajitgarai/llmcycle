"""
LLMCycle — Agentic Tool Calling
==================================
Let the LLM call your Python functions automatically.

LLMCycle runs the full tool loop for you:
  1. Sends the prompt + tool definitions to the LLM
  2. Detects which tools the LLM wants to call
  3. Executes your Python functions with the LLM's arguments
  4. Sends results back to the LLM
  5. Repeats until the LLM produces a final text response
"""
import asyncio
from llmcycle import LLMCycle

client = LLMCycle()

# ── Define your real Python functions ────────────────────────────────────────
async def get_weather(city: str) -> dict:
    """Simulate a real weather API call."""
    weather_db = {
        "London": {"temp_c": 12, "condition": "Rainy"},
        "Tokyo": {"temp_c": 24, "condition": "Sunny"},
        "New York": {"temp_c": 18, "condition": "Cloudy"},
    }
    return weather_db.get(city, {"temp_c": 20, "condition": "Unknown"})

async def tool_executor(name: str, args: dict):
    """LLMCycle calls this function when the LLM wants to use a tool."""
    if name == "get_weather":
        return await get_weather(args["city"])
    return {"error": f"Unknown tool: {name}"}

# ── OpenAI-format tool definitions ───────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a given city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "The city name, e.g. London"}
                },
                "required": ["city"]
            }
        }
    }
]

async def main():
    # LLMCycle handles the entire tool loop automatically
    response = await client.complete_with_tools(
        model="openai/gpt-4o-mini",
        prompt="What is the weather like in London and Tokyo right now?",
        tools=TOOLS,
        tool_executor=tool_executor,
        max_tool_calls=5,  # Safety guard
    )
    print(f"Final answer: {response.content}")

if __name__ == "__main__":
    asyncio.run(main())
