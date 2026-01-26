"""
Unit tests for encryption/decryption functionality.
"""
import pytest
import base64
from ez1 import EasyOneClient


@pytest.mark.unit
@pytest.mark.encryption
class TestEncryption:
    """Test encryption and decryption operations."""

    def test_generate_encryption_key(self, client):
        """Test encryption key generation."""
        key, key_string = client._generate_encryption_key()

        # Key should be 32 bytes (256 bits)
        assert len(key) == 32

        # Key string should be valid base64
        decoded = base64.b64decode(key_string)
        assert len(decoded) == 32
        assert decoded == key

    def test_generate_unique_keys(self, client):
        """Test that each generated key is unique."""
        keys = set()
        for _ in range(100):
            _, key_string = client._generate_encryption_key()
            keys.add(key_string)

        # All keys should be unique
        assert len(keys) == 100

    def test_encrypt_decrypt_round_trip(self, client):
        """Test that encrypting and decrypting returns original data."""
        original_data = b"Hello, World! This is test data for encryption."

        key, key_string = client._generate_encryption_key()
        encrypted = client._encrypt_chunk(original_data, key)
        decrypted = client._decrypt_chunk(encrypted, key_string)

        assert decrypted == original_data

    def test_encrypt_empty_data(self, client):
        """Test encrypting empty data."""
        original_data = b""

        key, key_string = client._generate_encryption_key()
        encrypted = client._encrypt_chunk(original_data, key)
        decrypted = client._decrypt_chunk(encrypted, key_string)

        assert decrypted == original_data

    def test_encrypt_large_data(self, client):
        """Test encrypting large data (1MB)."""
        original_data = b"A" * (1024 * 1024)  # 1MB

        key, key_string = client._generate_encryption_key()
        encrypted = client._encrypt_chunk(original_data, key)
        decrypted = client._decrypt_chunk(encrypted, key_string)

        assert decrypted == original_data

    def test_encrypt_with_binary_data(self, client):
        """Test encrypting binary data (including null bytes)."""
        original_data = bytes(range(256)) * 10  # All possible byte values

        key, key_string = client._generate_encryption_key()
        encrypted = client._encrypt_chunk(original_data, key)
        decrypted = client._decrypt_chunk(encrypted, key_string)

        assert decrypted == original_data

    def test_decrypt_with_wrong_key_fails(self, client):
        """Test that decrypting with wrong key raises an error."""
        original_data = b"Secret data"

        key1, key_string1 = client._generate_encryption_key()
        _, key_string2 = client._generate_encryption_key()  # Different key

        encrypted = client._encrypt_chunk(original_data, key1)

        # Should fail when decrypting with wrong key
        with pytest.raises(Exception):  # cryptography library raises an exception
            client._decrypt_chunk(encrypted, key_string2)

    def test_decrypt_tampered_data_fails(self, client):
        """Test that decrypting tampered data raises an error."""
        original_data = b"Secret data"

        key, key_string = client._generate_encryption_key()
        encrypted = client._encrypt_chunk(original_data, key)

        # Tamper with the encrypted data
        tampered = encrypted[:-1] + bytes([encrypted[-1] ^ 0xFF])

        # Should fail when decrypting tampered data (AES-GCM provides authentication)
        with pytest.raises(Exception):
            client._decrypt_chunk(tampered, key_string)

    def test_encryption_adds_iv(self, client):
        """Test that encrypted data includes IV."""
        original_data = b"Test data"

        key, _ = client._generate_encryption_key()
        encrypted = client._encrypt_chunk(original_data, key)

        # Encrypted data should be longer than original (IV + ciphertext + tag)
        assert len(encrypted) > len(original_data)

        # IV should be at the beginning
        iv_length = EasyOneClient.IV_LENGTH
        assert len(encrypted) >= iv_length + len(original_data) + 16  # 16 is GCM tag length

    def test_different_encryptions_produce_different_results(self, client):
        """Test that encrypting the same data twice produces different results (due to random IV)."""
        original_data = b"Same data"

        key, key_string = client._generate_encryption_key()
        encrypted1 = client._encrypt_chunk(original_data, key)
        encrypted2 = client._encrypt_chunk(original_data, key)

        # Encrypted data should be different (different IVs)
        assert encrypted1 != encrypted2

        # But both should decrypt to the same value
        assert client._decrypt_chunk(encrypted1, key_string) == original_data
        assert client._decrypt_chunk(encrypted2, key_string) == original_data

    def test_encrypt_data_method(self, client):
        """Test the public encrypt_data method."""
        original_data = b"Public method test"

        result = client.encrypt_data(original_data)

        assert "encrypted" in result
        assert "key" in result
        assert isinstance(result["encrypted"], bytes)
        assert isinstance(result["key"], str)

        # Verify decryption
        decrypted = client.decrypt_data(result["encrypted"], result["key"])
        assert decrypted == original_data

    def test_decrypt_data_method(self, client):
        """Test the public decrypt_data method."""
        original_data = b"Decrypt method test"

        result = client.encrypt_data(original_data)
        decrypted = client.decrypt_data(result["encrypted"], result["key"])

        assert decrypted == original_data
