"""
Integration tests for upload flow.
Tests require a valid API key and make real network calls.
"""
import os
import pytest
import tempfile
from pathlib import Path
from ez1 import EasyOneClient
from tests.helpers.config import config


@pytest.mark.integration
@pytest.mark.network
class TestUploadFlow:
    """Integration tests for file upload functionality."""

    @pytest.fixture
    def integration_client(self):
        """Create a client for integration tests."""
        api_key = os.getenv("TEST_API_KEY", config.test_api_key)
        if not api_key:
            pytest.skip("No TEST_API_KEY provided")
        return EasyOneClient(
            api_key=api_key,
            base_url=os.getenv("API_BASE_URL", config.api_base_url),
        )

    def test_upload_small_file(self, integration_client):
        """Test uploading a small file (< chunk size)."""
        # Create a temporary file with known content
        test_content = b"Hello, World! This is a small test file for integration testing."

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            # Upload the file
            result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "test_small_file.txt",
                    "mimeType": "text/plain",
                    "retentionDays": 7,
                },
            )

            # Verify response
            assert "cid" in result
            assert "decryptionKey" in result
            assert result["cid"] is not None
            assert len(result["decryptionKey"]) > 0

        finally:
            # Cleanup
            os.unlink(temp_path)

    def test_upload_large_file(self, integration_client):
        """Test uploading a large file (multiple chunks)."""
        # Create a file larger than default chunk size (15MB)
        # We'll use 20MB to ensure multiple chunks
        chunk_size = integration_client.chunk_size
        test_content = b"A" * (chunk_size + 5 * 1024 * 1024)  # chunk_size + 5MB

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".bin") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            # Upload the large file
            result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "test_large_file.bin",
                    "mimeType": "application/octet-stream",
                    "retentionDays": 1,  # Short retention for test files
                },
            )

            # Verify response
            assert "cid" in result
            assert "decryptionKey" in result

            # Note: We can't easily verify the exact number of chunks uploaded
            # without server-side information, but the upload should succeed

        finally:
            # Cleanup
            os.unlink(temp_path)

    def test_upload_with_custom_metadata(self, integration_client):
        """Test uploading file with custom metadata."""
        test_content = b"Custom metadata test content."

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".dat") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "custom_metadata.dat",
                    "mimeType": "application/octet-stream",
                    "retentionDays": 30,
                    "downloadLimit": 5,
                },
            )

            assert "cid" in result
            assert "decryptionKey" in result

        finally:
            os.unlink(temp_path)

    def test_upload_file_like_object(self, integration_client):
        """Test uploading from a file-like object."""
        import io

        test_content = b"File-like object upload test."
        file_obj = io.BytesIO(test_content)

        result = integration_client.upload_file(
            file_obj,
            options={
                "fileName": "file_like_test.txt",
                "mimeType": "text/plain",
                "retentionDays": 7,
            },
        )

        assert "cid" in result
        assert "decryptionKey" in result

    def test_upload_without_options(self, integration_client):
        """Test uploading without specifying options."""
        test_content = b"Test upload without options."

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            # Upload without any options
            result = integration_client.upload_file(temp_path)

            assert "cid" in result
            assert "decryptionKey" in result

        finally:
            os.unlink(temp_path)

    def test_encrypt_and_upload_separately(self, integration_client):
        """Test encrypting data separately and then uploading."""
        test_content = b"Separate encryption test."

        # First encrypt the data
        encrypted = integration_client.encrypt_data(test_content)

        assert "encrypted" in encrypted
        assert "key" in encrypted

        # Note: The SDK doesn't currently support uploading pre-encrypted data
        # This test verifies that the encryption functionality works correctly
        decrypted = integration_client.decrypt_data(encrypted["encrypted"], encrypted["key"])
        assert decrypted == test_content

    def test_encryption_key_uniqueness(self, integration_client):
        """Test that each upload generates a unique encryption key."""
        test_content1 = b"Content 1"
        test_content2 = b"Content 2"

        encrypted1 = integration_client.encrypt_data(test_content1)
        encrypted2 = integration_client.encrypt_data(test_content2)

        # Keys should be different
        assert encrypted1["key"] != encrypted2["key"]

    def test_upload_binary_data(self, integration_client):
        """Test uploading binary data with various byte values."""
        # Create binary data with all possible byte values
        test_content = bytes(range(256)) * 100

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".bin") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "binary_test.bin",
                    "mimeType": "application/octet-stream",
                    "retentionDays": 1,
                },
            )

            assert "cid" in result

        finally:
            os.unlink(temp_path)

    @pytest.mark.slow
    def test_upload_very_large_file(self, integration_client):
        """Test uploading a very large file (50MB)."""
        # Skip in local development due to S3 multipart upload limitations
        from tests.helpers.config import config
        if config.is_local_development():
            pytest.skip("50MB upload skipped in local development (S3 multipart limitations)")

        # This test is marked as slow and may be skipped in normal runs
        chunk_size = integration_client.chunk_size
        test_content = b"X" * (50 * 1024 * 1024)  # 50MB

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".bin") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "very_large_test.bin",
                    "mimeType": "application/octet-stream",
                    "retentionDays": 1,
                },
            )

            assert "cid" in result

        finally:
            os.unlink(temp_path)
