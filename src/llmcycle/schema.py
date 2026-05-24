"""
Production schema models with Pydantic v2.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
import time


class Message(BaseModel):
    role: str
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None



class CompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[Union[str, List[str]]] = None
    tools: Optional[List[Dict[str, Any]]] = None       # OpenAI tool definitions
    tool_choice: Optional[Any] = None                  # "auto" | "none" | {type, function}
    extra: Optional[Dict[str, Any]] = None

    def to_api_dict(self) -> dict:
        """Serialize for sending to OpenAI-compatible API."""
        d = self.model_dump(exclude_none=True, exclude={"extra"})
        d["messages"] = [m.model_dump() for m in self.messages]
        if self.extra:
            d.update(self.extra)
        return d


class ToolParameter(BaseModel):
    """A single parameter definition for a Tool."""
    type: str = "string"
    description: str = ""
    enum: Optional[List[str]] = None


class Tool(BaseModel):
    """
    A clean, Pythonic way to define an LLM tool (function).

    Instead of writing raw OpenAI-format dicts, use this class:

        from llmcycle import Tool, ToolParameter

        weather_tool = Tool(
            name="get_weather",
            description="Get the current weather for a city.",
            parameters={
                "city": ToolParameter(type="string", description="City name, e.g. London"),
                "unit": ToolParameter(type="string", description="Unit", enum=["celsius", "fahrenheit"]),
            },
            required=["city"],
        )

        response = await client.complete_with_tools(
            model="openai/gpt-4o-mini",
            prompt="What is the weather in London?",
            tools=[weather_tool],     # ← pass Tool objects directly
            tool_executor=my_handler,
        )
    """
    name: str
    description: str = ""
    parameters: Dict[str, ToolParameter] = Field(default_factory=dict)
    required: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to OpenAI-compatible tool definition dict."""
        props = {}
        for param_name, param in self.parameters.items():
            prop: Dict[str, Any] = {"type": param.type, "description": param.description}
            if param.enum:
                prop["enum"] = param.enum
            props[param_name] = prop

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": self.required or list(self.parameters.keys()),
                },
            },
        }


class CompletionResponse(BaseModel):
    id: str
    model: str
    provider: str
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: Optional[float] = None
    created_at: float = Field(default_factory=time.time)
    tool_calls: Optional[List[Any]] = None  # Populated when model returns tool calls


class StreamChunk(BaseModel):
    content: str
    model: str
    provider: str
    done: bool = False
