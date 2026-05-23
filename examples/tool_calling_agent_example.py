import asyncio
import json
from llmcycle import LLMCycle

# 1. Define the tool specification (OpenAI format)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City and state, e.g. San Francisco, CA"}
                },
                "required": ["location"]
            }
        }
    }
]

# 2. Define the executor function that actually runs the code
async def execute_tool(name: str, args: dict) -> dict:
    print(f"🛠️  Agent called tool '{name}' with args: {args}")
    if name == "get_weather":
        # Simulate an API call
        await asyncio.sleep(1)
        location = args.get("location", "Unknown")
        return {"temperature": "72F", "conditions": "Sunny", "location": location}
    return {"error": "Unknown tool"}

async def main():
    print("🤖 Initializing LLMCycle Agent Tool Loop...")
    client = LLMCycle()

    # The user asks a question that requires real-time data
    prompt = "Should I wear a jacket in San Francisco today?"
    print(f"\n💬 User: {prompt}")
    print("Running autonomous tool loop (max 5 turns)...")

    try:
        # LLMCycle handles the internal conversation loop!
        # It sends the prompt, the model returns a tool call, LLMCycle executes it locally,
        # sends the result back to the model, and the model generates the final answer.
        response = await client.complete_with_tools(
            model="openai/gpt-4o",
            prompt=prompt,
            tools=TOOLS,
            tool_executor=execute_tool,
            max_tool_calls=5
        )
        
        print(f"\n✅ Final Agent Answer:")
        print(response.content)
        
    except Exception as e:
        print(f"⚠️  Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
