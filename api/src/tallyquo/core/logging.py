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
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        # Route through stdlib `logging` rather than structlog's default
        # PrintLogger, which caches a direct reference to sys.stdout at
        # first use and so ignores basicConfig (and, in tests, ignores
        # capture/redirection of sys.stdout entirely -- caplog/capsys both
        # hook stdlib logging, not a raw stream reference).
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(log_level, logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(processor=structlog.processors.JSONRenderer())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)


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


def bind_tenant_context(tenant_id: str) -> None:
    """Called once auth resolves who's asking -- separate from
    `bind_request_context` so it never clobbers the request_id already
    bound by the middleware at the start of the request."""
    _context_vars.bind_contextvars(tenant_id=tenant_id)


def clear_request_context() -> None:
    _context_vars.clear_contextvars()
