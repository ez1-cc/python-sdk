"""
EasyOne Python SDK

Official SDK for interacting with EasyOne API.
Provides client-side AES-GCM encryption and chunked upload functionality.
"""

import os
import base64
import uuid
from typing import Optional, BinaryIO, Dict, Any
from pathlib import Path

try:
    import requests
except ImportError:
    raise ImportError("requests is required. Install with: pip install requests")

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.backends import default_backend
except ImportError:
    raise ImportError("cryptography is required. Install with: pip install cryptography")


class EasyOneClient:
    """
    Main EasyOne Client for Python.
    """

    DEFAULT_BASE_URL = "https://easyone.io"
    DEFAULT_CHUNK_SIZE = 15 * 1024 * 1024  # 15MB
    IV_LENGTH = 12

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the EasyOne client.

        Args:
            api_key: Your EasyOne API key
            base_url: API base URL (defaults to https://easyone.io)

        Note:
            Chunk size is fixed at 15MB for compatibility with CDN download workers.

        Raises:
            ValueError: If API key is empty or has invalid format
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")

        api_key = api_key.strip()

        # Validate API key format
        if not (api_key.startswith("up_live_") or api_key.startswith("up_test_")):
            raise ValueError(
                "Invalid API key format. API keys must start with 'up_live_' or 'up_test_'"
            )

        self.api_key = api_key
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.chunk_size = self.DEFAULT_CHUNK_SIZE  # Fixed at 15MB
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        """Get default headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

    def upload_file(
        self,
        file_path: str | BinaryIO,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Upload a file with client-side encryption.

        Args:
            file_path: Path to file or file-like object
            options: Optional metadata (fileName, mimeType, retentionDays, downloadLimit)

        Returns:
            Dict with 'cid' and 'decryptionKey'

        Raises:
            ValueError: If file is too large or has forbidden MIME type
            Exception: If upload fails
        """
        options = options or {}

        # Handle file input
        if isinstance(file_path, str):
            file_obj = open(file_path, "rb")
            should_close = True
            file_name = options.get("fileName") or os.path.basename(file_path)
            # Get file size for validation
            file_size = os.path.getsize(file_path)
        else:
            file_obj = file_path
            should_close = False
            file_name = options.get("fileName") or getattr(file_obj, "name", "unnamed")
            # For file-like objects, read to get size
            current_pos = file_obj.tell()
            file_obj.seek(0, 2)  # Seek to end
            file_size = file_obj.tell()
            file_obj.seek(current_pos)  # Seek back to original position

        # Client-side validation: Check file size (100GB max for enterprise, 5GB default)
        max_file_size = 100 * 1024 * 1024 * 1024  # 100GB
        if file_size > max_file_size:
            raise ValueError(
                f"File too large: {file_size} bytes. Maximum size is {max_file_size} bytes"
            )

        # Client-side validation: Warn about potentially problematic file types
        forbidden_extensions = [".exe", ".bat", ".cmd", ".com", ".pif", ".scr", ".vbs", ".js"]
        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext in forbidden_extensions:
            raise ValueError(
                f"Forbidden file type: {file_ext}. Executable files are not allowed for security reasons."
            )

        try:
            # Generate encryption key
            encryption_key, decryption_key = self._generate_encryption_key()

            # Calculate chunks (ensure at least 1 chunk even for empty files)
            total_chunks = max(1, (file_size + self.chunk_size - 1) // self.chunk_size)

            # SECURITY: CID is now server-generated on first chunk
            # Do not generate client-side CID
            cid = None

            # Upload chunks using streaming to avoid memory exhaustion
            for chunk_index in range(total_chunks):
                start = chunk_index * self.chunk_size
                end = min(start + self.chunk_size, file_size)

                # Seek to chunk position and read only this chunk (streaming)
                file_obj.seek(start)
                chunk = file_obj.read(end - start)

                # Encrypt chunk
                encrypted_chunk = self._encrypt_chunk(chunk, encryption_key)

                # Upload chunk (server returns CID on first chunk)
                cid = self._upload_chunk(
                    cid,
                    chunk_index,
                    total_chunks,
                    encrypted_chunk,
                    {
                        "fileName": file_name,
                        "fileSize": file_size,
                        "mimeType": options.get("mimeType", "application/octet-stream"),
                        "retentionDays": options.get("retentionDays", 30),
                        "downloadLimit": options.get("downloadLimit"),
                    },
                )

            return {"cid": cid, "decryptionKey": decryption_key}

        finally:
            if should_close:
                file_obj.close()

    def _upload_chunk(
        self,
        cid: str | None,
        chunk_index: int,
        total_chunks: int,
        encrypted_data: bytes,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Upload a single encrypted chunk.

        Returns:
            The CID (Content ID) returned by the server

        Note:
            For chunk 0, do not send x-cid header (server generates CID).
            For chunks > 0, send the CID returned by the server.
        """
        url = f"{self.base_url}/api/public/v1/upload"

        headers = self._get_headers()
        headers.update({
            "x-chunk-index": str(chunk_index),
            "x-total-chunks": str(total_chunks),
            "x-file-name": metadata["fileName"],
            "x-file-size": str(metadata["fileSize"]),
            "x-mime-type": metadata["mimeType"],
            "x-retention-days": str(metadata["retentionDays"]),
        })

        # SECURITY: Only send x-cid header for subsequent chunks
        # First chunk: server generates CID
        # Subsequent chunks: use CID returned by server
        if chunk_index > 0:
            if not cid:
                raise ValueError(f"CID required for chunk {chunk_index} but not provided")
            headers["x-cid"] = cid

        if metadata.get("downloadLimit") is not None:
            headers["x-download-limit"] = str(metadata["downloadLimit"])

        response = self.session.post(
            url,
            headers=headers,
            data=encrypted_data,
        )

        if not response.ok:
            raise Exception(f"Upload failed: {response.text}")

        # Extract CID from response
        result = response.json()
        if "cid" not in result:
            raise Exception(f"Server did not return CID: {result}")

        return result["cid"]

    def complete_upload(
        self,
        cid: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Complete a multipart upload (alternative approach).

        Args:
            cid: Content ID
            metadata: File metadata (fileName, fileSize, mimeType, etc.)

        Returns:
            Dict with 'cid' and 'success' status
        """
        url = f"{self.base_url}/api/public/v1/complete-upload"

        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        response = self.session.post(
            url,
            headers=headers,
            json={
                "cid": cid,
                **metadata,
            },
        )

        if not response.ok:
            raise Exception(f"Complete upload failed: {response.text}")

        return response.json()

    def download_file(
        self,
        cid: str,
        decryption_key: str,
        output_path: Optional[str] = None,
    ) -> bytes:
        """
        Download and decrypt a file.

        Args:
            cid: Content ID
            decryption_key: Decryption key (base64 string)
            output_path: Optional path to save the file

        Returns:
            Decrypted file data as bytes
        """
        # Get download info
        download_info = self.get_download_info(cid)

        # Download file
        response = requests.get(download_info["downloadUrl"])
        if not response.ok:
            raise Exception(f"Download failed: {response.reason}")

        encrypted_data = response.content

        # Decrypt data (handles both single and multi-chunk files)
        decrypted_data = self._decrypt_multi_chunk(encrypted_data, decryption_key)

        # Save to file if output path provided
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(decrypted_data)

        return decrypted_data

    def get_download_info(self, cid: str) -> Dict[str, Any]:
        """
        Get download information for a file.

        Args:
            cid: Content ID

        Returns:
            Dict with download info (downloadUrl, filename, size, etc.)
        """
        url = f"{self.base_url}/api/public/v1/files/{cid}/download"

        response = self.session.get(url, headers=self._get_headers())

        if not response.ok:
            raise Exception(f"Get download info failed: {response.text}")

        return response.json()

    def get_metadata(self, cid: str) -> Dict[str, Any]:
        """
        Get file metadata.

        Args:
            cid: Content ID

        Returns:
            Dict with file metadata
        """
        url = f"{self.base_url}/api/public/v1/files/{cid}/metadata"

        response = self.session.get(url, headers=self._get_headers())

        if not response.ok:
            raise Exception(f"Get metadata failed: {response.text}")

        return response.json()

    def list_files(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List user's files.

        Args:
            limit: Number of files to return (max 100)
            offset: Pagination offset

        Returns:
            Dict with 'files' list and 'pagination' info
        """
        url = f"{self.base_url}/api/public/v1/files"
        params = {"limit": limit, "offset": offset}

        response = self.session.get(url, headers=self._get_headers(), params=params)

        if not response.ok:
            raise Exception(f"List files failed: {response.text}")

        return response.json()

    def encrypt_data(self, data: bytes) -> Dict[str, Any]:
        """
        Encrypt data without uploading.

        Args:
            data: Raw data to encrypt

        Returns:
            Dict with 'encrypted' (bytes) and 'key' (base64 string)
        """
        encryption_key, key_string = self._generate_encryption_key()
        encrypted = self._encrypt_chunk(data, encryption_key)

        return {
            "encrypted": encrypted,
            "key": key_string,
        }

    def decrypt_data(self, encrypted_data: bytes, key: str) -> bytes:
        """
        Decrypt data.

        Args:
            encrypted_data: Encrypted data
            key: Decryption key (base64 string)

        Returns:
            Decrypted data as bytes
        """
        return self._decrypt_chunk(encrypted_data, key)

    def _generate_encryption_key(self) -> tuple[bytes, str]:
        """Generate a new AES-GCM encryption key."""
        key = AESGCM.generate_key(bit_length=256)
        key_string = base64.b64encode(key).decode("utf-8")
        return key, key_string

    def _encrypt_chunk(self, data: bytes, key: bytes) -> bytes:
        """Encrypt a chunk of data using AES-GCM."""
        aesgcm = AESGCM(key)
        nonce = os.urandom(self.IV_LENGTH)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def _decrypt_chunk(self, encrypted_data: bytes, key_string: str) -> bytes:
        """Decrypt a chunk of data using AES-GCM."""
        key = base64.b64decode(key_string)
        aesgcm = AESGCM(key)
        nonce = encrypted_data[: self.IV_LENGTH]
        ciphertext = encrypted_data[self.IV_LENGTH :]
        return aesgcm.decrypt(nonce, ciphertext, None)

    def _decrypt_multi_chunk(self, encrypted_data: bytes, key_string: str) -> bytes:
        """
        Decrypt data that may consist of multiple chunks.

        Each chunk is encrypted separately with:
        [12 bytes IV][encrypted data][16 bytes tag]

        For multi-chunk files, we need to decrypt each chunk separately.
        """
        key = base64.b64decode(key_string)
        aesgcm = AESGCM(key)

        # Encryption overhead: IV (12 bytes) + tag (16 bytes) = 28 bytes
        # Chunk size is 15MB, so encrypted chunk size is 15MB + 28 bytes
        CHUNK_SIZE = 15 * 1024 * 1024  # 15MB
        ENCRYPTION_OVERHEAD = 12 + 16  # IV + tag
        ENCRYPTED_CHUNK_SIZE = CHUNK_SIZE + ENCRYPTION_OVERHEAD

        # If data is smaller than one encrypted chunk, decrypt as single chunk
        if len(encrypted_data) <= ENCRYPTED_CHUNK_SIZE:
            return self._decrypt_chunk(encrypted_data, key_string)

        # Multi-chunk file: decrypt each chunk separately
        decrypted_chunks = []
        offset = 0

        while offset < len(encrypted_data):
            # Calculate encrypted chunk size (last chunk may be smaller)
            remaining_bytes = len(encrypted_data) - offset
            current_encrypted_size = min(ENCRYPTED_CHUNK_SIZE, remaining_bytes)

            # Extract encrypted chunk
            encrypted_chunk = encrypted_data[offset:offset + current_encrypted_size]

            # Decrypt this chunk
            decrypted_chunk = self._decrypt_chunk(encrypted_chunk, key_string)
            decrypted_chunks.append(decrypted_chunk)

            offset += current_encrypted_size

        # Combine all decrypted chunks
        return b"".join(decrypted_chunks)


__all__ = ["EasyOneClient"]
__version__ = "1.0.0"
