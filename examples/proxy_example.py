import asyncio
import os
from llmcycle import LLMCycle

async def main():
    print("🚀 Initializing LLMCycle with Proxy...")
    
    # You can pass a proxy URL directly when initializing the client
    # This proxy will be used for all HTTP requests to LLM providers
    client = LLMCycle(
        proxy="http://your.proxy.server:8080" # Replace with your actual proxy URL
    )
    
    print("\n💬 Requesting completion via proxy...")
    try:
        response = await client.complete(
            model="openai/gpt-4o-mini", 
            prompt="Hello! Did this request go through the proxy?"
        )
        print(f"\n✅ Success! Answered by: {response.model}")
        print(f"Response: {response.content}")
        
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        print("Note: If the proxy is not reachable, you will see a connection error here.")

if __name__ == "__main__":
    # Ensure you have your API keys set in your environment
    # os.environ["OPENAI_API_KEY"] = "your-api-key"
    asyncio.run(main())
