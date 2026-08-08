"""Platform-level OTP email delivery via Resend, and the environment
branch in request_otp() that decides whether to send it or just log
it. Found and fixed 2026-08-08: `environment` defaults to "local" and
nothing set it to "production" on the deployed Render service, so the
dev-only log path (meant only for local/CI convenience) was silently
active in real production -- every OTP code for every real signup was
being written in plaintext to Render's logs. Fixed by setting
ENVIRONMENT=production on Render and wiring up actual delivery here so
the dev-only path genuinely only fires outside production."""

from unittest.mock import AsyncMock

import httpx
import pytest

from tallyquo.core import resend_client
from tallyquo.core.config import get_settings
from tallyquo.identity import service


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse | None = None, raise_error: Exception | None = None):
        self._response = response
        self._raise_error = raise_error
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if self._raise_error:
            raise self._raise_error
        return self._response


def _patch_settings(monkeypatch, **overrides):
    settings = get_settings()
    for key, value in overrides.items():
        monkeypatch.setattr(settings, key, value)
    return settings


@pytest.mark.asyncio
async def test_send_otp_email_posts_to_resend_with_the_code(monkeypatch):
    _patch_settings(monkeypatch, resend_api_key="re_test_key", otp_from_email="Tallyquo <noreply@orbynlabs.ca>")
    fake_client = _FakeAsyncClient(_FakeResponse(200))
    monkeypatch.setattr(resend_client.httpx, "AsyncClient", lambda **kw: fake_client)

    await resend_client.send_otp_email("someone@example.com", "482913")

    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"]["Authorization"] == "Bearer re_test_key"
    assert call["json"]["to"] == ["someone@example.com"]
    assert "482913" in call["json"]["subject"]
    assert "482913" in call["json"]["text"]
    assert call["json"]["from"] == "Tallyquo <noreply@orbynlabs.ca>"


@pytest.mark.asyncio
async def test_send_otp_email_raises_on_non_2xx(monkeypatch):
    _patch_settings(monkeypatch, resend_api_key="re_test_key")
    fake_client = _FakeAsyncClient(_FakeResponse(422, "domain not verified"))
    monkeypatch.setattr(resend_client.httpx, "AsyncClient", lambda **kw: fake_client)

    with pytest.raises(resend_client.EmailSendFailed, match="422"):
        await resend_client.send_otp_email("someone@example.com", "482913")


@pytest.mark.asyncio
async def test_send_otp_email_raises_on_transport_error(monkeypatch):
    _patch_settings(monkeypatch, resend_api_key="re_test_key")
    fake_client = _FakeAsyncClient(raise_error=httpx.ConnectError("no route to host"))
    monkeypatch.setattr(resend_client.httpx, "AsyncClient", lambda **kw: fake_client)

    with pytest.raises(resend_client.EmailSendFailed):
        await resend_client.send_otp_email("someone@example.com", "482913")


@pytest.mark.asyncio
async def test_send_otp_email_without_api_key_raises_immediately(monkeypatch):
    _patch_settings(monkeypatch, resend_api_key="")
    with pytest.raises(resend_client.EmailSendFailed, match="not configured"):
        await resend_client.send_otp_email("someone@example.com", "482913")


@pytest.mark.asyncio
async def test_request_otp_sends_real_email_only_in_production(monkeypatch):
    """The actual gap this whole feature exists to close: outside
    production, request_otp must never attempt a real send (dev/CI have
    no Resend account, and the test suite calling this function
    directly must never need network access)."""
    _patch_settings(monkeypatch, environment="production", resend_api_key="re_test_key")
    send_mock = AsyncMock()
    import tallyquo.core.resend_client as rc_module

    monkeypatch.setattr(rc_module, "send_otp_email", send_mock)

    code = await service.request_otp("prodpath@example.com", ip=None)
    assert code is not None
    send_mock.assert_awaited_once()
    assert send_mock.await_args.args[0] == "prodpath@example.com"
    assert send_mock.await_args.args[1] == code


@pytest.mark.asyncio
async def test_request_otp_does_not_send_email_outside_production(monkeypatch):
    _patch_settings(monkeypatch, environment="local")
    send_mock = AsyncMock()
    import tallyquo.core.resend_client as rc_module

    monkeypatch.setattr(rc_module, "send_otp_email", send_mock)

    code = await service.request_otp("localpath@example.com", ip=None)
    assert code is not None
    send_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_otp_send_failure_does_not_raise_or_change_return_value(monkeypatch):
    """A1/A2: a Resend outage must never be visible to the caller --
    same generic behaviour as a successful send, just logged."""
    _patch_settings(monkeypatch, environment="production", resend_api_key="re_test_key")
    import tallyquo.core.resend_client as rc_module

    async def _boom(*args, **kwargs):
        raise rc_module.EmailSendFailed("Resend is down")

    monkeypatch.setattr(rc_module, "send_otp_email", _boom)

    code = await service.request_otp("failpath@example.com", ip=None)
    assert code is not None
