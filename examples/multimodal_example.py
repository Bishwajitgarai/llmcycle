import asyncio
import os
from pathlib import Path
from llmcycle import LLMCycle

async def main():
    print("=" * 60)
    print("  LLMCycle - Multimodal Attachments Example")
    print("=" * 60)

    # 1. Prepare dummy local attachment files for demonstration
    temp_dir = Path("./demo_attachments")
    temp_dir.mkdir(exist_ok=True)
    
    # Create a dummy text document
    doc_path = temp_dir / "report.txt"
    doc_path.write_text("LLMCycle project report: Phase 1 is fully complete and verified.")
    
    # Create a dummy image file (raw PNG signature bytes)
    img_path = temp_dir / "chart.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    print(f"Created temporary local attachments for demo at {temp_dir.resolve()}:")
    print(f"  - Document: {doc_path}")
    print(f"  - Image: {img_path}")

    # ─── Option A: Using Local Attachment Storage ─────────────────
    print("\n[A] Initializing LLMCycle with Local Attachment Storage...")
    client_local = LLMCycle(
        env_path=".env",
        attachment_storage="local",
        attachment_config={
            "local_dir": "./attachments_saved"  # directory to store saved copies
        }
    )

    providers = client_local.get_providers()
    if not providers:
        print("⚠️ No providers loaded in .env. Please add keys (e.g. OPENAI_API_KEYS) to run live completions.")
        print("Skipping live inference demonstration...")
        return

    provider = providers[0]
    model_to_use = f"{provider}/gpt-4o-mini"
    print(f"Using provider model: {model_to_use}")

    # Complete call with local attachments
    print(f"\n💬 Sending user query with 2 local attachments to {model_to_use}...")
    try:
        resp = await client_local.complete(
            model=model_to_use,
            prompt="Compare the findings in the attached report and the chart image. Summarize in one sentence.",
            attachments=[
                str(doc_path),  # path to text document
                str(img_path),  # path to image
            ]
        )
        print(f"✅ Response ({resp.latency_ms:.0f}ms):\n   {resp.content}")
    except Exception as e:
        print(f"❌ Completion failed: {e}")

    # ─── Option B: Using AWS S3 Attachment Storage ────────────────
    print("\n[B] Initializing LLMCycle with AWS S3 Attachment Storage...")
    print("To run this, make sure boto3 is installed and AWS credentials are set.")
    print("Example config:")
    print("  s3_bucket = 'my-llmcycle-attachments'")
    print("  s3_prefix = 'runs/multimodal/'")
    print("  s3_region = 'us-east-1'")
    
    # We show how it is constructed:
    # client_s3 = LLMCycle(
    #     attachment_storage="s3",
    #     attachment_config={
    #         "s3_bucket": "my-llmcycle-attachments",
    #         "s3_prefix": "runs/multimodal/",
    #         "s3_region": "us-east-1"
    #     }
    # )

    # Clean up temporary demo files
    try:
        doc_path.unlink()
        img_path.unlink()
        temp_dir.rmdir()
        print("\n🧹 Cleaned up temporary demo files.")
    except Exception:
        pass

    print("\n✅ Done.")

if __name__ == "__main__":
    asyncio.run(main())
