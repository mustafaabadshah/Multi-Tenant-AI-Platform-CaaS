"""Automated Verification Suite for Python SDK (mmaip)."""

import sys
from pathlib import Path

import pytest

# Add sdk/python to sys.path
sdk_path = Path(__file__).resolve().parent.parent.parent / "sdk" / "python"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from mmaip.client import MMAIPClient, MMAIPError  # noqa: E402


def test_python_sdk_initialization():
    """Verify that MMAIPClient enforces required API key and base URL normalization."""
    with pytest.raises(MMAIPError):
        MMAIPClient(api_key="")

    client = MMAIPClient(api_key="mmaip_live_test_12345", base_url="http://127.0.0.1:8000/api/v1/")
    assert client.api_key == "mmaip_live_test_12345"
    assert client.base_url == "http://127.0.0.1:8000/api/v1"
    headers = client._headers()
    assert headers["Authorization"] == "Bearer mmaip_live_test_12345"
    assert headers["Content-Type"] == "application/json"
    assert "mmaip-python-sdk" in headers["User-Agent"]


def test_python_sdk_error_model():
    """Verify MMAIPError status code and message representation."""
    err = MMAIPError("Unauthorized access", status_code=401)
    assert str(err) == "Unauthorized access"
    assert err.status_code == 401
