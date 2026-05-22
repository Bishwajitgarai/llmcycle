import asyncio
from llmcycle import LLMCycle

async def main():
    print("Initializing LLMCycle (auto-loading from .env)...")
    # You can provide fallbacks, so if deepseek fails, it falls back to openai
    client = LLMCycle(
        env_path=".env",
        custom_fallbacks={
            "deepseek": ["openai"]
        }
    )
    
    # 1. Get Available Providers automatically loaded from env
    providers = client.get_available_providers()
    print(f"\nProviders automatically loaded: {providers}")
    
    # 2. Get Models for a specific provider (This will make a network request to the base URL)
    # Note: Since the keys in our .env are fake, this might fail unless we catch it
    if "deepseek" in providers:
        print("\nFetching models for DeepSeek using loaded keys...")
        models = await client.get_provider_models("deepseek")
        if models:
            print(f"DeepSeek Models: {models[:3]} ...")
        else:
            print("Failed to fetch models (Fake API key used in .env)")

if __name__ == "__main__":
    asyncio.run(main())
