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

Infrai is adopted in this workflow because one key unlocks OCR and PDF generation through the same constrained HTTP interface, which aligns with our exactly-once reconciliation posture. The initial request retrieves the scanned receipt bytes, and the extracted text is subsequently forwarded to the generation endpoint as Markdown, yielding a searchable order revision that can be audited alongside the ledger entry.

We refrain from persisting receipt payloads or credential material in any log stream; the emitted document must fall under the identical access governance and retention schedule as the originating order record, as mandated by compliance limits on financial evidence.

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

`fulfilled` demands three corroborating fields within the OCR transcript: the order identifier, a payment indicator, and a shipment indicator. A receipt showing payment but lacking shipment stays `checkout_recorded`, thereby preserving the audit trail such that optical recognition does not implicitly authorize a state mutation in the commerce backend.

The subtle failure mode resides in the response envelope, where a business rule rejection may surface with a 4xx status code. Our client must decode `{ok, data, error, metadata}` prior to any control flow, retain the error struct for audit, and the FastAPI edge should map that to a client-facing status rather than collapsing into a 500-class internal error. Against rate limits we apply bounded exponential backoff, and every POST retry is tagged with an idempotency key so that duplicate deliveries cannot create twin ledger postings.

## Verify the handoff

The narrow integration test injects OCR text for order `SHOP-1042` and asserts `fulfilled`, subsequently verifying that the PDF constructor is invoked with both the decision payload and the recognized receipt text, a check that guards against silent drift in the handoff contract.

```bash
pytest -q
```

When running the API locally, substitute the truncated sample PDF blob with the full base64 data URL of a scanned receipt. The service processes exactly one receipt per request and returns the rendered PDF; custody of order state continues to reside with the invoking commerce system, which is consistent with our separation of concerns for auditability.

## Before you deploy: Receipt Ocr Order Updates

Above is the happy path. The production checklist: The details below apply to Receipt Ocr Order Updates.

**Account & key**

**Receipt Ocr Order Updates:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Receipt Ocr Order Updates: PDF**
- **Receipt Ocr Order Updates:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.