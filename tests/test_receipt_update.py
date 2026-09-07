from typing import Any

from receipt_update_service import ReceiptUpdateRequest, process_receipt


class RecordingPdfClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[str, str]] = []

    def ocr(self, pdf: str) -> dict[str, Any]:
        self.calls.append(("ocr", pdf))
        return {"job_id": "ocr-job"}

    def generate(self, markdown: str) -> dict[str, Any]:
        self.calls.append(("generate", markdown))
        return {"job_id": "generate-job"}

    def resolve(self, data: dict[str, Any]) -> dict[str, Any]:
        if data["job_id"] == "ocr-job":
            return {"text": self.text}
        return {"url": "https://documents.example/order-update.pdf"}


def test_paid_shipped_receipt_marks_order_fulfilled_and_generates_searchable_update() -> None:
    client = RecordingPdfClient("Order SHOP-1042\nPayment received\nShipped")
    request = ReceiptUpdateRequest(
        order_id="SHOP-1042",
        scanned_receipt_pdf="data:application/pdf;base64,JVBERi0xLjQK",
        customer_email="care@example.org",
    )

    result = process_receipt(request, client)  # type: ignore[arg-type]

    assert result.state == "fulfilled"
    assert result.searchable_pdf["url"].endswith("order-update.pdf")
    assert [name for name, _ in client.calls] == ["ocr", "generate"]
    assert "Status: fulfilled" in client.calls[1][1]
    assert "Payment received" in client.calls[1][1]


def test_receipt_without_shipping_keeps_checkout_recorded() -> None:
    client = RecordingPdfClient("Order SHOP-1042\nPayment received")
    request = ReceiptUpdateRequest(
        order_id="SHOP-1042",
        scanned_receipt_pdf="data:application/pdf;base64,JVBERi0xLjQK",
        customer_email="care@example.org",
    )

    result = process_receipt(request, client)  # type: ignore[arg-type]

    assert result.state == "checkout_recorded"
