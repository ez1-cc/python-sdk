"""
Unit tests for error handling scenarios.
"""
import pytest
from unittest.mock import Mock, patch
from ez1 import EasyOneClient
import requests


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_upload_chunk_non_ok_response(self, client):
        """Test upload failure when response is not OK."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.text = "Upload failed: insufficient storage"

        with patch.object(client.session, 'post', return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                client._upload_chunk(
                    cid=None,  # chunk 0: no cid
                    chunk_index=0,
                    total_chunks=1,
                    encrypted_data=b"data",
                    metadata={
                        "fileName": "test.txt",
                        "fileSize": 100,
                        "mimeType": "text/plain",
                        "retentionDays": 30,
                    },
                )

            assert "Upload failed" in str(exc_info.value)

    def test_complete_upload_non_ok_response(self, client):
        """Test complete upload failure."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.text = "Invalid CID"

        with patch.object(client.session, 'post', return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                client.complete_upload("invalid-cid", {"fileName": "test.txt", "fileSize": 100, "mimeType": "text/plain"})

            assert "Complete upload failed" in str(exc_info.value)

    def test_get_metadata_non_ok_response(self, client):
        """Test get metadata failure."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.text = "File not found"

        with patch.object(client.session, 'get', return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                client.get_metadata("nonexistent-cid")

            assert "Get metadata failed" in str(exc_info.value)

    def test_list_files_non_ok_response(self, client):
        """Test list files failure."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.text = "Unauthorized"

        with patch.object(client.session, 'get', return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                client.list_files()

            assert "List files failed" in str(exc_info.value)

    def test_get_download_info_non_ok_response(self, client):
        """Test get download info failure."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.text = "File expired"

        with patch.object(client.session, 'get', return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                client.get_download_info("expired-cid")

            assert "Get download info failed" in str(exc_info.value)

    def test_download_file_download_failure(self, client):
        """Test download failure when fetching file."""
        mock_info_response = Mock()
        mock_info_response.ok = True
        mock_info_response.json.return_value = {
            "downloadUrl": "https://example.com/download/test-cid",
            "filename": "test.txt",
            "mimeType": "text/plain",
        }

        mock_download_response = Mock()
        mock_download_response.ok = False
        mock_download_response.statusText = "Not Found"

        with patch.object(client.session, 'get', return_value=mock_info_response):
            with patch('easyone.requests.get', return_value=mock_download_response):
                with pytest.raises(Exception) as exc_info:
                    client.download_file("test-cid", "decryption_key")

                assert "Download failed" in str(exc_info.value)

    def test_upload_file_invalid_path(self, client):
        """Test uploading file with invalid path."""
        with pytest.raises(FileNotFoundError):
            client.upload_file("/nonexistent/path/to/file.txt")

    def test_decrypt_with_invalid_base64_key(self, client):
        """Test decryption with invalid base64 key."""
        encrypted_data = b"some_encrypted_data_here"
        invalid_key = "not_valid_base64!!!"

        with pytest.raises(Exception):
            client._decrypt_chunk(encrypted_data, invalid_key)

    def test_decrypt_with_truncated_data(self, client):
        """Test decryption with data that's too short."""
        # Data shorter than IV length
        truncated_data = b"short"

        key, key_string = client._generate_encryption_key()

        with pytest.raises(Exception):
            client._decrypt_chunk(truncated_data, key_string)

    def test_upload_file_with_file_like_object_read_error(self, client):
        """Test upload when file-like object raises error on read."""
        file_obj = Mock()
        file_obj.read.side_effect = IOError("Read error")
        # Mock tell() and seek() for file size detection
        file_obj.tell.return_value = 100  # File size
        file_obj.seek.return_value = None
        # Mock name attribute (should be a string, not Mock)
        file_obj.name = "test.bin"

        with pytest.raises(IOError):
            client.upload_file(file_obj)

    def test_session_reuse(self, client):
        """Test that session is reused across requests."""
        with patch.object(client.session, 'get', return_value=Mock(ok=True, json=Mock(return_value={}))) as mock_get:
            client.get_metadata("cid1")
            client.get_metadata("cid2")

            # Should use the same session (same mock object)
            assert mock_get.call_count == 2

    def test_network_timeout_simulation(self, client):
        """Test handling of network timeout."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.text = "Request timeout"

        with patch.object(client.session, 'post', return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                client._upload_chunk(
                    cid=None,  # chunk 0: no cid
                    chunk_index=0,
                    total_chunks=1,
                    encrypted_data=b"data",
                    metadata={
                        "fileName": "test.txt",
                        "fileSize": 100,
                        "mimeType": "text/plain",
                        "retentionDays": 30,
                    },
                )

            assert "Upload failed" in str(exc_info.value)

    def test_response_with_empty_body(self, client):
        """Test handling of response with empty body."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.text = ""

        with patch.object(client.session, 'get', return_value=mock_response):
            with pytest.raises(Exception):
                client.get_metadata("test-cid")

    def test_malformed_json_response(self, client):
        """Test handling of malformed JSON response."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch.object(client.session, 'get', return_value=mock_response):
            with pytest.raises(ValueError):
                client.get_metadata("test-cid")

    def test_empty_api_key(self):
        """Test client with empty API key raises ValueError."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            EasyOneClient(api_key="")

    def test_special_characters_in_filename(self, client):
        """Test uploading file with special characters in name."""
        special_filename = "test file (1) [copy].txt"

        # Create a mock response that returns CID
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"cid": "server-generated-cid", "success": True, "message": "Chunk uploaded"}

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            client._upload_chunk(
                cid=None,  # chunk 0: no cid
                chunk_index=0,
                total_chunks=1,
                encrypted_data=b"data",
                metadata={
                    "fileName": special_filename,
                    "fileSize": 100,
                    "mimeType": "text/plain",
                    "retentionDays": 30,
                },
            )

            # Filename should be passed as-is (URL encoding handled by requests)
            call_args = mock_post.call_args
            assert call_args.kwargs['headers']['x-file-name'] == special_filename
