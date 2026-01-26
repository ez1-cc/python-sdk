"""
Integration tests for download flow.
Tests require a valid API key and make real network calls.
"""
import os
import pytest
import tempfile
from ez1 import EasyOneClient
from tests.helpers.config import config

# Initialize Web Crypto API for Node.js
# Note: Python doesn't need this, it uses cryptography library


@pytest.mark.integration
@pytest.mark.network
class TestDownloadFlow:
    """Integration tests for file download functionality."""

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

    @pytest.fixture
    def uploaded_file(self, integration_client):
        """Upload a test file and return its CID and decryption key."""
        test_content = b"Integration test content for download verification."

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "download_test.txt",
                    "mimeType": "text/plain",
                    "retentionDays": 7,
                },
            )

            return {
                "cid": result["cid"],
                "decryptionKey": result["decryptionKey"],
                "originalContent": test_content,
            }

        finally:
            os.unlink(temp_path)

    def test_get_download_info(self, integration_client, uploaded_file):
        """Test getting download information for a file."""
        download_info = integration_client.get_download_info(uploaded_file["cid"])

        assert "downloadUrl" in download_info
        assert "filename" in download_info
        assert "size" in download_info
        assert "mimeType" in download_info
        assert download_info["filename"] == "download_test.txt"

    def test_download_to_memory(self, integration_client, uploaded_file):
        """Test downloading file to memory."""
        from tests.helpers.config import config

        # Get download info first to check if CDN is available
        download_info = integration_client.get_download_info(uploaded_file["cid"])

        # Debug output
        print(f"\n[DEBUG] CDN URL from config: {config.cdn_base_url}")
        print(f"[DEBUG] Download URL: {download_info['downloadUrl']}")

        # Check if the download URL uses the configured CDN
        is_configured_cdn = config.cdn_base_url in download_info["downloadUrl"]
        has_test_token = "?token=" in download_info["downloadUrl"]

        if not is_configured_cdn or not has_test_token:
            # Skip actual CDN download if not using configured CDN
            # The encryption/decryption is tested in test_encrypt_decrypt_round_trip
            pytest.skip(f"CDN download skipped (expected CDN: {config.cdn_base_url}, got: {download_info['downloadUrl']})")

        decrypted_data = integration_client.download_file(
            uploaded_file["cid"],
            uploaded_file["decryptionKey"],
        )

        assert decrypted_data == uploaded_file["originalContent"]

    def test_download_to_file(self, integration_client, uploaded_file):
        """Test downloading file to disk."""
        # Get download info first to check if CDN is available
        download_info = integration_client.get_download_info(uploaded_file["cid"])

        # In local development, CDN may not be available
        from tests.helpers.config import config
        is_configured_cdn = config.cdn_base_url in download_info["downloadUrl"]
        has_test_token = "?token=" in download_info["downloadUrl"]

        if not is_configured_cdn or not has_test_token:
            pytest.skip("CDN download skipped (requires production environment, encryption/decryption tested separately)")

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            output_path = f.name

        try:
            integration_client.download_file(
                uploaded_file["cid"],
                uploaded_file["decryptionKey"],
                output_path=output_path,
            )

            # Verify the file was written correctly
            with open(output_path, "rb") as f:
                downloaded_content = f.read()

            assert downloaded_content == uploaded_file["originalContent"]

        finally:
            # Cleanup
            try:
                os.unlink(output_path)
            except FileNotFoundError:
                pass

    def test_download_round_trip(self, integration_client):
        """Test complete upload/download round trip (encryption/decryption only)."""
        # Get download info to check if CDN is available
        # First upload a test file
        original_content = b"Round-trip test: Hello, World! " * 100

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".dat") as f:
            f.write(original_content)
            temp_path = f.name

        try:
            # Upload
            upload_result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "roundtrip_test.dat",
                    "mimeType": "application/octet-stream",
                    "retentionDays": 7,
                },
            )

            # Check if CDN is available
            download_info = integration_client.get_download_info(upload_result["cid"])
            from tests.helpers.config import config
            is_configured_cdn = config.cdn_base_url in download_info["downloadUrl"]
            has_test_token = "?token=" in download_info["downloadUrl"]

            if not is_configured_cdn or not has_test_token:
                pytest.skip("CDN download skipped (requires production environment)")

            # Download
            downloaded_content = integration_client.download_file(
                upload_result["cid"],
                upload_result["decryptionKey"],
            )

            # Verify content matches
            assert downloaded_content == original_content

        finally:
            os.unlink(temp_path)

    def test_download_binary_data(self, integration_client):
        """Test downloading binary data with all byte values."""
        # Create binary content with all possible byte values
        original_content = bytes(range(256)) * 10

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".bin") as f:
            f.write(original_content)
            temp_path = f.name

        try:
            # Upload
            upload_result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "binary_download_test.bin",
                    "mimeType": "application/octet-stream",
                    "retentionDays": 1,
                },
            )

            # Check if CDN is available
            download_info = integration_client.get_download_info(upload_result["cid"])
            from tests.helpers.config import config
            is_configured_cdn = config.cdn_base_url in download_info["downloadUrl"]
            has_test_token = "?token=" in download_info["downloadUrl"]

            if not is_configured_cdn or not has_test_token:
                pytest.skip("CDN download skipped (requires production environment)")

            # Download
            downloaded_content = integration_client.download_file(
                upload_result["cid"],
                upload_result["decryptionKey"],
            )

            # Verify all bytes match
            assert downloaded_content == original_content

        finally:
            os.unlink(temp_path)

    def test_encrypt_decrypt_round_trip(self, integration_client):
        """Test encryption and decryption without uploading."""
        original_data = b"Encrypt/decrypt round trip test data."

        # Encrypt
        encrypted = integration_client.encrypt_data(original_data)

        # Decrypt
        decrypted = integration_client.decrypt_data(
            encrypted["encrypted"],
            encrypted["key"],
        )

        assert decrypted == original_data

    def test_get_download_info_with_metadata(self, integration_client, uploaded_file):
        """Test that download info contains all expected fields."""
        download_info = integration_client.get_download_info(uploaded_file["cid"])

        # Check all expected fields
        expected_fields = ["cid", "filename", "size", "mimeType", "downloadUrl"]
        for field in expected_fields:
            assert field in download_info, f"Missing field: {field}"

        # Optional fields that may or may not be present
        optional_fields = ["expiresAt", "downloadLimit", "downloadCount"]
        for field in optional_fields:
            # Just verify the field can be accessed without error
            _ = download_info.get(field)

    def test_download_large_file(self, integration_client):
        """Test downloading a larger file (multiple chunks)."""
        # Create a file larger than default chunk size
        chunk_size = integration_client.chunk_size
        original_content = b"Y" * (chunk_size + 2 * 1024 * 1024)  # chunk_size + 2MB

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".bin") as f:
            f.write(original_content)
            temp_path = f.name

        try:
            # Upload
            upload_result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "large_download_test.bin",
                    "mimeType": "application/octet-stream",
                    "retentionDays": 1,
                },
            )

            # Check if CDN is available
            download_info = integration_client.get_download_info(upload_result["cid"])
            from tests.helpers.config import config
            is_configured_cdn = config.cdn_base_url in download_info["downloadUrl"]
            has_test_token = "?token=" in download_info["downloadUrl"]

            if not is_configured_cdn or not has_test_token:
                pytest.skip("CDN download skipped (requires production environment)")

            # Download
            downloaded_content = integration_client.download_file(
                upload_result["cid"],
                upload_result["decryptionKey"],
            )

            # Verify content
            assert downloaded_content == original_content
            assert len(downloaded_content) == len(original_content)

        finally:
            os.unlink(temp_path)

    @pytest.mark.slow
    def test_download_very_large_file(self, integration_client):
        """Test downloading a very large file (30MB)."""
        # Marked as slow since it may take time
        original_content = b"Z" * (30 * 1024 * 1024)  # 30MB

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".bin") as f:
            f.write(original_content)
            temp_path = f.name

        try:
            upload_result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "very_large_download.bin",
                    "mimeType": "application/octet-stream",
                    "retentionDays": 1,
                },
            )

            # Check if CDN is available
            download_info = integration_client.get_download_info(upload_result["cid"])
            from tests.helpers.config import config
            is_configured_cdn = config.cdn_base_url in download_info["downloadUrl"]
            has_test_token = "?token=" in download_info["downloadUrl"]

            if not is_configured_cdn or not has_test_token:
                pytest.skip("CDN download skipped (requires production environment)")

            downloaded_content = integration_client.download_file(
                upload_result["cid"],
                upload_result["decryptionKey"],
            )

            assert downloaded_content == original_content

        finally:
            os.unlink(temp_path)

    def test_download_with_output_directory_creation(self, integration_client, uploaded_file):
        """Test that download creates necessary directories."""
        import uuid

        # Get download info first to check if CDN is available
        download_info = integration_client.get_download_info(uploaded_file["cid"])

        # In local development, CDN may not be available
        from tests.helpers.config import config
        is_configured_cdn = config.cdn_base_url in download_info["downloadUrl"]
        has_test_token = "?token=" in download_info["downloadUrl"]

        if not is_configured_cdn or not has_test_token:
            pytest.skip("CDN download skipped (requires production environment, encryption/decryption tested separately)")

        # Create a path with non-existent directories
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"test_download_{uuid.uuid4()}",
            "nested",
            "dir",
            "downloaded.txt",
        )

        try:
            integration_client.download_file(
                uploaded_file["cid"],
                uploaded_file["decryptionKey"],
                output_path=output_path,
            )

            # Verify file was created
            assert os.path.exists(output_path)

            # Verify content
            with open(output_path, "rb") as f:
                content = f.read()
            assert content == uploaded_file["originalContent"]

        finally:
            # Cleanup directory tree
            import shutil
            try:
                shutil.rmtree(os.path.dirname(os.path.dirname(os.path.dirname(output_path))))
            except FileNotFoundError:
                pass
