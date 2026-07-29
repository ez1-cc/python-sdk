"""Helpers for exercising the public streaming SDK API in integration tests."""

from pathlib import Path
from typing import Dict, Optional, Union

from ez1 import EasyOneClient


def upload_path(
    client: EasyOneClient,
    file_path: Union[str, Path],
    *,
    file_name: Optional[str] = None,
    mime_type: str = "application/octet-stream",
    retention_days: int = 30,
    download_limit: Optional[int] = None,
    private: bool = False,
) -> Dict[str, str]:
    path = Path(file_path)
    with path.open("rb") as source:
        return client.upload_file(
            source,
            file_name=file_name or path.name,
            file_size=path.stat().st_size,
            mime_type=mime_type,
            retention_days=retention_days,
            download_limit=download_limit,
            private=private,
        )
