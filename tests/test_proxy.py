import pytest
from fastapi.testclient import TestClient
from llmcycle.ui.app import app
from llmcycle import LLMCycle

def test_proxy_models_endpoint():
    client = TestClient(app)
    # Ingress proxy models list endpoint
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert "object" in data
    assert data["object"] == "list"
    assert "data" in data
    assert len(data["data"]) > 0
    
    # Ensure format conforms to standard OpenAI spec
    first_model = data["data"][0]
    assert "id" in first_model
    assert "owned_by" in first_model

def test_proxy_chat_completions_bad_request():
    client = TestClient(app)
    # A request missing the 'model' field must return 400 Bad Request
    response = client.post("/v1/chat/completions", json={})
    assert response.status_code == 400

def test_egress_proxy_initialization():
    # Verify that explicit proxy settings propagate correctly to the LLMCycle client
    client = LLMCycle(proxy="http://127.0.0.1:8080")
    assert client.proxy == "http://127.0.0.1:8080"
