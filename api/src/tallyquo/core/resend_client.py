"""Platform-level transactional email via Resend's HTTP API -- distinct
from notifications/smtp_client.py, which sends on a *tenant's own*
configured identity (invoices to clients). An OTP sign-in code is
requested before any tenant or business profile exists, so there is no
tenant identity to send it from; this always goes out as the platform.
"""

import httpx

from tallyquo.core.config import get_settings

_RESEND_URL = "https://api.resend.com/emails"


class EmailSendFailed(Exception):
    """Raised on any non-2xx response or transport failure. The caller
    (identity/service.py) never lets this reach the HTTP response --
    edgecases.md A1/A2 require the request-otp response to be identical
    regardless of what happened server-side, so a delivery failure is
    logged, not surfaced to the client."""


async def send_otp_email(to_address: str, code: str) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        raise EmailSendFailed("RESEND_API_KEY is not configured.")

    minutes = settings.otp_ttl_seconds // 60
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(
                _RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.otp_from_email,
                    "to": [to_address],
                    "subject": f"Your Tallyquo sign-in code: {code}",
                    "text": (
                        f"Your Tallyquo sign-in code is {code}.\n\n"
                        f"It expires in {minutes} minutes. If you didn't request "
                        "this, you can safely ignore this email."
                    ),
                },
            )
        except httpx.HTTPError as exc:
            raise EmailSendFailed(f"Could not reach Resend: {exc}") from exc

    if response.status_code >= 400:
        raise EmailSendFailed(f"Resend returned {response.status_code}: {response.text}")
