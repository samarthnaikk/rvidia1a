from email.message import Message
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from app.core import client_cli, p2p_cli


class _FakeResponse:
    def __init__(self, body: str, content_type: str = "application/json"):
        self._body = body.encode("utf-8")
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _redirect_error(url: str, location: str) -> HTTPError:
    headers = Message()
    headers["Location"] = location
    return HTTPError(
        url=url,
        code=301,
        msg="Moved Permanently",
        hdrs=headers,
        fp=BytesIO(b"<html>redirect</html>"),
    )


def test_client_cli_follows_redirect_and_preserves_json_parsing() -> None:
    initial_url = "http://example.com/jobs"
    redirected_url = "http://example.com/jobs/"

    responses = [
        _redirect_error(initial_url, redirected_url),
        _FakeResponse('{"ok": true}'),
    ]

    def _fake_urlopen(req, timeout=30):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        payload = client_cli._api_request("GET", "http://example.com", "/jobs", token="t")

    assert payload == {"ok": True}


def test_p2p_cli_follows_redirect_and_preserves_json_parsing() -> None:
    initial_url = "http://example.com/p2p/jobs/abc/request-access"
    redirected_url = "http://example.com/p2p/jobs/abc/request-access/"

    responses = [
        _redirect_error(initial_url, redirected_url),
        _FakeResponse('{"status": "accepted"}'),
    ]

    def _fake_urlopen(req, timeout=30):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        payload = p2p_cli._api_request(
            "POST",
            "http://example.com",
            "/p2p/jobs/abc/request-access",
            token="t",
            payload={},
        )

    assert payload == {"status": "accepted"}
