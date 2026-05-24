import asyncio
import sys
import os
from dotenv import load_dotenv
from llmcycle import LLMCycle
from llmcycle.core.attachments import AttachmentManager

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


async def main():
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}🚀 RUNNING TEST: Local Attachment Storage & Multimodal payloads{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    # 1. Initialize AttachmentManager locally
    print("Setting up local AttachmentManager...")
    manager = AttachmentManager(storage_type="local", local_dir="./attachments_test_dir")
    
    # 2. Test uploading bytes as mock image
    mock_image_bytes = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;" # 1x1 transparent GIF
    
    print("\nUploading mock image attachment bytes...")
    info = manager.upload_attachment(
        file_source=mock_image_bytes,
        filename="mock_pixel.gif",
        media_type="image/gif"
    )
    print("Uploaded attachment info:")
    print(f"  - Storage path: {info['storage_path']}")
    print(f"  - Resolved MIME: {info['media_type']}")
    print(f"  - Base64 URL: {info['base64_url'][:40]}...")
    
    assert info["storage_type"] == "local"
    assert info["media_type"] == "image/gif"
    print(f"{BOLD}{GREEN}✓ PASS: Local upload and mime mapping completed successfully!{RESET}")

    # 3. Test formatting multimodal message contents
    print("\nFormatting multimodal user message with prompt and attachments...")
    content = manager.format_message_content(
        prompt="Describe this uploaded picture.",
        attachments=[info["storage_path"]]
    )
    print("Formatted message content blocks:")
    for idx, block in enumerate(content):
        if block["type"] == "text":
            print(f"  [{idx}]: type='text' | text='{block['text']}'")
        elif block["type"] == "image_url":
            print(f"  [{idx}]: type='image_url' | url='{block['image_url']['url'][:40]}...'")

    assert len(content) == 2
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    print(f"{BOLD}{GREEN}✓ PASS: Multimodal payload formatted correctly!{RESET}")

    # Clean up test directories
    if os.path.exists("./attachments_test_dir"):
        import shutil
        shutil.rmtree("./attachments_test_dir")

import pytest
@pytest.mark.asyncio
async def test_attachment_storage():
    await main()

if __name__ == "__main__":
    import os
    asyncio.run(main())

