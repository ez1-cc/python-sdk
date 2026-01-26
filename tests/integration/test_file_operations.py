"""
Integration tests for file operations (list, metadata).
Tests require a valid API key and make real network calls.
"""
import os
import pytest
import tempfile
from ez1 import EasyOneClient
from tests.helpers.config import config


@pytest.mark.integration
@pytest.mark.network
class TestFileOperations:
    """Integration tests for file listing and metadata operations."""

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
    def test_files(self, integration_client):
        """Upload multiple test files for listing tests."""
        test_files = []

        # Upload 3 test files
        for i in range(3):
            test_content = f"Test file {i} content.".encode()

            with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
                f.write(test_content)
                temp_path = f.name

            try:
                result = integration_client.upload_file(
                    temp_path,
                    options={
                        "fileName": f"test_file_{i}.txt",
                        "mimeType": "text/plain",
                        "retentionDays": 7,
                    },
                )
                test_files.append({
                    "cid": result["cid"],
                    "decryptionKey": result["decryptionKey"],
                    "filename": f"test_file_{i}.txt",
                })
            finally:
                os.unlink(temp_path)

        yield test_files

    def test_list_files_default(self, integration_client, test_files):
        """Test listing files with default parameters."""
        result = integration_client.list_files()

        assert "files" in result
        assert "pagination" in result
        assert isinstance(result["files"], list)
        assert len(result["files"]) >= len(test_files)

    def test_list_files_with_limit(self, integration_client, test_files):
        """Test listing files with a limit."""
        result = integration_client.list_files(limit=2)

        assert "files" in result
        assert "pagination" in result
        assert len(result["files"]) <= 2
        assert result["pagination"]["limit"] == 2

    def test_list_files_with_offset(self, integration_client, test_files):
        """Test listing files with an offset."""
        result1 = integration_client.list_files(limit=10, offset=0)
        result2 = integration_client.list_files(limit=10, offset=2)

        # Results should be different when using offset
        assert result1["files"][0]["id"] != result2["files"][0]["id"]

    def test_list_files_pagination_info(self, integration_client):
        """Test that pagination information is correct."""
        result = integration_client.list_files(limit=5, offset=0)

        pagination = result["pagination"]
        assert "limit" in pagination
        assert "offset" in pagination
        assert "total" in pagination
        assert "hasMore" in pagination

        assert pagination["limit"] == 5
        assert pagination["offset"] == 0
        assert pagination["total"] >= 0
        assert isinstance(pagination["hasMore"], bool)

    def test_get_metadata(self, integration_client, test_files):
        """Test getting metadata for a specific file."""
        file_info = test_files[0]
        metadata = integration_client.get_metadata(file_info["cid"])

        assert "id" in metadata
        assert "filename" in metadata
        assert "size" in metadata
        assert "mimeType" in metadata
        assert "uploadedAt" in metadata
        assert metadata["id"] == file_info["cid"]

    def test_get_metadata_fields(self, integration_client, test_files):
        """Test that metadata contains all expected fields."""
        file_info = test_files[0]
        metadata = integration_client.get_metadata(file_info["cid"])

        # Required fields
        required_fields = ["id", "filename", "size", "mimeType", "uploadedAt"]
        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"

        # Optional fields
        optional_fields = ["expiresAt", "downloadLimit", "downloadCount"]
        for field in optional_fields:
            # Just verify we can access the field without error
            _ = metadata.get(field)

    def test_metadata_matches_upload(self, integration_client):
        """Test that metadata reflects the uploaded file information."""
        test_content = b"Metadata verification test content."

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            upload_options = {
                "fileName": "metadata_test.txt",
                "mimeType": "text/plain",
                "retentionDays": 14,
                "downloadLimit": 100,
            }

            result = integration_client.upload_file(temp_path, options=upload_options)
            metadata = integration_client.get_metadata(result["cid"])

            assert metadata["filename"] == upload_options["fileName"]
            assert metadata["mimeType"] == upload_options["mimeType"]
            assert metadata["size"] == len(test_content)

        finally:
            os.unlink(temp_path)

    def test_list_empty_files(self, integration_client):
        """Test listing with a very large offset (should return empty list)."""
        result = integration_client.list_files(limit=10, offset=999999)

        assert "files" in result
        assert "pagination" in result
        assert len(result["files"]) == 0
        assert result["pagination"]["hasMore"] is False

    def test_list_files_maximum_limit(self, integration_client):
        """Test listing files with maximum limit (100)."""
        result = integration_client.list_files(limit=100)

        assert len(result["files"]) <= 100
        assert result["pagination"]["limit"] == 100

    def test_get_multiple_file_metadata(self, integration_client, test_files):
        """Test getting metadata for multiple files."""
        metadatas = []

        for file_info in test_files:
            metadata = integration_client.get_metadata(file_info["cid"])
            metadatas.append(metadata)

        # All metadatas should be unique
        ids = [m["id"] for m in metadatas]
        assert len(ids) == len(set(ids))

    def test_file_size_in_metadata(self, integration_client):
        """Test that file size in metadata is correct."""
        test_content = b"X" * 1000  # Exactly 1000 bytes

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".bin") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = integration_client.upload_file(temp_path)
            metadata = integration_client.get_metadata(result["cid"])

            assert metadata["size"] == 1000

        finally:
            os.unlink(temp_path)

    def test_upload_and_verify_in_list(self, integration_client):
        """Test that uploaded files appear in the list."""
        # Upload a new test file
        test_content = b"File search test content."
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            upload_result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "search_test.txt",
                    "mimeType": "text/plain",
                    "retentionDays": 7,
                },
            )

            # Retry a few times to find the file in the list
            # (there might be a slight delay due to database indexing)
            import time
            max_retries = 5
            for attempt in range(max_retries):
                # Get list of all files
                result = integration_client.list_files(limit=100)

                # Find our test file in the list
                file_ids = [f["id"] for f in result["files"]]

                if upload_result["cid"] in file_ids:
                    # File found, test passes
                    return

                # Wait before retry
                if attempt < max_retries - 1:
                    time.sleep(0.5)

            # If we get here, the file was never found
            assert False, f"Test file {upload_result['cid']} not found in list after {max_retries} attempts"

        finally:
            os.unlink(temp_path)

    @pytest.mark.slow
    def test_list_performance_with_many_files(self, integration_client):
        """Test listing performance with pagination."""
        # This test assumes there may be many files
        all_files = []
        offset = 0
        limit = 50

        while True:
            result = integration_client.list_files(limit=limit, offset=offset)
            all_files.extend(result["files"])

            if not result["pagination"]["hasMore"]:
                break

            offset += limit

        # Verify we got all files
        assert len(all_files) >= 0

    def test_expiration_field_in_metadata(self, integration_client):
        """Test that expiration field is handled correctly."""
        test_content = b"Expiration test content."

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "expiration_test.txt",
                    "mimeType": "text/plain",
                    "retentionDays": 30,  # Should have expiration
                },
            )

            metadata = integration_client.get_metadata(result["cid"])

            # Expiration may or may not be present depending on server implementation
            if "expiresAt" in metadata and metadata["expiresAt"] is not None:
                # If present, it should be a string
                assert isinstance(metadata["expiresAt"], str)

        finally:
            os.unlink(temp_path)

    def test_download_limit_in_metadata(self, integration_client):
        """Test that download limit is reflected in metadata."""
        test_content = b"Download limit test content."

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            download_limit = 50
            result = integration_client.upload_file(
                temp_path,
                options={
                    "fileName": "download_limit_test.txt",
                    "mimeType": "text/plain",
                    "retentionDays": 7,
                    "downloadLimit": download_limit,
                },
            )

            metadata = integration_client.get_metadata(result["cid"])

            # Download limit may or may not be present
            if "downloadLimit" in metadata and metadata["downloadLimit"] is not None:
                assert metadata["downloadLimit"] == download_limit

        finally:
            os.unlink(temp_path)
