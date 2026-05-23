import asyncio
from pydantic import BaseModel, Field
from llmcycle import LLMCycle

class WeatherReport(BaseModel):
    city: str = Field(..., description="The name of the city")
    temperature_c: float = Field(..., description="Current temperature in Celsius")
    conditions: str = Field(..., description="Short description of the weather conditions")
    is_raining: bool = Field(..., description="True if it is raining")

async def main():
    print("🧩 Initializing LLMCycle for Structured Output...")
    client = LLMCycle()

    print("\n📝 Requesting a strictly typed WeatherReport object...")
    
    # complete_structured automatically uses OpenAI tool-calling under the hood
    # to enforce perfect JSON adherence matching the Pydantic model.
    try:
        report: WeatherReport = await client.complete_structured(
            model="openai/gpt-4o-mini",
            prompt="It is currently 15 degrees and pouring rain in London today.",
            schema=WeatherReport
        )
        
        print("\n✅ Success! Received parsed Pydantic object:")
        print(f"City:        {report.city}")
        print(f"Temperature: {report.temperature_c}°C")
        print(f"Conditions:  {report.conditions}")
        print(f"Raining?:    {report.is_raining}")
        
    except Exception as e:
        print(f"⚠️  Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
