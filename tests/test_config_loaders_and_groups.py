import os
import pytest
from llmcycle.core.config_loader import EnvConfigLoader
from llmcycle.core.keys import KeyManager
from llmcycle.core.router import ModelRouter, RoutingStrategy

class TestConfigLoaders:
    def test_env_config_loader(self, monkeypatch):
        monkeypatch.setenv("CUSTOM_OPENAI_API_KEYS", "sk-123,sk-456")
        monkeypatch.setenv("CUSTOM_OPENAI_BASE_URL", "https://custom.openai")
        monkeypatch.setenv("CUSTOM_GROQ_API_KEYS", "gsk-1")
        
        loader = EnvConfigLoader(prefix="CUSTOM_", suffix="_API_KEYS")
        configs = loader.load_configs()
        
        assert "OPENAI" in configs
        assert configs["OPENAI"]["api_keys"] == "sk-123,sk-456"
        assert configs["OPENAI"]["base_url"] == "https://custom.openai"
        
        assert "GROQ" in configs
        assert configs["GROQ"]["api_keys"] == "gsk-1"
        assert "base_url" not in configs["GROQ"]

class TestGroupManager:
    def test_group_manager_crud(self):
        from llmcycle.core.groups import GroupManager
        gm = GroupManager({"tier1": ["openai/gpt-4o"]})
        
        # Test __contains__ and get
        assert "tier1" in gm
        assert gm.get("tier1") == ["openai/gpt-4o"]
        
        # Test set
        gm.set("fast", ["groq/llama3", "openai/gpt-4o-mini"])
        assert "fast" in gm
        assert len(gm.get("fast")) == 2
        
        # Test remove
        assert gm.remove("tier1") is True
        assert "tier1" not in gm
        assert gm.get("tier1") is None
        assert gm.remove("tier1") is False  # Already removed
        
        # Test list_all
        all_groups = gm.list_all()
        assert "fast" in all_groups
        assert "tier1" not in all_groups

class TestRouterGroupsAndActiveFirst:
    def test_router_groups(self):
        groups = {
            "fast": ["groq/llama3", "openai/gpt-4o-mini"]
        }
        router = ModelRouter(groups=groups, strategy=RoutingStrategy.PRIORITY)
        
        route = router.get_route("fast")
        assert len(route) == 2
        assert route[0] == ("groq", "llama3")
        assert route[1] == ("openai", "gpt-4o-mini")

    def test_active_first_routing(self):
        km = KeyManager()
        km.add_keys("groq", ["gsk-1"])
        km.add_keys("openai", ["sk-1"])
        
        # Mark groq key as permanently failed (401)
        km.report_error("groq", "gsk-1", "auth")
        
        # Groq has no active keys, OpenAI has 1 active key.
        assert not km.has_active_keys("groq")
        assert km.has_active_keys("openai")
        
        groups = {
            "fast": ["groq/llama3", "openai/gpt-4o-mini"]
        }
        
        # Priority should keep groq first
        router_priority = ModelRouter(groups=groups, key_manager=km, strategy=RoutingStrategy.PRIORITY)
        route_p = router_priority.get_route("fast")
        assert route_p[0] == ("groq", "llama3")
        
        # Active first should move openai to the top because groq is inactive
        router_active = ModelRouter(groups=groups, key_manager=km, strategy=RoutingStrategy.ACTIVE_FIRST)
        route_a = router_active.get_route("fast")
        assert route_a[0] == ("openai", "gpt-4o-mini")
        assert route_a[1] == ("groq", "llama3")
