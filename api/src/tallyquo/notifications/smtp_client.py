"""Sends via a tenant's own configured SMTP server -- never a
platform-level sending identity. architecture.md's external
dependencies table: "isolated per tenant by construction; a failure
never affects another tenant or any other feature."
"""

from dataclasses import dataclass, field
from email.message import EmailMessage

import aiosmtplib


@dataclass
class Attachment:
    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"


@dataclass
class SmtpConfig:
    host: str
    port: int
    security: str  # starttls | tls | none
    username: str
    password: str
    from_name: str
    from_address: str


@dataclass
class SendResult:
    accepted: list[str] = field(default_factory=list)
    refused: dict[str, str] = field(default_factory=dict)  # address -> reason

    @property
    def fully_sent(self) -> bool:
        return not self.refused


class SmtpSendFailed(Exception):
    """User-facing: the message could not be sent at all (auth, connect,
    or every recipient refused)."""


def _build_message(
    *,
    config: SmtpConfig,
    to_addresses: list[str],
    cc_addresses: list[str],
    subject: str,
    body: str,
    attachments: list[Attachment],
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = f"{config.from_name} <{config.from_address}>"
    message["To"] = ", ".join(to_addresses)
    if cc_addresses:
        message["Cc"] = ", ".join(cc_addresses)
    message["Subject"] = subject
    message.set_content(body)

    for attachment in attachments:
        maintype, _, subtype = attachment.mime_type.partition("/")
        message.add_attachment(
            attachment.content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=attachment.filename,
        )
    return message


async def send(
    config: SmtpConfig,
    *,
    to_addresses: list[str],
    cc_addresses: list[str],
    subject: str,
    body: str,
    attachments: list[Attachment],
) -> SendResult:
    """Raises SmtpSendFailed only when nothing could be delivered at all
    (auth failure, can't connect, every recipient refused). A partial
    accept/refuse split comes back as a SendResult instead of an
    exception -- O8: never collapsed to a single pass/fail bit."""
    message = _build_message(
        config=config,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        subject=subject,
        body=body,
        attachments=attachments,
    )
    all_recipients = to_addresses + cc_addresses
    try:
        _, _ = await aiosmtplib.send(
            message,
            hostname=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            use_tls=config.security == "tls",
            start_tls=config.security == "starttls",
            timeout=30,
        )
        return SendResult(accepted=all_recipients, refused={})
    except aiosmtplib.errors.SMTPRecipientsRefused as exc:
        refused = {r.recipient: str(r.error) for r in exc.recipients}
        accepted = [addr for addr in all_recipients if addr not in refused]
        if not accepted:
            raise SmtpSendFailed("Every recipient was refused by the mail server.") from exc
        return SendResult(accepted=accepted, refused=refused)
    except aiosmtplib.errors.SMTPException as exc:
        raise SmtpSendFailed(str(exc)) from exc


async def verify(config: SmtpConfig) -> None:
    """A lightweight connect-and-authenticate check, no message sent.
    Raises SmtpSendFailed on any failure with a user-facing message."""
    try:
        client = aiosmtplib.SMTP(
            hostname=config.host,
            port=config.port,
            use_tls=config.security == "tls",
            start_tls=config.security == "starttls",
            timeout=15,
        )
        async with client:
            await client.login(config.username, config.password)
    except aiosmtplib.errors.SMTPException as exc:
        raise SmtpSendFailed(str(exc)) from exc
