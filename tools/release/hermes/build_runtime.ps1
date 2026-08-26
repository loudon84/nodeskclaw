param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [Parameter(Mandatory = $true)][string]$Dest,
    [string]$Wheelhouse = "",
    [string]$Profile = "smc-managed",
    [string]$HermesVersion = "",
    [string]$NodeRoot = "",
    [string]$Wheel = "",
    [ValidateSet("online", "offline")][string]$Mode = "online",
    [switch]$AllowDirty
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$argsList = @(
    (Join-Path $PSScriptRoot "build_runtime.py"),
    "--repo", $Repo,
    "--dest", $Dest,
    "--profile", $Profile,
    "--mode", $Mode
)
if ($Wheelhouse) { $argsList += @("--wheelhouse", $Wheelhouse) }
if ($HermesVersion) { $argsList += @("--hermes-version", $HermesVersion) }
if ($NodeRoot) { $argsList += @("--node-root", $NodeRoot) }
if ($Wheel) { $argsList += @("--wheel", $Wheel) }
if ($AllowDirty) { $argsList += "--allow-dirty" }
& python @argsList
if ($LASTEXITCODE -ne 0) { throw "hermes runtime build failed" }
