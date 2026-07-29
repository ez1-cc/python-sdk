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
                    "encryptedMetadata": "AAAAAAAAAAAAAAAABBBBBBBBBBBBBBBBBBBBBBBBBBBB",
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
                    "encryptedMetadata": "AAAAAAAAAAAAAAAABBBBBBBBBBBBBBBBBBBBBBBBBBBB",
                },
            )

            # Verify server's CID is returned
            assert result_cid == "server-generated-cid"

    def test_upload_file_streams_protocol_chunks(self, client, mock_response):
        client.chunk_size = 4
        mock_response.json.return_value = {"cid": "server-generated-cid"}
        source = io.BytesIO(b"abcdefg")

        with patch.object(client.session, "post", return_value=mock_response) as mock_post:
            result = client.upload_file(
                source,
                file_name="stream.bin",
                file_size=7,
                mime_type="application/octet-stream",
            )

        assert result["cid"] == "server-generated-cid"
        assert mock_post.call_count == 2
        assert [len(call.kwargs["data"]) for call in mock_post.call_args_list] == [32, 31]

    def test_upload_file_rejects_short_source(self, client):
        with pytest.raises(ValueError, match="ended early"):
            client.upload_file(
                io.BytesIO(b"ab"),
                file_name="short.bin",
                file_size=3,
                mime_type="application/octet-stream",
            )

    def test_upload_file_rejects_trailing_data_before_request(self, client):
        with patch.object(client.session, "post") as mock_post:
            with pytest.raises(ValueError, match="more data"):
                client.upload_file(
                    io.BytesIO(b"abc"),
                    file_name="long.bin",
                    file_size=2,
                    mime_type="application/octet-stream",
                )
        mock_post.assert_not_called()

    def test_download_file_streams_authenticated_chunks(self, client):
        client.chunk_size = 4
        key, key_string = client._generate_encryption_key()
        encrypted = client._encrypt_chunk(b"abcd", key) + client._encrypt_chunk(b"efg", key)
        info_response = Mock(ok=True)
        info_response.json.return_value = {
            "downloadUrl": "https://example.com/download/test-cid",
            "filename": None,
            "mimeType": None,
            "size": None,
            "encryptedMetadata": client._encrypt_metadata({
                "filename": "stream.bin",
                "mimeType": "application/octet-stream",
                "size": 7,
            }, key),
        }
        download_response = Mock(ok=True)
        download_response.iter_content.return_value = [
            encrypted[:3], encrypted[3:35], encrypted[35:]
        ]
        destination = io.BytesIO()

        with patch.object(client.session, "get", return_value=info_response):
            with patch("ez1.requests.get", return_value=download_response) as mock_get:
                metadata = client.download_file(
                    "test-cid", key_string, destination
                )

        assert destination.getvalue() == b"abcdefg"
        assert metadata["size"] == 7
        mock_get.assert_called_once_with(
            "https://example.com/download/test-cid", stream=True
        )
        download_response.close.assert_called_once()

    def test_upload_chunk_requires_encrypted_metadata(self, client):
        with pytest.raises(ValueError, match="encryptedMetadata is required"):
            client._upload_chunk(
                cid=None,
                chunk_index=0,
                total_chunks=1,
                encrypted_data=b"encrypted_data",
                metadata={
                    "fileName": "missing.txt",
                    "fileSize": 1024,
                    "mimeType": "text/plain",
                    "retentionDays": 30,
                    "downloadLimit": None,
                },
            )

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
                "encryptedMetadata": "AAAAAAAAAAAAAAAABBBBBBBBBBBBBBBBBBBBBBBBBBBB",
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
            assert headers["x-file-name"] == "encrypted-metadata"
            assert headers["x-file-size"] == "2048"
            assert headers["x-mime-type"] == "application/octet-stream"
            assert headers["x-encrypted-metadata"] == "AAAAAAAAAAAAAAAABBBBBBBBBBBBBBBBBBBBBBBBBBBB"

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
                    "encryptedMetadata": "AAAAAAAAAAAAAAAABBBBBBBBBBBBBBBBBBBBBBBBBBBB",
                },
            )

            assert result["cid"] == "test-cid"
            assert result["success"] is True

    def test_complete_upload_requires_encrypted_metadata(self, client):
        with pytest.raises(ValueError, match="encryptedMetadata is required"):
            client.complete_upload(
                cid="missing-metadata",
                metadata={
                    "fileName": "missing.txt",
                    "fileSize": 1024,
                    "mimeType": "text/plain",
                },
            )

    def test_build_and_decrypt_encrypted_metadata(self, client):
        """Test public encrypted metadata helpers."""
        metadata = {
            "filename": "report.pdf",
            "mimeType": "application/pdf",
            "size": 2048,
        }
        key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

        encrypted = client.build_encrypted_metadata(metadata, key)
        decrypted = client.decrypt_metadata(encrypted, key)

        assert decrypted == metadata

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
