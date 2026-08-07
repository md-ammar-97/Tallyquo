from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tallyquo.core.config import get_settings
from tallyquo.core.logging import configure_logging, get_logger
from tallyquo.core.middleware import RequestContextMiddleware
from tallyquo.billing.clients_router import router as clients_router
from tallyquo.billing.invoices_router import router as invoices_router
from tallyquo.billing.reports_router import router as reports_router
from tallyquo.expenses.router import router as expenses_router
from tallyquo.identity.profile_router import router as profile_router
from tallyquo.identity.router import router as identity_router
from tallyquo.tax.router import router as tax_router

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(title="Tallyquo API", version="0.1.0")
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(identity_router)
app.include_router(profile_router)
app.include_router(clients_router)
app.include_router(tax_router)
app.include_router(invoices_router)
app.include_router(reports_router)
app.include_router(expenses_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness only — no DB round trip. A tenant-scoped `/health/db` style
    check is unnecessary before there's a tenant to scope it to."""
    return {"status": "ok"}
