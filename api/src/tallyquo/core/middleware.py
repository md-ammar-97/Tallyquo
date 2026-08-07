import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from tallyquo.core.logging import bind_request_context, clear_request_context

REQUEST_ID_HEADER = "X-Request-Id"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Step 1 of the request lifecycle (architecture.md §4): assign a request
    ID and bind it to the logging context before anything else runs.

    `tenant_id` is bound here as None and re-bound once authentication
    resolves it (Phase 1) — every log line for this request exists from the
    first line, tenant_id just starts empty rather than absent.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        bind_request_context(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
