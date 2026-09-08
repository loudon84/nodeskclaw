# RM-18 live-attachment-ack

This package is a dedicated live fixture. It is not a production skill.
Installing `SKILL.md` onto Hermes is required, but Catalog `supportsAttachments=true` only appears after a **published** Release whose `extra_metadata.supportsAttachments` is true, and only for `user_jwt` callers.

Expected MCP tool name when the Hermes agent profile is `marketing`:

```
hermes_marketing__live-attachment-ack
```

Set that value as `RM18_TOOL_NAME` before re-running `python tools/acceptance/run_rm18_live_attachment.py`.

## 1. Install onto Hermes

Zip path: `tools/acceptance/fixtures/rm18-live-attachment-ack.zip`.

Replace `marketing` / `default` if your agent profile or Hermes profile differs. Existing Catalog name `hermes_marketing__customer-profiling` means agent profile is `marketing`.

```powershell
$base = $env:RM13_BACKEND_BASE_URL.TrimEnd("/")
$jwt = $env:RM13_USER_JWT
$org = $env:RM13_ORG_ID
$zip = "e:\git\nodeskclaw\tools\acceptance\fixtures\rm18-live-attachment-ack.zip"
$agent = "marketing"
$profile = "default"
$headers = @{
  Authorization = "Bearer $jwt"
  "X-Org-Id" = $org
}

$upload = curl.exe -sS -X POST "$base/api/v1/hermes/agents/$agent/profiles/$profile/skills/upload" `
  -H "Authorization: Bearer $jwt" `
  -H "X-Org-Id: $org" `
  -F "file=@$zip"
$upload
$installed = ($upload | ConvertFrom-Json).data.installed_path

curl.exe -sS -X POST "$base/api/v1/hermes/agents/$agent/profiles/$profile/skills/rescan" `
  -H "Authorization: Bearer $jwt" `
  -H "X-Org-Id: $org"
```

If `register-to-org-mcp` later returns `errors.hermes.runtime_skill_not_found`, Hermes API Server has not listed the new skill yet. Restart that Hermes container, wait, then retry register. Do not guess another production skill's metadata.

## 2. Register to org MCP

```powershell
$regRaw = curl.exe -sS -X POST "$base/api/v1/hermes/agents/$agent/skills/live-attachment-ack/register-to-org-mcp" `
  -H "Authorization: Bearer $jwt" `
  -H "X-Org-Id: $org" `
  -H "Content-Type: application/json" `
  -d "{\"profile_id\":\"$profile\",\"workspace_id\":null,\"is_mcp_exposed\":true}"
$regRaw
$reg = $regRaw | ConvertFrom-Json
$skillDbId = $reg.data.skill_db_id
$skillId = $reg.data.tool_name
```

## 3. Mark attachments on the published Catalog row

Runtime Skill 没有 Hub `canonical_path`。不要为了 `supportsAttachments` 再 publish 1.0.1。

`PATCH /api/v1/hermes/skills/{id}` 会把 `extra_metadata.supportsAttachments` 写到工作副本，并同步到当前 published Release（需 Backend 含 `sync_runtime_published_catalog_extra`）。

```powershell
powershell -NoProfile -File tools/acceptance/fixtures/rm18-live-attachment-ack/publish-attachments-flag.ps1
```

Do **not** paste JSON into `curl.exe` from PowerShell. `{` is a script block.

If live Backend 还没有这次 PATCH 同步，Catalog 仍读旧 Release extra。把 Backend 部署后再跑脚本，或直接把 published Release 的 `extra_metadata.supportsAttachments` 写成 true。

## 4. Point the live runner at this tool

```powershell
$env:RM18_TOOL_NAME = $skillId
python tools/acceptance/run_rm18_live_attachment.py
```

`tools/list` must show this tool with `supportsAttachments: true` under the same `user_jwt`. Connector auth cannot make it true.

Live Backend must already include Public `POST /api/v1/attachments` and Catalog honesty. `SKILL_AGENT_INTERNAL_TOKEN` must be the real Agent token, not a placeholder.
