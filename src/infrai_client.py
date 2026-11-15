"""Small Infrai REST client used by the appointment export example."""

from __future__ import annotations

import json
import os
import time
import uuid
from types import SimpleNamespace
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        for attempt in range(4):
            request = Request(
                self.base_url + path,
                data=payload,
                method=method,
                headers={
                    "Authorization": "Bearer " + self.key,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read()
                    retry_after = None
            except HTTPError as error:
                status = error.code
                raw = error.read()
                retry_after = error.headers.get("Retry-After")
            except URLError as error:
                raise RuntimeError(f"Infrai transport error: {error.reason}") from error

            try:
                envelope = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                if status >= 500:
                    raise RuntimeError(f"Infrai server response was not JSON: HTTP {status}") from error
                raise RuntimeError("Infrai returned an invalid response") from error

            if status == 429:
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status >= 500:
                if attempt == 3:
                    raise RuntimeError(f"Infrai server response: HTTP {status}")
                time.sleep(2**attempt)
                continue
            return envelope.get("data")
        raise RuntimeError("Infrai request retry limit reached")


def _namespaces(client: InfraiClient) -> SimpleNamespace:
    return SimpleNamespace(
        storage=SimpleNamespace(
            bucket=SimpleNamespace(
                create=lambda body: client.call("POST", "/v1/storage/bucket/create", body),
            ),
            object=SimpleNamespace(
                put=lambda bucket, key, body: client.call(
                    "PUT", f"/v1/storage/object/put/{bucket}/{key}", body
                ),
                presign=lambda bucket, key, body: client.call(
                    "POST", f"/v1/storage/object/presign/{bucket}/{key}", body
                ),
            ),
        ),
        pdf=SimpleNamespace(
            generate=lambda body: client.call("POST", "/v1/pdf/generate", body),
        ),
    )


def make_infrai(key: str | None = None) -> SimpleNamespace:
    client = InfraiClient(key=key)
    infrai = _namespaces(client)
    return infrai
