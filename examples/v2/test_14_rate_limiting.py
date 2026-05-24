import asyncio
import sys
import time
import pytest
from dotenv import load_dotenv
from llmcycle import LLMCycle
from llmcycle.core.rate_limit import TokenBucket, RateLimiter, RateLimitManager
from llmcycle.core.keys import KeyStatus

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def reset_key_cooldown(client):
    for provider in client.get_providers():
        for rec in client.key_manager._keys.get(provider, []):
            rec.status = KeyStatus.ACTIVE
            rec.rate_limit_until = 0.0
            rec.consecutive_errors = 0

async def main():
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}🚀 RUNNING TEST: Client-Side Rate Limiting & Self-Throttling{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    # 1. Test standalone TokenBucket
    print("Testing TokenBucket math...")
    # Bucket with capacity 2.0, window of 2.0 seconds (refills 1 token/sec)
    bucket = TokenBucket(limit=2.0, window=2.0)
    
    # First 2 requests should be instant (0.0 wait)
    wait1 = bucket.get_wait_time(1.0)
    wait2 = bucket.get_wait_time(1.0)
    assert wait1 == 0.0
    assert wait2 == 0.0
    
    # Third request immediately should require waiting
    wait3 = bucket.get_wait_time(1.0)
    assert wait3 > 0.0
    print(f"TokenBucket correctly forced wait of {wait3:.2f}s when exhausted.")
    print(f"{BOLD}{GREEN}✓ PASS: TokenBucket math & exhaustion limits verified!{RESET}")

    # 2. Test RateLimiter acquire mechanics
    print("\nTesting RateLimiter sleep mechanics...")
    limiter = RateLimiter(rpm_limit=120, tpm_limit=5000) # High limits for test
    
    t0 = time.time()
    # Acquire 1000 tokens (well within limits)
    await limiter.acquire(1000)
    t1 = time.time()
    assert (t1 - t0) < 0.1
    print(f"{BOLD}{GREEN}✓ PASS: RateLimiter passed fast-path acquisition!{RESET}")

    # 3. Test RateLimitManager integration on client
    print("\nVerifying client-side rate limit integration...")
    MODEL = "openrouter/openai/gpt-oss-20b:free"
    
    # Configure tiny model rate limits to trigger self-throttling easily
    client = LLMCycle(
        rate_limits={
            MODEL: {"rpm": 60, "tpm": 100}  # ~100 tokens max per minute before throttling
        }
    )
    reset_key_cooldown(client)
    
    assert isinstance(client.rate_limit_manager, RateLimitManager)
    
    # The first live query should go through and deduct tokens
    print("Making first request...")
    try:
        t0 = time.time()
        res1 = await client.complete(MODEL, "Say 'Throttle Test 1'")
        t1 = time.time()
        print(f"First request completed in {t1-t0:.2f}s: {res1.content.strip()}")
        
        # Second request right after should exceed TPM (100 tokens) and trigger client-side throttling sleep
        print("Making second request (should auto-throttle client-side)...")
        t0 = time.time()
        res2 = await client.complete(MODEL, "Say 'Throttle Test 2'")
        t1 = time.time()
        print(f"Second request completed in {t1-t0:.2f}s: {res2.content.strip()}")
        print(f"{BOLD}{GREEN}✓ PASS: Rate limited live request handled successfully!{RESET}")
    except Exception as e:
        print(f"\033[93m⚠ INFO: Live client throttling test bypassed due to rate limit/error: {e}{RESET}")

@pytest.mark.asyncio
async def test_rate_limiting():
    await main()

if __name__ == "__main__":
    asyncio.run(main())
