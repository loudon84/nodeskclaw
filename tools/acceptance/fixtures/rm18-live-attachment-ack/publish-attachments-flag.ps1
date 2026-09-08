param(
    [string]$RuntimeSkillId = "live-attachment-ack",
    [string]$ToolName = "hermes_marketing__live-attachment-ack"
)

$ErrorActionPreference = "Stop"

function Get-RequiredEnv([string]$Name) {
    $item = Get-Item "Env:$Name" -ErrorAction SilentlyContinue
    $raw = [string]$item.Value
    if ([string]::IsNullOrWhiteSpace($raw)) {
        throw "missing environment variable: $Name"
    }
    return $raw.Trim()
}

function ConvertTo-PlainMap($value) {
    if ($null -eq $value) {
        return @{}
    }
    if ($value -is [hashtable]) {
        return $value
    }
    $map = @{}
    $value.PSObject.Properties | ForEach-Object {
        $map[$_.Name] = $_.Value
    }
    return $map
}

function Invoke-Json {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][hashtable]$Headers,
        $BodyObject
    )
    $params = @{
        Method = $Method
        Uri = $Uri
        Headers = $Headers
        TimeoutSec = 60
    }
    if ($PSBoundParameters.ContainsKey("BodyObject")) {
        $json = $BodyObject | ConvertTo-Json -Depth 16 -Compress
        $params.ContentType = "application/json; charset=utf-8"
        $params.Body = [System.Text.Encoding]::UTF8.GetBytes($json)
    }
    return Invoke-RestMethod @params
}

$base = (Get-RequiredEnv "RM13_BACKEND_BASE_URL").TrimEnd("/")
$jwt = Get-RequiredEnv "RM13_USER_JWT"
$org = Get-RequiredEnv "RM13_ORG_ID"
$headers = @{
    Authorization = "Bearer $jwt"
    "X-Org-Id" = $org
    Accept = "application/json"
}

Write-Host "GET skill list"
$list = Invoke-Json -Method GET -Uri "$base/api/v1/hermes/skills?keyword=$RuntimeSkillId" -Headers $headers
$skillRow = @($list.data.items) | Where-Object { $_.tool_name -eq $ToolName -or $_.name -eq $RuntimeSkillId } | Select-Object -First 1
if (-not $skillRow) {
    throw "skill not found in GET /hermes/skills keyword=$RuntimeSkillId"
}
$skillDbId = [string]$skillRow.id
Write-Host "skill_db_id=$skillDbId published_version=$($skillRow.published_version)"

Write-Host "GET skill"
$skill = (Invoke-Json -Method GET -Uri "$base/api/v1/hermes/skills/$skillDbId" -Headers $headers).data
$extra = ConvertTo-PlainMap $skill.extra_metadata
$extra["supportsAttachments"] = $true
$extra["interactionMode"] = "chat"
$extra["promptField"] = "prompt"

Write-Host "PATCH extra_metadata.supportsAttachments=true"
$patched = Invoke-Json -Method PATCH -Uri "$base/api/v1/hermes/skills/$skillDbId" -Headers $headers -BodyObject @{
    extra_metadata = $extra
}
$patchedExtra = ConvertTo-PlainMap $patched.data.extra_metadata
if (-not $patchedExtra.supportsAttachments) {
    throw "PATCH did not persist supportsAttachments on the skill working copy"
}

Write-Host "patched supportsAttachments=$($patchedExtra.supportsAttachments)"
Write-Host "SET RM18_TOOL_NAME=$ToolName"
$env:RM18_TOOL_NAME = $ToolName
Write-Host "done: re-run tools/list; Catalog reads the published Release extra after this PATCH on runtime skills"
