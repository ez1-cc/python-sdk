"""
Unit tests for API calls (with mocks).
"""
import io
import pytest
from unittest.mock import Mock, patch, call
from ez1 import EasyOneClient


@pytest.mark.unit
class TestAPICalls:
    """Test API call methods with mocks."""

    def test_upload_chunk_success(self, client, mock_response):
        """Test successful chunk upload (chunk 0)."""
        # Setup mock response with CID
        mock_response.json.return_value = {"cid": "server-generated-cid", "success": True, "message": "Chunk uploaded"}
        mock_response.ok = True

        with patch.object(client.session, 'post', return_value=mock_response):
            # Test chunk 0: cid should be None
            result_cid = client._upload_chunk(
                cid=None,  # chunk 0: server generates CID
                chunk_index=0,
                total_chunks=1,
                encrypted_data=b"encrypted_data",
                metadata={
                    "fileName": "test.txt",
                    "fileSize": 1024,
                    "mimeType": "text/plain",
                    "retentionDays": 30,
                    "downloadLimit": 10,
                },
            )

            # Verify server's CID is returned
            assert result_cid == "server-generated-cid"

    def test_upload_chunk_without_download_limit(self, client, mock_response):
        """Test chunk upload without download limit (chunk 0)."""
        mock_response.json.return_value = {"cid": "server-generated-cid", "success": True, "message": "Chunk uploaded"}
        mock_response.ok = True

        with patch.object(client.session, 'post', return_value=mock_response):
            result_cid = client._upload_chunk(
                cid=None,  # chunk 0: server generates CID
                chunk_index=0,
                total_chunks=1,
                encrypted_data=b"encrypted_data",
                metadata={
                    "fileName": "test.txt",
                    "fileSize": 1024,
                    "mimeType": "text/plain",
                    "retentionDays": 30,
                    "downloadLimit": None,
                },
            )

            # Verify server's CID is returned
            assert result_cid == "server-generated-cid"

    def test_upload_chunk_request_format(self, client, mock_response):
        """Test that upload request has correct format (subsequent chunk with CID)."""
        mock_response.json.return_value = {"cid": "server-generated-cid", "success": True, "message": "Chunk uploaded"}
        mock_response.ok = True

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            cid = "test-cid"
            chunk_index = 2  # Subsequent chunk
            total_chunks = 5
            encrypted_data = b"encrypted_data"
            metadata = {
                "fileName": "test file.txt",
                "fileSize": 2048,
                "mimeType": "application/octet-stream",
                "retentionDays": 7,
                "downloadLimit": 5,
            }

            client._upload_chunk(cid, chunk_index, total_chunks, encrypted_data, metadata)

            # Verify the call
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Check headers
            headers = call_args.kwargs['headers']
            assert headers["Authorization"] == "Bearer up_live_test12345"
            assert headers["x-cid"] == cid  # Subsequent chunks send CID
            assert headers["x-chunk-index"] == str(chunk_index)

    def test_complete_upload_success(self, client, mock_response):
        """Test successful complete upload."""
        mock_response.json.return_value = {"cid": "test-cid", "success": True}

        with patch.object(client.session, 'post', return_value=mock_response):
            result = client.complete_upload(
                cid="test-cid",
                metadata={
                    "fileName": "test.txt",
                    "fileSize": 1024,
                    "mimeType": "text/plain",
                },
            )

            assert result["cid"] == "test-cid"
            assert result["success"] is True

    def test_get_metadata_success(self, client, sample_cid, mock_metadata_response):
        """Test successful get metadata."""
        with patch.object(client.session, 'get', return_value=mock_metadata_response):
            metadata = client.get_metadata(sample_cid)

            assert metadata["id"] == sample_cid
            assert metadata["filename"] == "test.txt"
            assert metadata["size"] == 1024
            assert metadata["mimeType"] == "text/plain"

    def test_list_files_success(self, client, mock_list_files_response):
        """Test successful list files."""
        with patch.object(client.session, 'get', return_value=mock_list_files_response):
            result = client.list_files(limit=10, offset=5)

            assert len(result["files"]) == 2
            assert result["pagination"]["limit"] == 50
            assert result["pagination"]["total"] == 2

    def test_get_download_info_success(self, client, mock_download_info_response):
        """Test successful get download info."""
        with patch.object(client.session, 'get', return_value=mock_download_info_response):
            info = client.get_download_info("test-cid")

            assert info["cid"] == "test-cid"
            assert info["filename"] == "test.txt"
            assert "downloadUrl" in info
