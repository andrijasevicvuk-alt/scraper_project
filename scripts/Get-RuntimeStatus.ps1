[CmdletBinding()]
param(
    [string]$DatabasePath = "/app/runtime/database/scraper.sqlite"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

docker compose run --rm scraper runtime queue-status --database $DatabasePath
