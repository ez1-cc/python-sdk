"""
Test configuration loader for Python SDK tests.
"""
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class TestConfig:
    """Test configuration settings."""
    api_base_url: str
    cdn_base_url: str
    test_api_key: str
    default_chunk_size: int
    default_retention_days: int
    run_integration_tests: bool
    mock_api_responses: bool
    coverage_min_percent: int

    @classmethod
    def from_env(cls) -> "TestConfig":
        """Load configuration from environment variables."""
        # Try to load from .env.test file
        env_file = Path(__file__).parent.parent.parent / ".env.test"
        if env_file.exists():
            cls._load_env_file(env_file)

        return cls(
            api_base_url=os.getenv("API_BASE_URL", "https://file.ez1.cc"),
            cdn_base_url=os.getenv("CDN_BASE_URL", "https://serve.ez1.cc"),
            test_api_key=os.getenv("TEST_API_KEY", ""),
            default_chunk_size=int(os.getenv("DEFAULT_CHUNK_SIZE", str(15 * 1024 * 1024))),
            default_retention_days=int(os.getenv("DEFAULT_RETENTION_DAYS", "30")),
            run_integration_tests=os.getenv("RUN_INTEGRATION_TESTS", "false").lower() == "true",
            mock_api_responses=os.getenv("MOCK_API_RESPONSES", "true").lower() == "true",
            coverage_min_percent=int(os.getenv("COVERAGE_MIN_PERCENT", "80")),
        )

    @staticmethod
    def _load_env_file(env_file: Path) -> None:
        """Load environment variables from .env file."""
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

    def should_skip_integration(self) -> bool:
        """Check if integration tests should be skipped."""
        return not self.run_integration_tests or not self.test_api_key

    def is_local_development(self) -> bool:
        """Check if running in local development environment."""
        return "localhost" in self.api_base_url or "127.0.0.1" in self.api_base_url


# Global config instance
config = TestConfig.from_env()
