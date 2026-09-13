# Frontend Integration Flow — Contract v1.0.0

## 1. Authentication and base URLs

Frontend authenticates against `nodeskclaw-backend`, then sends the same opaque bearer token to Knowledge.

```text
Browser
  -> Backend login/session
  -> Bearer token
  -> Knowledge API
  -> Backend /api/v1/auth/knowledge-context
  -> KnowledgePrincipal
```

The frontend must not:
- decode Knowledge authorization locally;
- call RAGFlow directly;
- hold a RAGFlow API key;
- use runtime dataset/document/chunk IDs as UI identity.

## 2. Knowledge Base management

```text
GET  /api/v2/knowledge-bases
POST /api/v2/knowledge-bases
GET  /api/v2/knowledge-bases/{kb_id}
PATCH /api/v2/knowledge-bases/{kb_id}
```

For operations that are not yet present in v2, use compatibility endpoints:

```text
DELETE /api/v1/knowledge-bases/{kb_id}
GET    /api/v1/knowledge-bases/{kb_id}/acl
POST   /api/v1/knowledge-bases/{kb_id}/acl
DELETE /api/v1/knowledge-bases/{kb_id}/acl/{acl_id}
GET    /api/v1/knowledge-bases/{kb_id}/metadata-schema
PUT    /api/v1/knowledge-bases/{kb_id}/metadata-schema
```

UI state:
- `provisioning`: show provisioning progress/disabled destructive actions.
- `active`: normal operations.
- `updating`: allow read, restrict conflicting mutations.
- `degraded`: show warning.
- `error`: show failure and recovery actions.
- `deleting`: read-only pending removal.

## 3. Document upload and ingestion

```text
POST /api/v1/knowledge-bases/{kb_id}/files
```

Multipart:
- `file`: binary
- `metadata`: JSON string

Response contains:
- `source_file`
- `file_version_id`
- `job`

Frontend then polls:

```text
GET /api/v1/ingestion-jobs/{job_id}
POST /api/v1/ingestion-jobs/{job_id}/retry
POST /api/v1/ingestion-jobs/{job_id}/cancel
```

These three paths are `stable-compat`: semantically frozen on `/api/v1`.

Terminal success is `status=active`. Terminal failure is `failed` or `cancelled`.

After ingestion becomes active, the UI should read:

```text
GET /api/v2/knowledge-bases/{kb_id}/indexes
GET /api/v2/knowledge-bases/{kb_id}/build-profile
PUT /api/v2/knowledge-bases/{kb_id}/build-profile
POST /api/v2/knowledge-bases/{kb_id}/builds
GET /api/v2/builds/{build_id}
POST /api/v2/builds/{build_id}/retry
```

Chunk is production-retrieval ready only when:

```text
chunk.build_status == "ready"
AND
chunk.retrieval_status == "ready"
```

Do not infer retrieval readiness only from build readiness.

## 4. Source file lifecycle

```text
GET    /api/v1/knowledge-bases/{kb_id}/files
GET    /api/v1/source-files/{source_file_id}
GET    /api/v1/source-files/{source_file_id}/versions
POST   /api/v1/source-files/{source_file_id}/versions
POST   /api/v1/source-files/{source_file_id}/versions/{version_id}/activate
POST   /api/v1/source-files/{source_file_id}/archive
POST   /api/v1/source-files/{source_file_id}/unarchive
POST   /api/v1/source-files/{source_file_id}/reparse
GET    /api/v1/source-files/{source_file_id}/download
GET    /api/v1/source-files/{source_file_id}/acl
POST   /api/v1/source-files/{source_file_id}/acl
DELETE /api/v1/source-files/{source_file_id}/acl/{acl_id}
DELETE /api/v1/source-files/{source_file_id}
```

The frontend must treat `active_version_id` as the document-version authority.

## 5. Knowledge Set and retrieval profile

Use v2 for the Set itself:

```text
GET    /api/v2/knowledge-sets
POST   /api/v2/knowledge-sets
GET    /api/v2/knowledge-sets/{set_id}
PATCH  /api/v2/knowledge-sets/{set_id}
POST   /api/v2/knowledge-sets/{set_id}/knowledge-bases
DELETE /api/v2/knowledge-sets/{set_id}/knowledge-bases/{kb_id}
```

Use compatibility APIs for profile lifecycle:

