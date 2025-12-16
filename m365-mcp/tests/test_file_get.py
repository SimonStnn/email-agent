from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

from src.m365_mcp.tools import file as file_tools
from src.m365_mcp.validators import ValidationError


@pytest.fixture
def record_stream_calls(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[Any]], None]:
    """Patch _stream_download to replay configured outcomes."""

    calls: deque[Any] = deque()

    def configure(outcomes: list[Any]) -> None:
        calls.clear()
        calls.extend(outcomes)

    def fake_stream(url: str, destination: Path, **kwargs: Any) -> None:
        if not calls:
            raise AssertionError("No outcomes configured for _stream_download")
        outcome = calls.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        data: bytes = outcome
        destination.write_bytes(data)

    monkeypatch.setattr(file_tools, "_stream_download", fake_stream)
    return configure


def _register_metadata(
    register_graph: Callable[[str, str, Any], None],
    metadata: dict[str, Any],
) -> None:
    register_graph("GET", f"/me/drive/items/{metadata['id']}", metadata)


def test_file_get_downloads_file_successfully(
    tmp_path: Path,
    mock_graph_request: Callable[[str, str, Any], None],
    mock_file_metadata: Callable[..., dict[str, Any]],
    mock_account_id: str,
    record_stream_calls: Callable[[list[Any]], None],
) -> None:
    destination = tmp_path / "downloaded.txt"
    metadata = mock_file_metadata(size=512)
    _register_metadata(mock_graph_request, metadata)
    record_stream_calls([b"hello world"])

    result = file_tools._file_get_impl(
        metadata["id"], mock_account_id, str(destination)
    )

    assert destination.exists()
    assert destination.read_bytes() == b"hello world"
    assert result["name"] == metadata["name"]
    assert result["mime_type"] == metadata["file"]["mimeType"]


def test_file_get_rejects_non_graph_host(
    tmp_path: Path,
    mock_graph_request: Callable[[str, str, Any], None],
    mock_file_metadata: Callable[..., dict[str, Any]],
    mock_account_id: str,
    record_stream_calls: Callable[[list[Any]], None],
) -> None:
    destination = tmp_path / "downloaded.txt"
    metadata = mock_file_metadata(
        **{"@microsoft.graph.downloadUrl": "https://malicious.example.com/file"}
    )
    _register_metadata(mock_graph_request, metadata)
    record_stream_calls([b""])

    with pytest.raises(ValidationError) as exc:
        file_tools._file_get_impl(metadata["id"], mock_account_id, str(destination))

    assert "Host" in exc.value.args[0] or "host" in exc.value.args[0]
    assert not destination.exists()


def test_file_get_enforces_size_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_graph_request: Callable[[str, str, Any], None],
    mock_file_metadata: Callable[..., dict[str, Any]],
    mock_account_id: str,
    record_stream_calls: Callable[[list[Any]], None],
) -> None:
    monkeypatch.setattr(file_tools, "MAX_DOWNLOAD_MIB", 1)
    destination = tmp_path / "downloaded.txt"
    metadata = mock_file_metadata(size=2 * 1024 * 1024)
    _register_metadata(mock_graph_request, metadata)
    record_stream_calls([b"a" * (2 * 1024)])

    with pytest.raises(ValidationError):
        file_tools._file_get_impl(metadata["id"], mock_account_id, str(destination))

    assert not destination.exists()


def test_file_get_cleans_up_on_http_error(
    tmp_path: Path,
    mock_graph_request: Callable[[str, str, Any], None],
    mock_file_metadata: Callable[..., dict[str, Any]],
    mock_account_id: str,
    record_stream_calls: Callable[[list[Any]], None],
) -> None:
    destination = tmp_path / "downloaded.txt"
    metadata = mock_file_metadata(size=512)
    _register_metadata(mock_graph_request, metadata)
    request = httpx.Request("GET", metadata["@microsoft.graph.downloadUrl"])
    response = httpx.Response(500, request=request)
    record_stream_calls(
        [
            httpx.HTTPStatusError("server error", request=request, response=response),
            httpx.HTTPStatusError("server error", request=request, response=response),
            httpx.HTTPStatusError("server error", request=request, response=response),
            httpx.HTTPStatusError("server error", request=request, response=response),
        ]
    )

    with pytest.raises(RuntimeError):
        file_tools._file_get_impl(metadata["id"], mock_account_id, str(destination))

    assert not destination.exists()


def test_file_get_retries_then_succeeds(
    tmp_path: Path,
    mock_graph_request: Callable[[str, str, Any], None],
    mock_file_metadata: Callable[..., dict[str, Any]],
    mock_account_id: str,
    record_stream_calls: Callable[[list[Any]], None],
) -> None:
    destination = tmp_path / "downloaded.txt"
    metadata = mock_file_metadata(size=512)
    _register_metadata(mock_graph_request, metadata)
    request = httpx.Request("GET", metadata["@microsoft.graph.downloadUrl"])
    response = httpx.Response(503, request=request)
    record_stream_calls(
        [
            httpx.HTTPStatusError("transient", request=request, response=response),
            b"final-chunk",
        ]
    )

    result = file_tools._file_get_impl(
        metadata["id"], mock_account_id, str(destination)
    )

    payload = destination.read_bytes()
    assert payload == b"final-chunk"
    expected_size_mb = round(len(payload) / (1024 * 1024), 2)
    assert result["size_mb"] == expected_size_mb


def test_file_get_timeout_raises_runtime_error(
    tmp_path: Path,
    mock_graph_request: Callable[[str, str, Any], None],
    mock_file_metadata: Callable[..., dict[str, Any]],
    mock_account_id: str,
    record_stream_calls: Callable[[list[Any]], None],
) -> None:
    destination = tmp_path / "downloaded.txt"
    metadata = mock_file_metadata(size=512)
    _register_metadata(mock_graph_request, metadata)
    record_stream_calls([httpx.ReadTimeout("timeout", request=None)])

    with pytest.raises(RuntimeError):
        file_tools._file_get_impl(metadata["id"], mock_account_id, str(destination))

    assert not destination.exists()


def test_file_list_rejects_invalid_limit(mock_account_id: str) -> None:
    with pytest.raises(ValidationError):
        file_tools.file_list.fn(account_id=mock_account_id, limit=0)
