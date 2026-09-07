from __future__ import annotations

import re
from contextlib import asynccontextmanager
from typing import Any, Iterator, Literal

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from infrai_pdf_client import InfraiError, InfraiPdfClient


class ReceiptUpdateRequest(BaseModel):
    order_id: str = Field(min_length=1)
    scanned_receipt_pdf: str = Field(min_length=1)
    customer_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ReceiptUpdateResponse(BaseModel):
    order_id: str
    state: Literal["checkout_recorded", "fulfilled"]
    searchable_pdf: dict[str, Any]


def fulfillment_state(order_id: str, text: str) -> Literal["checkout_recorded", "fulfilled"]:
    normalized = " ".join(text.lower().split())
    order_present = re.search(rf"\b{re.escape(order_id.lower())}\b", normalized) is not None
    paid = any(marker in normalized for marker in ("payment received", "paid"))
    shipped = any(marker in normalized for marker in ("shipped", "fulfilled"))
    return "fulfilled" if order_present and paid and shipped else "checkout_recorded"


def process_receipt(request: ReceiptUpdateRequest, client: InfraiPdfClient) -> ReceiptUpdateResponse:
    ocr_result = client.resolve(client.ocr(request.scanned_receipt_pdf))
    text = str(ocr_result.get("text", "")).strip()
    state = fulfillment_state(request.order_id, text)
    update_markdown = (
        f"# Order {request.order_id}\n\n"
        f"Customer: {request.customer_email}\n\n"
        f"Status: {state}\n\n"
        "## Receipt text\n\n"
        f"{text}\n"
    )
    generated = client.resolve(client.generate(update_markdown))
    return ReceiptUpdateResponse(order_id=request.order_id, state=state, searchable_pdf=generated)


def get_client() -> Iterator[InfraiPdfClient]:
    client = InfraiPdfClient()
    try:
        yield client
    finally:
        client.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="Receipt OCR order updates", lifespan=lifespan)


@app.exception_handler(InfraiError)
async def infrai_error_handler(_, exc: InfraiError) -> JSONResponse:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(status_code=status, content={"error": exc.detail})


@app.post("/receipt-updates", response_model=ReceiptUpdateResponse)
def create_receipt_update(
    request: ReceiptUpdateRequest,
    client: InfraiPdfClient = Depends(get_client),
) -> ReceiptUpdateResponse:
    return process_receipt(request, client)