```text
GET   /api/v1/knowledge-sets/{set_id}/retrieval-profiles
POST  /api/v1/knowledge-sets/{set_id}/retrieval-profiles
GET   /api/v1/retrieval-profiles/{profile_id}
PATCH /api/v1/retrieval-profiles/{profile_id}
POST  /api/v1/retrieval-profiles/{profile_id}/publish
POST  /api/v1/retrieval-profiles/{profile_id}/rollback
```

Profile states: `draft | active | archived`.

## 6. Application and release

```text
GET   /api/v2/applications
POST  /api/v2/applications
GET   /api/v2/applications/{application_id}
PATCH /api/v2/applications/{application_id}

POST   /api/v2/applications/{application_id}/knowledge-sets
DELETE /api/v2/applications/{application_id}/knowledge-sets/{set_id}

GET  /api/v2/applications/{application_id}/readiness
```

Application lifecycle:

```text
draft -> active -> disabled
```

`active` means stable delivery has become usable; the UI must not infer active from a validation request alone.

## 7. Application retrieval policy

```text
GET  /api/v2/applications/{application_id}/retrieval-policy-revisions
POST /api/v2/applications/{application_id}/retrieval-policy-revisions
POST /api/v2/applications/{application_id}/retrieval-policy-revisions/{revision_id}/publish
```

Policy states: `draft | active | archived`.

## 8. Release validation and promotion

Recommended explicit flow:

```text
POST /api/v2/applications/{application_id}/releases
  -> release.status=draft

POST /api/v2/applications/{application_id}/releases/{release_id}/validate
  -> HTTP 202
  -> release.status=validating
  -> validation_job_id

GET /api/v2/builds/{validation_job_id}
  -> queued/running/completed|failed

GET /api/v2/applications/{application_id}/releases/{release_id}
  -> validated

POST /api/v2/applications/{application_id}/channels/stable/promote
  -> stable.active_release_id=release_id
  -> application.status=active

GET  /api/v2/applications/{application_id}/channels
POST /api/v2/applications/{application_id}/channels/{channel}/rollback
POST /api/v2/applications/{application_id}/releases/{release_id}/retire
POST /api/v2/applications/{application_id}/publish
POST /api/v2/applications/{application_id}/disable
```

The frontend must poll the build job. It must not immediately promote after a 202 validation response.

Channels:
- `preview`
- `stable`

## 9. Production retrieval

```text
POST /api/v2/applications/{application_id}/retrieval
```

Normal production requests resolve the stable channel/release on the server.

Frontend identity rules:
- use `evidence_id` for result/citation identity;
- never depend on `dataset_id`, `document_id`, `chunk_id`, `ragflow_*`.

Success can be:
- `status=success` with evidence-bearing chunks/results;
- `status=empty` with HTTP 200;
- `status=degraded` where policy permits partial results.

The R1 runtime closure intentionally treats “no certified semantic slice” as HTTP 200 empty instead of a false 503.

Playground (`POST /api/v2/retrieval/playground`) is in the matrix for debug UI. Trace / query-analysis fields are not frozen.

## 10. Evidence

```text
GET /api/v2/evidence/{evidence_id}
```

Evidence resolution re-authorizes the current member. A cached frontend result does not grant permanent access.

## 11. Quality and artifact UI

Feature-gated:

```text
GET  /api/v2/knowledge-bases/{kb_id}/quality
GET  /api/v2/knowledge-bases/{kb_id}/quality/history
GET  /api/v2/applications/{application_id}/quality

GET  /api/v2/knowledge-bases/{kb_id}/artifacts
GET  /api/v2/knowledge-bases/{kb_id}/artifacts/{artifact_type}
POST /api/v2/knowledge-bases/{kb_id}/artifacts/builds
GET  /api/v2/artifacts/{artifact_id}
GET  /api/v2/artifacts/{artifact_id}/content
```

Artifact build is asynchronous; use its `build_job_id` with `/api/v2/builds/{id}`.

## 12. Error handling

Every JSON API error uses:

```json
{
  "code": 40000,
  "error_code": 40000,
  "message_key": "errors.common.bad_request",
  "message": "请求参数错误",
  "data": null,
  "details": {}
}
```

Frontend behavior should be keyed primarily by:
1. HTTP status;
2. `message_key`;
3. `details`.

Do not branch on localized `message`.

## 13. Polling recommendations

The contract does not freeze exact polling intervals. Recommended UI defaults:
- ingestion/build: 1–2 s while foreground page is open;
- use exponential backoff after 15–30 s;
- stop on terminal states;
- cancel polling when the user leaves the page.
