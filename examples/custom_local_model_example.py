import asyncio
import os
from llmcycle import LLMCycle

async def main():
    print("🏠 Initializing LLMCycle for Local/Custom Models...")
    
    # You can point LLMCycle to a local Ollama or vLLM instance easily!
    # Set the base URL in the environment before init, or pass a custom `ConfigLoader`.
    
    os.environ["OPENAI_BASE_URL"] = "http://localhost:11434/v1"
    os.environ["OPENAI_API_KEYS"] = "ollama"  # Ollama doesn't require a real key
    
    # Initialize the client. It will automatically load the environment variables.
    client = LLMCycle()

    print("\n💬 Querying local Llama 3 model via Ollama compatibility layer...")
    try:
        # Request your local custom model!
        response = await client.complete("openai/llama3", prompt="Why is open-source AI important? Keep it brief.")
        print(f"\n✅ Success! Local Model Response:")
        print(response.content)
        
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        print("Note: Make sure you have Ollama running with the 'llama3' model downloaded for this example.")

if __name__ == "__main__":
    asyncio.run(main())
