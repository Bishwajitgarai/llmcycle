import sys
from unittest.mock import MagicMock, patch

# Mock boto3 and botocore in sys.modules before any imports
class MockNoCredentialsError(Exception):
    pass

sys.modules["boto3"] = MagicMock()
mock_botocore = MagicMock()
mock_botocore_exceptions = MagicMock()
mock_botocore_exceptions.NoCredentialsError = MockNoCredentialsError
sys.modules["botocore"] = mock_botocore
sys.modules["botocore.exceptions"] = mock_botocore_exceptions

import pytest
import os
import shutil
from pathlib import Path
from llmcycle.core.attachments import AttachmentManager


@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "test_attachments"
    d.mkdir()
    yield d
    if d.exists():
        shutil.rmtree(d)


def test_local_attachment_manager_init(temp_dir):
    manager = AttachmentManager(
        storage_type="local",
        local_dir=str(temp_dir)
    )
    assert manager.storage_type == "local"
    assert manager.local_dir == temp_dir.resolve()
    assert temp_dir.exists()


def test_local_attachment_upload_path(temp_dir):
    manager = AttachmentManager(
        storage_type="local",
        local_dir=str(temp_dir)
    )

    # Create dummy text file
    dummy_file = temp_dir / "hello.txt"
    dummy_file.write_text("Hello World!")

    info = manager.upload_attachment(str(dummy_file))
    assert info["storage_type"] == "local"
    assert info["media_type"] == "text/plain"
    assert "data:text/plain;base64," in info["base64_url"]
    
    # Verify file saved under a unique filename
    saved_path = Path(info["storage_path"])
    assert saved_path.exists()
    assert saved_path.parent == temp_dir.resolve()
    assert saved_path.read_text() == "Hello World!"


def test_local_attachment_upload_bytes(temp_dir):
    manager = AttachmentManager(
        storage_type="local",
        local_dir=str(temp_dir)
    )

    raw_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    info = manager.upload_attachment(
        raw_data,
        filename="image.png",
        media_type="image/png"
    )
    assert info["storage_type"] == "local"
    assert info["media_type"] == "image/png"
    assert "data:image/png;base64," in info["base64_url"]
    assert Path(info["storage_path"]).exists()
    assert Path(info["storage_path"]).read_bytes() == raw_data


def test_local_attachment_format_message(temp_dir):
    manager = AttachmentManager(
        storage_type="local",
        local_dir=str(temp_dir)
    )

    dummy_image = temp_dir / "logo.jpg"
    dummy_image.write_bytes(b"mockjpegdata")

    parts = manager.format_message_content(
        prompt="Explain this logo:",
        attachments=[str(dummy_image)]
    )

    assert len(parts) == 2
    assert parts[0] == {"type": "text", "text": "Explain this logo:"}
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


@patch("boto3.client")
def test_s3_attachment_upload(mock_boto_client, temp_dir):
    # Mock S3 Client interactions
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3
    mock_s3.generate_presigned_url.return_value = "https://mock-bucket.s3.amazonaws.com/attachments/unique.pdf?temp-sig"

    manager = AttachmentManager(
        storage_type="s3",
        s3_bucket="my-mock-bucket",
        s3_prefix="tests-folder/",
        s3_region="us-west-2"
    )

    dummy_pdf = temp_dir / "doc.pdf"
    dummy_pdf.write_bytes(b"mockpdfcontent")

    info = manager.upload_attachment(str(dummy_pdf))

    assert info["storage_type"] == "s3"
    assert info["media_type"] == "application/pdf"
    assert info["url"] == "https://mock-bucket.s3.amazonaws.com/attachments/unique.pdf?temp-sig"
    assert info["storage_path"].startswith("s3://my-mock-bucket/tests-folder/")

    # Check put_object was called
    mock_s3.put_object.assert_called_once()
    kwargs = mock_s3.put_object.call_args[1]
    assert kwargs["Bucket"] == "my-mock-bucket"
    assert kwargs["ContentType"] == "application/pdf"
    assert kwargs["Body"] == b"mockpdfcontent"
