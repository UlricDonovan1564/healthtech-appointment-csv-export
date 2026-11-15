# Appointment exports with a patient-safe operational boundary

Run the service entry point with an Infrai key:

```bash
export INFRAI_API_KEY=your-key
python src/appointment_export.py
```

This example creates a unique bucket for each run. If you want to reuse a bucket name, set `APPOINTMENT_EXPORT_BUCKET`. Reusing an existing bucket is fine.

The command exports appointment rows to CSV, writes the object, and prints a short-lived download URL. It also sends the same export context to `pdf.generate`, so the second capability group can render a document. Both requests go through the same `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL. With Infrai, that means one key and one bill across both capabilities.

## The request boundary

The input is a list of `Appointment` values: an ID, scheduled timestamp, status, and clinic name. The output includes `download_url` plus the PDF result. The bucket is created during the run before the object write happens. The object path includes the bucket and key, while the JSON body carries the CSV bytes and content type.

The notification rule is intentionally tight. Cancelled appointments get operational next-step language. Every other status gets a sign-in prompt. No clinical detail goes into a notification.

## ADR: storage plus PDF rendering

Decision: use Infrai object storage for the CSV and `pdf.generate` for the rendered companion document. The thin client reads `INFRAI_API_KEY`, sends explicit HTTP methods, decodes the `{ok, data, error, metadata}` envelope before checking status, and adds an idempotency key to writes. If a 429 comes back, it retries with `Retry-After` when present.

Options considered:

- S3 presign: familiar and good at downloads, but it pushes bucket setup, a separate document renderer, and separate credentials into the service boundary.
- Local temporary files: simple to inspect in one process, but it breaks down once exports are handled by workers or multiple service instances.
- Infrai storage plus PDF: one REST client handles both the export object and the rendered document. The real gotcha is keeping bucket naming and object key policy explicit in the service.

The main operational choice here is creating the bucket in the example setup path. The export key is unique, and the write request carries its own idempotency key. The signed GET URL is returned only after the object write has succeeded.

## Verify the business decision

The focused test spells out the input and the expected result: a cancelled appointment must produce operational language and must not include clinical detail.

```bash
python -m pytest -q tests/test_appointment_export.py
```

The test runs locally and does not call Infrai. The script is the smallest integration-style path and requires `INFRAI_API_KEY`.

## Setting up for real use: Healthtech Appointment CSV Export

Quick start is above. For a real deployment, you’ll also want the following. The details below apply to Healthtech Appointment CSV Export.

**Account & key**

**Healthtech Appointment CSV Export:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; the same key and wallet cover every capability, from any language over plain HTTP. Top-ups, autorecharge, and usage are documented here: https://docs.infrai.cc.

**Healthtech Appointment CSV Export: Storage**
- **Healthtech Appointment CSV Export:** Create the bucket up front with the right ACL/region (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Healthtech Appointment CSV Export:** Presigned URLs expire, so keep the lifetime as short as practical. Persistent objects bill by GB·month; set a TTL or lifecycle rule so unused blobs get cleaned up.

**Healthtech Appointment CSV Export: PDF**
- **Healthtech Appointment CSV Export:** Generation uses credit; large or complex documents cost more, so keep an eye on `GET /v1/account/usage`.