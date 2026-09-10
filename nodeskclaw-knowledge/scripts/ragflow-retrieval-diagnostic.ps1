# ==========================================================
# RAGFlow v0.27 Retrieval Diagnostic
#
# Purpose:
# Verify whether RAGFlow Dataset retrieval works independently
# from nodeskclaw-knowledge IndexState.
#
# Environment:
# Windows PowerShell 5+/7+
#
# ==========================================================


param(
    [string]$RagflowUrl = "http://192.168.102.247:9222",
    [string]$ApiKey = "ragflow-ibbZBf6GjpamSxtJVdKCjn4UADvmfsmqOzej_I7PCvM",
    [string]$DatasetId = "7b7a36aeacc111f1a0c48d3842373341",
    [string]$Query = "test document retrieval",
    [int]$TopK = 5
)


$ErrorActionPreference = "Stop"


$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

$output = ".\ragflow-retrieval-diagnostic-$timestamp.json"


$result = @{
    timestamp = $timestamp
    ragflow_url = $RagflowUrl
    dataset_id = $DatasetId
    query = $Query
    health = $null
    dataset = $null
    retrieval = $null
    errors = @()
}



function Invoke-RagflowApi {

    param(
        [string]$Path,
        [string]$Method="GET",
        [object]$Body=$null
    )


    $headers = @{}

    if ($ApiKey -ne "") {

        $headers["Authorization"] = "Bearer $ApiKey"

    }


    $url = "$RagflowUrl$Path"


    Write-Host ""
    Write-Host "REQUEST:"
    Write-Host "$Method $url"


    if ($Body) {

        $json = $Body | ConvertTo-Json -Depth 10

        Write-Host $json


        return Invoke-RestMethod `
            -Uri $url `
            -Method $Method `
            -Headers $headers `
            -ContentType "application/json" `
            -Body $json
    }
    else {

        return Invoke-RestMethod `
            -Uri $url `
            -Method $Method `
            -Headers $headers
    }

}



Write-Host ""
Write-Host "====================================="
Write-Host "RAGFlow Retrieval Diagnostic"
Write-Host "====================================="
Write-Host ""


#
# 1. Health
#

try {

    Write-Host "[1] Checking RAGFlow Health..."

    $health = Invoke-RagflowApi "/v1/system/version"


    $result.health = $health


    Write-Host "PASS"
    $health | ConvertTo-Json -Depth 10


}
catch {

    Write-Host "FAILED"

    $result.errors += $_.Exception.Message

}



#
# 2. Dataset
#

if ($DatasetId -eq "") {


    Write-Host ""

    Write-Host "[2] DatasetId missing"

    Write-Host ""
    Write-Host "Please execute:"
    Write-Host ""
    Write-Host " .\ragflow-retrieval-diagnostic.ps1 -DatasetId xxxx"
    Write-Host ""

}
else {


    try {


        Write-Host ""

        Write-Host "[2] Getting Dataset Information..."


        $dataset = Invoke-RagflowApi `
            "/api/v1/datasets/$DatasetId"


        $result.dataset = $dataset


        Write-Host "Dataset:"
        $dataset | ConvertTo-Json -Depth 20



    }
    catch {

        Write-Host "Dataset query FAILED"

        $result.errors += $_.Exception.Message

    }



    #
    # 3. Retrieval
    #

    try {


        Write-Host ""

        Write-Host "[3] Testing Retrieval..."



        $body = @{
            question = $Query
            dataset_ids = @(
                $DatasetId
            )
            top_k = $TopK
            similarity_threshold = 0.2
        }



        $retrieval = Invoke-RagflowApi `
            "/api/v1/retrieval" `
            "POST" `
            $body



        $result.retrieval = $retrieval



        Write-Host ""
        Write-Host "Retrieval Result:"
        $retrieval | ConvertTo-Json -Depth 30



        if ($retrieval.data.chunks.Count -gt 0) {

            Write-Host ""
            Write-Host "================================"
            Write-Host "RETRIEVAL READY"
            Write-Host "Chunks:"
            Write-Host $retrieval.data.chunks.Count
            Write-Host "================================"

        }
        else {

            Write-Host ""
            Write-Host "================================"
            Write-Host "RETRIEVAL EMPTY"
            Write-Host "No chunks returned"
            Write-Host "================================"

        }


    }
    catch {


        Write-Host ""

        Write-Host "Retrieval FAILED"

        $result.errors += $_.Exception.Message

    }

}



#
# Save Evidence
#

$result | ConvertTo-Json -Depth 50 |
    Out-File `
    -Encoding UTF8 `
    $output



Write-Host ""

Write-Host "====================================="
Write-Host "Diagnostic Finished"
Write-Host ""
Write-Host "Evidence:"
Write-Host $output
Write-Host "====================================="