import asyncio
from llmcycle import LLMCycle
from llmcycle.core.semantic import SemanticRouter

async def main():
    print("🧠 Initializing LLMCycle with Semantic Intent Routing...")
    
    # 1. Setup the semantic router
    s_router = SemanticRouter()
    
    # Define route intents based on user text semantics
    s_router.add_route("coding_queries", ["Write a python script", "How do I fix this bug?", "Generate SQL for this"])
    s_router.add_route("casual_chat", ["Hello how are you?", "Tell me a joke", "What's up?"])
    
    # 2. Attach the semantic router to the client
    client = LLMCycle()
    client.semantic_router = s_router

    # Map semantic intents to specific models or groups!
    INTENT_MODEL_MAP = {
        "coding_queries": "openai/gpt-4o",         # Use the smart model for coding
        "casual_chat": "openai/gpt-4o-mini",       # Use the cheaper/faster model for chat
        None: "groq/llama-3.1-8b"                  # Fallback model
    }

    queries = [
        "Hey! Give me a quick joke about programmers.",
        "Can you write an asyncio implementation of a TCP server in Python?"
    ]

    for q in queries:
        print(f"\n💬 Query: '{q}'")
        
        # Determine the intent of the prompt using semantic similarity
        intent = s_router.get_intent(q)
        print(f"🎯 Detected Intent: {intent}")
        
        target_model = INTENT_MODEL_MAP.get(intent, INTENT_MODEL_MAP[None])
        print(f"🔀 Routing to model: {target_model}")
        
        try:
            response = await client.complete(model=target_model, prompt=q)
            print(f"🤖 Response: {response.content}")
        except Exception as e:
            print(f"⚠️  Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
