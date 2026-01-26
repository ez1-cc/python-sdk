"""
Pytest configuration and fixtures for Python SDK tests.
"""
import os
import sys
import io
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Generator
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ez1 import EasyOneClient
from tests.helpers.config import config


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration."""
    return config


@pytest.fixture
def mock_api_key() -> str:
    """Provide a mock API key for testing."""
    return "up_live_test12345"


@pytest.fixture
def client(mock_api_key: str) -> EasyOneClient:
    """Provide a test client instance."""
    return EasyOneClient(
        api_key=mock_api_key,
        base_url="https://test.example.com",
    )


@pytest.fixture
def sample_file_data() -> bytes:
    """Provide sample file data for testing."""
    return b"Hello, World! This is a test file content." * 100


@pytest.fixture
def sample_file_path(sample_file_data: bytes) -> Generator[str, None, None]:
    """Create a temporary file with sample data."""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
        f.write(sample_file_data)
        temp_path = f.name

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def sample_file_like(sample_file_data: bytes) -> io.BytesIO:
    """Provide a file-like object with sample data."""
    return io.BytesIO(sample_file_data)


@pytest.fixture
def mock_response():
    """Provide a mock response object."""
    mock = Mock()
    mock.ok = True
    mock.status_code = 200
    mock.text = ""
    mock.content = b""
    mock.json.return_value = {}
    return mock


@pytest.fixture
def encrypted_chunk():
    """Provide an encrypted chunk for testing."""
    # This simulates the format: IV(12 bytes) + ciphertext
    import os
    iv = os.urandom(12)
    ciphertext = b"encrypted_data_here"
    return iv + ciphertext


@pytest.fixture
def sample_cid() -> str:
    """Provide a sample content ID."""
    return "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def sample_decryption_key() -> str:
    """Provide a sample decryption key (base64 encoded)."""
    import base64
    return base64.b64encode(b"test_key_32_bytes_long_encryption").decode("utf-8")


@pytest.fixture
def mock_upload_response(mock_response, sample_cid: str):
    """Provide a mock upload response."""
    return mock_response


@pytest.fixture
def mock_metadata_response(mock_response, sample_cid: str):
    """Provide a mock metadata response."""
    mock_response.json.return_value = {
        "id": sample_cid,
        "filename": "test.txt",
        "size": 1024,
        "mimeType": "text/plain",
        "uploadedAt": "2024-01-01T00:00:00Z",
        "expiresAt": "2024-02-01T00:00:00Z",
        "downloadLimit": 10,
        "downloadCount": 0,
    }
    return mock_response


@pytest.fixture
def mock_list_files_response(mock_response):
    """Provide a mock list files response."""
    mock_response.json.return_value = {
        "files": [
            {
                "id": "file1",
                "filename": "test1.txt",
                "size": 1024,
                "mimeType": "text/plain",
                "uploadedAt": "2024-01-01T00:00:00Z",
                "expiresAt": "2024-02-01T00:00:00Z",
                "downloadLimit": 10,
                "downloadCount": 0,
            },
            {
                "id": "file2",
                "filename": "test2.txt",
                "size": 2048,
                "mimeType": "text/plain",
                "uploadedAt": "2024-01-02T00:00:00Z",
                "expiresAt": None,
                "downloadLimit": None,
                "downloadCount": 5,
            },
        ],
        "pagination": {
            "limit": 50,
            "offset": 0,
            "total": 2,
            "hasMore": False,
        },
    }
    return mock_response


@pytest.fixture
def mock_download_info_response(mock_response):
    """Provide a mock download info response."""
    mock_response.json.return_value = {
        "cid": "test-cid",
        "filename": "test.txt",
        "size": 1024,
        "mimeType": "text/plain",
        "downloadUrl": "https://example.com/download/test-cid",
        "expiresAt": "2024-02-01T00:00:00Z",
        "downloadLimit": 10,
        "downloadCount": 0,
    }
    return mock_response


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (no network calls)")
    config.addinivalue_line("markers", "integration: Integration tests (requires API key)")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "encryption: Encryption/decryption tests")
    config.addinivalue_line("markers", "network: Tests that make network calls")


def pytest_collection_modifyitems(config, items):
    """Modify collected test items based on configuration."""
    from tests.helpers.config import TestConfig

    test_config = TestConfig.from_env()

    # Skip integration tests if not enabled
    if test_config.should_skip_integration():
        skip_integration = pytest.mark.skip(
            reason="Integration tests disabled (set RUN_INTEGRATION_TESTS=true and provide TEST_API_KEY)"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
