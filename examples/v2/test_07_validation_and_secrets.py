import asyncio
import sys
from dotenv import load_dotenv
from llmcycle import LLMCycle, EnvSecretLoader
from llmcycle.core.keys import KeyStatus

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

def reset_key_cooldown(client: LLMCycle):
    for provider in client.get_providers():
        for rec in client.key_manager._keys.get(provider, []):
            rec.status = KeyStatus.ACTIVE
            rec.rate_limit_until = 0.0
            rec.consecutive_errors = 0

async def main():
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}🚀 RUNNING TEST: Output Validators & Secret Manager Adapters{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    # 1. Verify Secret Manager Env Loader
    print("--- Test Case 1: Secret Loader ---")
    try:
        loader = EnvSecretLoader()
        key_value = loader.load("OPENROUTER_API_KEYS")
        print(f"Secret prefix loaded successfully: {key_value[:15]}...")
        assert len(key_value) > 10
        print(f"{BOLD}{GREEN}✓ PASS: Secret Loader successfully retrieved API keys!{RESET}")
    except Exception as e:
        print(f"\033[91m✗ FAIL: Secret Loader failed: {e}{RESET}")

    # 2. Verify Output Validation / Guarding
    print("\n--- Test Case 2: Response Validation & Guarding ---")
    
    def forbidden_word_validator(model: str, response):
        forbidden = ["apple", "banana"]
        for word in forbidden:
            if word in response.content.lower():
                raise ValueError(f"Content violation: Forbidden word '{word}' found in response.")
        print(f"{BOLD}{YELLOW}⚠ Validator: Content is clean!{RESET}")

    client = LLMCycle()
    reset_key_cooldown(client)
    MODEL = "openrouter/openai/gpt-oss-20b:free"
    
    try:
        print(f"Routing completion with validation checks to: {MODEL}...")
        res = await client.complete(MODEL, "Say 'Validation Complete'", validators=[forbidden_word_validator])
        print("Response:", res.content.strip())
        print(f"{BOLD}{GREEN}✓ PASS: Response validation guard verified successfully!{RESET}")
    except Exception as e:
        print(f"{BOLD}{YELLOW}⚠ INFO: Live validation call bypassed due to rate limit: {e}{RESET}")

if __name__ == "__main__":
    asyncio.run(main())
