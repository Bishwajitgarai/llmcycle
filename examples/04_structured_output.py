"""
LLMCycle — Structured Output (Pydantic)
=========================================
Force the LLM to return data that perfectly matches a Pydantic model.
No parsing, no regex, no markdown stripping. Just a validated Python object.

Uses the OpenAI tool-calling API under the hood for maximum reliability.
Falls back to JSON-prompt mode automatically for providers that don't support it.
"""
import asyncio
from typing import List
from pydantic import BaseModel, Field
from llmcycle import LLMCycle

client = LLMCycle()

# Define your expected output schema
class JobPosting(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    required_skills: List[str] = Field(description="List of required technical skills")
    experience_years: int = Field(description="Minimum years of experience required")
    remote: bool = Field(description="Whether the role is remote-friendly")

async def main():
    raw_text = """
    Senior Python Engineer at TechCorp. We are looking for 5+ years of experience
    in Python, FastAPI, Kubernetes, and PostgreSQL. The role is fully remote.
    """

    # complete_structured returns a validated Pydantic object directly
    result: JobPosting = await client.complete_structured(
        model="openai/gpt-4o-mini",
        prompt=f"Extract the job posting details from this text: {raw_text}",
        schema=JobPosting,
    )

    print(f"Title: {result.title}")
    print(f"Company: {result.company}")
    print(f"Skills: {', '.join(result.required_skills)}")
    print(f"Experience: {result.experience_years}+ years")
    print(f"Remote: {result.remote}")

if __name__ == "__main__":
    asyncio.run(main())
