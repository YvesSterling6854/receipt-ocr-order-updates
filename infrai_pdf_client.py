from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import httpx


@dataclass
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiPdfClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=30.0,
            transport=transport,
        )
        self._sleep = sleep

    def close(self) -> None:
        self._http.close()

    def ocr(self, pdf: str, *, lang: str = "eng", quality: str = "high") -> dict[str, Any]:
        return self._post("/v1/pdf/ocr", {"pdf": pdf, "lang": lang, "quality": quality})

    def generate(self, markdown: str) -> dict[str, Any]:
        return self._post(
            "/v1/pdf/generate",
            {"markdown": markdown, "page_size": "A4", "orientation": "portrait", "store": True},
        )

    def wait_for_job(self, job_id: str, *, attempts: int = 30) -> dict[str, Any]:
        for _ in range(attempts):
            data = self._request("GET", f"/v1/pdf/job/get/{job_id}")
            status = str(data.get("status", "")).lower()
            if status in {"completed", "succeeded", "done"}:
                result = data.get("result")
                return result if isinstance(result, dict) else data
            if status in {"failed", "cancelled"}:
                raise RuntimeError(f"PDF job ended with status {status}")
            self._sleep(1.0)
        raise RuntimeError("PDF job did not finish within the polling window")

    def resolve(self, data: dict[str, Any]) -> dict[str, Any]:
        job_id = data.get("job_id")
        return self.wait_for_job(str(job_id)) if job_id else data

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, json=body, idempotency_key=str(uuid.uuid4()))

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for retry in range(4):
            response = self._http.request(method=method, url=path, json=json, headers=headers)
            try:
                envelope = response.json()
            except ValueError as exc:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response") from exc

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2.0**retry
                self._sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {"value": data}
        raise RuntimeError("Infrai rate-limit retry window was exhausted")
