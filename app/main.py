from fastapi import FastAPI

from app.api.v1.payments import router as payments_router

app = FastAPI(title="Payment Service", version="0.1.0")
app.include_router(payments_router, prefix="/api/v1")
