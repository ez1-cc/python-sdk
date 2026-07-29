"""
EasyOne Python SDK

Official SDK for interacting with EasyOne API.
Provides client-side AES-GCM encryption and chunked upload functionality.
"""

import os
import base64
import json
from urllib.parse import quote
from typing import Optional, BinaryIO, Dict, Any, Tuple

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

    DEFAULT_BASE_URL = "https://file.ez1.cc"
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
            base_url: API base URL (defaults to https://file.ez1.cc)

        Note:
            Chunk size is fixed at 15MB for compatibility with CDN download workers.

        Raises:
            ValueError: If API key is empty or has invalid format
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")

        api_key = api_key.strip()

        # Validate API key format
        if not api_key.startswith("up_live_"):
            raise ValueError(
                "Invalid API key format. API keys must start with 'up_live_'"
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
        source: BinaryIO,
        *,
        file_name: str,
        file_size: int,
        mime_type: str,
        retention_days: int = 30,
        download_limit: Optional[int] = None,
        private: bool = False,
    ) -> Dict[str, str]:
        """
        Upload a file with client-side encryption.

        Args:
            source: Binary stream positioned at the first byte to upload
            file_name: User-facing filename
            file_size: Exact number of bytes available from source
            mime_type: User-facing MIME type
            retention_days: Retention period
            download_limit: Optional download count limit
            private: Restrict access to the uploader

        Returns:
            Dict with 'cid' and 'decryptionKey'

        Raises:
            ValueError: If file is too large or has forbidden MIME type
            Exception: If upload fails
        """
        if not hasattr(source, "read"):
            raise TypeError("source must be a binary readable stream")
        if not file_name or not mime_type:
            raise ValueError("file_name and mime_type are required")
        if not isinstance(file_size, int) or isinstance(file_size, bool) or file_size < 0:
            raise ValueError("file_size must be a non-negative integer")

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

        encryption_key, decryption_key = self._generate_encryption_key()
        encrypted_metadata = self._encrypt_metadata(
            {"filename": file_name, "mimeType": mime_type, "size": file_size},
            encryption_key,
        )
        total_chunks = max(1, (file_size + self.chunk_size - 1) // self.chunk_size)
        cid = None

        for chunk_index in range(total_chunks):
            remaining = file_size - chunk_index * self.chunk_size
            chunk = self._read_exact(source, min(self.chunk_size, max(remaining, 0)))
            if chunk_index == total_chunks - 1 and source.read(1):
                raise ValueError("source contains more data than file_size")
            encrypted_chunk = self._encrypt_chunk(chunk, encryption_key)
            cid = self._upload_chunk(
                cid,
                chunk_index,
                total_chunks,
                encrypted_chunk,
                {
                    "fileName": file_name,
                    "fileSize": file_size,
                    "mimeType": mime_type,
                    "retentionDays": retention_days,
                    "downloadLimit": download_limit,
                    "isPrivate": private,
                    "encryptedMetadata": encrypted_metadata,
                },
            )

        if not cid:
            raise RuntimeError("upload completed without a server-generated CID")
        return {"cid": cid, "decryptionKey": decryption_key}

    @staticmethod
    def _read_exact(source: BinaryIO, length: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < length:
            remaining = length - len(chunks)
            chunk = source.read(remaining)
            if not chunk:
                raise ValueError(
                    f"source ended early: expected {length} bytes, received {len(chunks)}"
                )
            if not isinstance(chunk, bytes):
                raise TypeError("source must return bytes")
            if len(chunk) > remaining:
                raise ValueError("source returned more bytes than requested")
            chunks.extend(chunk)
        return bytes(chunks)

    @staticmethod
    def _write_all(destination: BinaryIO, data: bytes) -> None:
        offset = 0
        while offset < len(data):
            written = destination.write(data[offset:])
            if not isinstance(written, int) or written <= 0:
                raise IOError("destination failed to accept decrypted data")
            offset += written

    def _upload_chunk(
        self,
        cid: Optional[str],
        chunk_index: int,
        total_chunks: int,
        encrypted_data: bytes,
        metadata: Dict[str, Any],
        max_retries: int = 5,
    ) -> str:
        """
        Upload a single encrypted chunk with retry logic for rate limiting.

        Returns:
            The CID (Content ID) returned by the server

        Note:
            For chunk 0, do not send x-cid header (server generates CID).
            For chunks > 0, send the CID returned by the server.
        """
        if not metadata.get("encryptedMetadata"):
            raise ValueError("encryptedMetadata is required")
        url = f"{self.base_url}/api/public/v1/upload"

        headers = self._get_headers()
        headers.update({
            "x-chunk-index": str(chunk_index),
            "x-total-chunks": str(total_chunks),
            "x-file-name": quote("encrypted-metadata", safe=""),
            "x-file-size": str(metadata["fileSize"]),
            "x-mime-type": "application/octet-stream",
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

        headers["x-encrypted-metadata"] = metadata["encryptedMetadata"]

        if metadata.get("isPrivate"):
            headers["x-private"] = "true"

        last_error = None

        for attempt in range(max_retries + 1):
            response = self.session.post(
                url,
                headers=headers,
                data=encrypted_data,
            )

            if response.ok:
                # Extract CID from response
                result = response.json()
                if "cid" not in result:
                    raise Exception(f"Server did not return CID: {result}")
                return result["cid"]

            if response.status_code == 429:
                # Rate limited - get Retry-After header
                retry_after = response.headers.get("Retry-After")
                wait_seconds = int(retry_after) if retry_after else (2 ** attempt)

                last_error = Exception(
                    f"Rate limited. Retry after {wait_seconds} seconds. (Attempt {attempt + 1}/{max_retries + 1})"
                )

                if attempt < max_retries:
                    import time
                    time.sleep(wait_seconds)
                    continue

            # Non-429 error or max retries exceeded
            raise Exception(f"Upload failed: {response.text}")

        raise last_error or Exception("Upload failed after retries")

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
        if not metadata.get("encryptedMetadata"):
            raise ValueError("encryptedMetadata is required")
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

    def build_encrypted_metadata(
        self,
        metadata: Dict[str, Any],
        decryption_key: str,
    ) -> str:
        """
        Build encrypted metadata for low-level multipart flows.

        Args:
            metadata: Dict with filename, mimeType, and size
            decryption_key: Base64 AES key returned by upload/encrypt helpers

        Returns:
            Base64 AES-GCM metadata payload
        """
        if not metadata.get("filename") or not metadata.get("mimeType") or not isinstance(metadata.get("size"), int):
            raise ValueError("metadata requires filename, mimeType, and integer size")

        key = base64.b64decode(decryption_key)
        return self._encrypt_metadata(
            {
                "filename": metadata["filename"],
                "mimeType": metadata["mimeType"],
                "size": metadata["size"],
            },
            key,
        )

    def decrypt_metadata(self, encrypted_metadata: str, decryption_key: str) -> Dict[str, Any]:
        """
        Decrypt encrypted metadata returned by metadata/list/download APIs.
        """
        return self._decrypt_metadata(encrypted_metadata, decryption_key)

    def download_file(
        self,
        cid: str,
        decryption_key: str,
        destination: BinaryIO,
    ) -> Dict[str, Any]:
        """
        Download and decrypt a file.

        Args:
            cid: Content ID
            decryption_key: Decryption key (base64 string)
            destination: Binary stream that receives authenticated plaintext chunks

        Returns:
            Decrypted filename, MIME type, and size
        """
        download_info = self.get_download_info(cid)
        if not download_info.get("encryptedMetadata"):
            raise ValueError("download is missing encrypted metadata")
        file_info = self._decrypt_metadata(
            download_info["encryptedMetadata"], decryption_key
        )
        if (
            not isinstance(file_info, dict)
            or not isinstance(file_info.get("filename"), str)
            or not file_info["filename"]
            or not isinstance(file_info.get("mimeType"), str)
            or not file_info["mimeType"]
            or not isinstance(file_info.get("size"), int)
            or isinstance(file_info["size"], bool)
            or file_info["size"] < 0
            or file_info["size"] > 100 * 1024 * 1024 * 1024
        ):
            raise ValueError(
                "download metadata does not contain a valid filename, MIME type, and size"
            )
        if not hasattr(destination, "write"):
            raise TypeError("destination must be a binary writable stream")

        response = requests.get(download_info["downloadUrl"], stream=True)
        try:
            if not response.ok:
                raise Exception(f"Download failed: {response.reason}")

            key = base64.b64decode(decryption_key, validate=True)
            aesgcm = AESGCM(key)
            encrypted_parts = iter(response.iter_content(chunk_size=64 * 1024))
            buffered = bytearray()
            total_chunks = max(1, (file_info["size"] + self.chunk_size - 1) // self.chunk_size)

            for chunk_index in range(total_chunks):
                remaining = file_info["size"] - chunk_index * self.chunk_size
                plaintext_size = min(self.chunk_size, max(remaining, 0))
                encrypted_size = plaintext_size + self.IV_LENGTH + 16
                while len(buffered) < encrypted_size:
                    try:
                        part = next(encrypted_parts)
                    except StopIteration as error:
                        raise ValueError(
                            f"encrypted download ended early at chunk {chunk_index}"
                        ) from error
                    if part:
                        buffered.extend(part)

                encrypted_chunk = bytes(buffered[:encrypted_size])
                del buffered[:encrypted_size]
                nonce = encrypted_chunk[: self.IV_LENGTH]
                plaintext = aesgcm.decrypt(
                    nonce, encrypted_chunk[self.IV_LENGTH :], None
                )
                if len(plaintext) != plaintext_size:
                    raise ValueError(f"decrypted chunk {chunk_index} has an invalid size")
                self._write_all(destination, plaintext)

            if buffered:
                raise ValueError("encrypted download contains trailing data")
            for part in encrypted_parts:
                if part:
                    raise ValueError("encrypted download contains trailing data")
            return file_info
        finally:
            response.close()

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

    def _generate_encryption_key(self) -> Tuple[bytes, str]:
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

    def _encrypt_metadata(self, metadata: Dict[str, Any], key: bytes) -> str:
        """Encrypt private file metadata using the same AES-GCM key."""
        aesgcm = AESGCM(key)
        nonce = os.urandom(self.IV_LENGTH)
        plaintext = json.dumps(metadata, separators=(",", ":")).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return base64.b64encode(nonce + ciphertext).decode("utf-8")

    def _decrypt_metadata(self, encrypted_metadata: str, key_string: str) -> Dict[str, Any]:
        """Decrypt private file metadata returned by the API."""
        key = base64.b64decode(key_string)
        payload = base64.b64decode(encrypted_metadata)
        aesgcm = AESGCM(key)
        nonce = payload[: self.IV_LENGTH]
        ciphertext = payload[self.IV_LENGTH :]
        return json.loads(aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8"))

    def _decrypt_chunk(self, encrypted_data: bytes, key_string: str) -> bytes:
        """Decrypt a chunk of data using AES-GCM."""
        key = base64.b64decode(key_string)
        aesgcm = AESGCM(key)
        nonce = encrypted_data[: self.IV_LENGTH]
        ciphertext = encrypted_data[self.IV_LENGTH :]
        return aesgcm.decrypt(nonce, ciphertext, None)

__all__ = ["EasyOneClient"]
__version__ = "2.0.0"
