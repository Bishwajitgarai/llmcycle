import asyncio
import sys
import pytest
from dotenv import load_dotenv
from llmcycle import LLMCycle
from llmcycle.core.prompts import PromptRegistry, PromptVersion

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

async def main():
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}🚀 RUNNING TEST: Prompt Registry & Template Versioning{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    # 1. Instantiate PromptRegistry independently to test its CRUD logic
    print("Initializing standalone PromptRegistry...")
    registry = PromptRegistry()
    
    # 2. Register templates with v1 and v2 versioning
    registry.set("greeting", "Hello {{name}}, welcome to {{place}}!", version="v1", description="Simple greeting")
    registry.set("greeting", "Hey {{name}}, enjoy your stay at {{place}}!", version="v2", description="Casual greeting")
    
    # Assert versions are saved
    v1 = registry.get("greeting", "v1")
    v2 = registry.get("greeting", "v2")
    latest = registry.get("greeting")
    
    assert v1.template == "Hello {{name}}, welcome to {{place}}!"
    assert v2.template == "Hey {{name}}, enjoy your stay at {{place}}!"
    assert latest.version == "v2"  # Last registered wins as latest
    
    print(f"{BOLD}{GREEN}✓ PASS: Templates registered and fetched successfully!{RESET}")
    
    # 3. Test variables identification
    assert "name" in v1.variables()
    assert "place" in v1.variables()
    print(f"{BOLD}{GREEN}✓ PASS: Variables parsed correctly: {v1.variables()}{RESET}")
    
    # 4. Test rendering templates
    rendered_v1 = registry.render("greeting", version="v1", name="Alice", place="Wonderland")
    rendered_v2 = registry.render("greeting", version="v2", name="Bob", place="Atlantis")
    rendered_latest = registry.render("greeting", name="Charlie", place="Valhalla")
    
    assert rendered_v1 == "Hello Alice, welcome to Wonderland!"
    assert rendered_v2 == "Hey Bob, enjoy your stay at Atlantis!"
    assert rendered_latest == "Hey Charlie, enjoy your stay at Valhalla!"
    print(f"{BOLD}{GREEN}✓ PASS: Interpolations rendered correctly!{RESET}")
    
    # 5. Verify error when missing variable
    try:
        registry.render("greeting", name="Alice")  # missing place
        raise AssertionError("Rendering should have failed with KeyError due to missing variable.")
    except KeyError as e:
        print(f"{BOLD}{GREEN}✓ PASS: Caught expected KeyError for missing variable: {e}{RESET}")
        
    # 6. Test listing prompts
    all_prompts = registry.list()
    assert len(all_prompts) == 2
    print(f"{BOLD}{GREEN}✓ PASS: Prompt listing works: {len(all_prompts)} items.{RESET}")
    
    # 7. Test deleting prompt versions
    deleted_count = registry.delete("greeting", version="v1")
    assert deleted_count == 1
    assert len(registry.list()) == 1
    assert registry.get("greeting").version == "v2"
    
    # Test deleting remaining prompt entirely
    deleted_all = registry.delete("greeting")
    assert deleted_all == 1
    assert len(registry.list()) == 0
    print(f"{BOLD}{GREEN}✓ PASS: Delete operations worked correctly!{RESET}")
    
    # 8. Test integrated PromptRegistry on LLMCycle client
    print("\nVerifying PromptRegistry on client.prompts...")
    client = LLMCycle()
    assert isinstance(client.prompts, PromptRegistry)
    
    client.prompts.set("weather", "How is the weather in {{city}}?")
    prompt_rendered = client.prompts.render("weather", city="London")
    assert prompt_rendered == "How is the weather in London?"
    
    print(f"{BOLD}{GREEN}✓ PASS: client.prompts is fully integrated and functional!{RESET}")

@pytest.mark.asyncio
async def test_prompt_registry():
    await main()

if __name__ == "__main__":
    asyncio.run(main())
