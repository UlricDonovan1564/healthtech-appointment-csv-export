"""Appointment CSV export and patient-safe notification policy."""

from __future__ import annotations

import base64
import csv
import io
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any

try:
    from src.infrai_client import InfraiError, make_infrai
except ModuleNotFoundError:
    from infrai_client import InfraiError, make_infrai


BUCKET_PREFIX = "appointment-exports"


@dataclass(frozen=True)
class Appointment:
    appointment_id: str
    scheduled_for: str
    status: str
    clinic: str


def notification_text(appointment: Appointment) -> str:
    if appointment.status == "cancelled":
        return "Your appointment was cancelled. Please contact the clinic for next steps."
    return "Your appointment schedule has been updated. Sign in to review the details."


def csv_bytes(appointments: list[Appointment]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=["appointment_id", "scheduled_for", "status", "clinic"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(a.__dict__ for a in appointments)
    return output.getvalue().encode("utf-8")


def export_appointments(
    appointments: list[Appointment],
    key: str | None = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    infrai = make_infrai(key)
    bucket = bucket or os.environ.get("APPOINTMENT_EXPORT_BUCKET")
    bucket = bucket or f"{BUCKET_PREFIX}-{uuid.uuid4().hex[:12]}"
    export_key = f"exports/{uuid.uuid4()}.csv"
    try:
        infrai.storage.bucket.create({"name": bucket})
    except InfraiError as error:
        if error.status != 409 and error.code not in {"BUCKET_ALREADY_EXISTS", "ALREADY_EXISTS"}:
            raise
    content = csv_bytes(appointments)
    infrai.storage.object.put(bucket, export_key, {
        "data_base64": base64.b64encode(content).decode("ascii"),
        "content_type": "text/csv",
        "idempotency_key": export_key,
    })
    download = infrai.storage.object.presign(bucket, export_key, {
        "op": "get",
        "expires_seconds": 900,
        "response_disposition": "attachment",
        "idempotency_key": export_key,
    })
    markdown = "\n".join([
        "# Appointment export",
        "",
        f"Rows: {len(appointments)}",
        "",
        "This document contains operational appointment information.",
    ])
    document = infrai.pdf.generate({
        "markdown": markdown,
        "page_size": "A4",
        "orientation": "portrait",
        "store": True,
    })
    return {"download_url": download["url"], "document": document}


def main() -> None:
    appointments = [Appointment("apt-104", "2026-10-24T09:00:00Z", "confirmed", "North Clinic")]
    print(json.dumps(export_appointments(appointments), indent=2))


if __name__ == "__main__":
    main()
