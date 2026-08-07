"""Receipt OCR via Groq's qwen/qwen3.6-27b vision model (free tier).

E3: "OCR provider down | Falls straight to manual entry with no error
dialog. The upload still succeeds." Every failure mode here -- no key
configured, network error, malformed response -- returns None rather
than raising, so the caller always has a safe, silent fallback.
"""

import base64
import json
from decimal import Decimal, InvalidOperation

import httpx

from tallyquo.core.config import get_settings

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "qwen/qwen3.6-27b"

_PROMPT = (
    "Extract the vendor name, transaction date, and total amount paid from "
    "this receipt image. Respond with JSON only, no other text: "
    '{"vendor": string or null, "date": "YYYY-MM-DD" or null, '
    '"amount": string or null, "confidence": number from 0 to 1}. '
    "Use null for any field you can't read confidently. confidence reflects "
    "your certainty in the amount specifically, since that's the field "
    "that matters most if it's wrong."
)


async def extract_receipt_fields(image_bytes: bytes, mime_type: str) -> dict | None:
    settings = get_settings()
    if not settings.groq_api_key:
        return None

    b64 = base64.b64encode(image_bytes).decode("ascii")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                _GROQ_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={
                    "model": _MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": _PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                                },
                            ],
                        }
                    ],
                    "response_format": {"type": "json_object"},
                    "max_completion_tokens": 300,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError, TypeError):
        return None

    amount = None
    if parsed.get("amount") is not None:
        try:
            amount = str(Decimal(str(parsed["amount"])))
        except InvalidOperation:
            amount = None

    confidence = parsed.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = None

    return {
        "vendor": parsed.get("vendor") or None,
        "date": parsed.get("date") or None,
        "amount": amount,
        "confidence": confidence,
    }
