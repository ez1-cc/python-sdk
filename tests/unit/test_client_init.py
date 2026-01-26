"""
Unit tests for client initialization.
"""
import pytest
from ez1 import EasyOneClient


@pytest.mark.unit
class TestClientInit:
    """Test client initialization and configuration."""

    def test_default_values(self):
        """Test client initialization with default values."""
        client = EasyOneClient(api_key="up_live_test_key")

        assert client.api_key == "up_live_test_key"
        assert client.base_url == EasyOneClient.DEFAULT_BASE_URL
        assert client.chunk_size == EasyOneClient.DEFAULT_CHUNK_SIZE
        assert client.session is not None

    def test_custom_base_url(self):
        """Test client initialization with custom base URL."""
        custom_url = "https://custom.example.com"
        client = EasyOneClient(api_key="up_live_test_key", base_url=custom_url)

        assert client.base_url == custom_url

    def test_all_custom_parameters(self):
        """Test client initialization with all custom parameters."""
        custom_url = "https://api.example.com"
        api_key = "up_live_custom_api_key"

        client = EasyOneClient(
            api_key=api_key,
            base_url=custom_url,
        )

        assert client.api_key == api_key
        assert client.base_url == custom_url
        assert client.chunk_size == EasyOneClient.DEFAULT_CHUNK_SIZE  # Fixed at 15MB

    def test_default_base_url_constant(self):
        """Test the DEFAULT_BASE_URL constant."""
        assert EasyOneClient.DEFAULT_BASE_URL == "https://easyone.io"

    def test_default_chunk_size_constant(self):
        """Test the DEFAULT_CHUNK_SIZE constant."""
        assert EasyOneClient.DEFAULT_CHUNK_SIZE == 15 * 1024 * 1024  # 15MB

    def test_iv_length_constant(self):
        """Test the IV_LENGTH constant (for AES-GCM)."""
        assert EasyOneClient.IV_LENGTH == 12

    def test_session_created(self):
        """Test that a requests Session is created."""
        import requests

        client = EasyOneClient(api_key="up_test_key")

        assert isinstance(client.session, requests.Session)

    def test_get_headers(self, client):
        """Test that default headers include authorization."""
        headers = client._get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer up_live_test12345"

    def test_get_headers_format(self, client):
        """Test the format of the authorization header."""
        headers = client._get_headers()

        # Should follow Bearer token format
        assert headers["Authorization"].startswith("Bearer ")

    def test_api_key_stored_as_is(self):
        """Test that API key is stored without modification."""
        special_key = "up_live_e458375d_1ea6b2ed70c45b029e63ba4f1327197bb24cd62b29ca190b8a460bf5e386e716"
        client = EasyOneClient(api_key=special_key)

        assert client.api_key == special_key

    def test_base_url_without_trailing_slash(self):
        """Test base URL handling without trailing slash."""
        url = "https://example.com/api"
        client = EasyOneClient(api_key="up_live_key", base_url=url)
        assert client.base_url == url

    def test_base_url_with_trailing_slash(self):
        """Test base URL handling with trailing slash."""
        url = "https://example.com/api/"
        client = EasyOneClient(api_key="up_live_key", base_url=url)
        assert client.base_url == url

    def test_api_key_validation_up_live(self):
        """Test API key validation for up_live_ prefix."""
        client = EasyOneClient(api_key="up_live_valid_key_123")
        assert client.api_key == "up_live_valid_key_123"

    def test_api_key_validation_up_test(self):
        """Test API key validation for up_test_ prefix."""
        client = EasyOneClient(api_key="up_test_valid_key_456")
        assert client.api_key == "up_test_valid_key_456"

    def test_api_key_validation_invalid_prefix(self):
        """Test API key validation rejects invalid prefix."""
        with pytest.raises(ValueError, match="Invalid API key format"):
            EasyOneClient(api_key="invalid_key_xyz")

    def test_api_key_validation_empty(self):
        """Test API key validation rejects empty key."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            EasyOneClient(api_key="")

    def test_api_key_validation_whitespace_only(self):
        """Test API key validation rejects whitespace-only key."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            EasyOneClient(api_key="   ")

    def test_api_key_trimming(self):
        """Test that API key is trimmed of whitespace."""
        client = EasyOneClient(api_key="  up_live_key_with_spaces  ")
        assert client.api_key == "up_live_key_with_spaces"
