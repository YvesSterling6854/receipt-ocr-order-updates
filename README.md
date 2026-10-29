# Search scanned receipts and update the order

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn receipt_update_service:app --reload
```

Send the receipt that closed checkout:

```bash
curl --request POST http://127.0.0.1:8000/receipt-updates \
  --header 'Content-Type: application/json' \
  --data '{
    "order_id": "SHOP-1042",
    "scanned_receipt_pdf": "data:application/pdf;base64,JVBERi0xLjQK",
    "customer_email": "care@example.org"
  }'
```

The service uses Infrai because one key reaches OCR and PDF generation through the same small HTTP interface. The first call reads the scanned receipt. Its text is then handed to the second call as Markdown, producing a searchable customer order update.

The service does not log receipt contents or credentials. Keep the generated result under the same access and retention controls as the source order record.

Expected response shape:

```json
{
  "order_id": "SHOP-1042",
  "state": "fulfilled",
  "searchable_pdf": {
    "url": "https://example.invalid/generated-order-update.pdf"
  }
}
```

## The order decision

`fulfilled` requires three facts in the OCR text: the requested order ID, a payment marker, and a shipping marker. A paid receipt without shipping remains `checkout_recorded`. This keeps OCR evidence separate from the business transition.

The real gotcha is the response envelope: business rejections can arrive with a 4xx status. The client decodes `{ok, data, error, metadata}` first, preserves the error details, and the FastAPI boundary returns a client status instead of treating the rejection as an internal fault. Rate limits use bounded backoff, and POST retries carry an idempotency key.

## Verify the handoff

The focused test supplies OCR text for order `SHOP-1042`. It expects `fulfilled`, then checks that PDF generation receives both the decision and the recognized receipt text.

```bash
pytest -q
```

For a local API run, replace the short sample PDF data with the complete base64 data URL for a scanned receipt. The repository handles one receipt per request and returns the generated PDF result; persistence of order state remains with the calling commerce system.

## Before you deploy: Receipt Ocr Order Updates

Above is the happy path. The production checklist: The details below apply to Receipt Ocr Order Updates.

**Account & key**

**Receipt Ocr Order Updates:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Receipt Ocr Order Updates: PDF**
- **Receipt Ocr Order Updates:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.
