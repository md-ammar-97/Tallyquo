"""Structured logging: every line carries `request_id` and, once known,
`tenant_id` (architecture.md §13). No invoice amounts or PII in application
logs — callers must not pass raw request/response bodies into log calls.
"""

import logging
import sys

import structlog

_context_vars = structlog.contextvars


def configure_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(log_level, logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_request_context(*, request_id: str, tenant_id: str | None = None) -> None:
    """Bind fields visible on every subsequent log line for this request.

    Cleared per-request by `clear_request_context` in ASGI middleware —
    contextvars are request-scoped in an async server, but clearing
    explicitly avoids ever leaking one request's tenant_id into another's
    logs under any executor reuse.
    """
    _context_vars.bind_contextvars(request_id=request_id, tenant_id=tenant_id)


def clear_request_context() -> None:
    _context_vars.clear_contextvars()
