param(
    [int]$StartOffset = 0,
    [int]$EndOffset = 2000,
    [int]$ChunkSize = 200,
    [int]$MaxFilingsPerTarget = 1,
    [string]$StartDate = "20240101",
    [string]$EndDate = "20260220",
    [switch]$IncludeQuarterly,
    [int]$SleepSecondsBetweenChunks = 2
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

for ($offset = $StartOffset; $offset -lt $EndOffset; $offset += $ChunkSize) {
    $limit = [Math]::Min($ChunkSize, $EndOffset - $offset)
    if ($limit -le 0) { break }

    Write-Host ("[DART] chunk start offset={0} limit={1}" -f $offset, $limit)

    $args = @(
        "-m", "orchestrator.run_dart_pipeline",
        "--config", "config.yaml",
        "--all-listed",
        "--target-offset", "$offset",
        "--target-limit", "$limit",
        "--max-filings", "$MaxFilingsPerTarget",
        "--start-date", "$StartDate",
        "--end-date", "$EndDate",
        "--skip-existing"
    )

    if ($IncludeQuarterly) {
        $args += "--include-quarterly"
    }

    & $pythonExe @args
    if ($LASTEXITCODE -ne 0) {
        throw ("Chunk failed at offset={0} (exit={1})" -f $offset, $LASTEXITCODE)
    }

    Start-Sleep -Seconds $SleepSecondsBetweenChunks
}

Write-Host "[DART] chunk run completed."
