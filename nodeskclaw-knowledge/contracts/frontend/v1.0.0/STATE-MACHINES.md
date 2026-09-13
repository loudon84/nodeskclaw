# Frontend State Machines — Contract v1.0.0

## KnowledgeBase

`provisioning -> active | degraded | error -> deleting`

## SourceFile

`pending -> active | updating | error -> deleting`

Archive is represented by `archived_at`, not a new SourceFileStatus enum.

## ParseStatus

`pending -> parsing -> active | failed`
Historical version: `superseded`

## IngestionJob

`pending -> uploading -> ragflow_uploaded -> metadata_synced -> parse_dispatched -> parsing -> validating -> active`

Exceptional:
- `upload_unknown`
- `failed`
- `cancelled`

## IndexState

Build:
`not_built | building | ready | stale | failed | unsupported`

Retrieval:
`unavailable | ready | degraded | unsupported`

Frontend production-ready test:

```text
build_status == ready && retrieval_status == ready
```

## BuildJob

`queued -> running -> completed | partial | failed | cancelled`

## RetrievalProfile

`draft -> active -> archived`

## Application

`draft -> active -> disabled`

Only stable promotion makes the application active in release mode.

## ApplicationRelease

`draft -> validating -> validated | failed -> retired`

Legacy DB values `promoted` / `superseded` may exist but are not frontend channel authority.

## ReleaseChannel

`preview` and `stable` each own an `active_release_id`.

## Retrieval response

`success | empty | degraded`

Transport/service faults use HTTP errors rather than a success status.
