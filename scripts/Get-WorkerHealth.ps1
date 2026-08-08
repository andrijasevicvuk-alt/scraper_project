[CmdletBinding()]
param(
    [string]$RuntimeDirectory = "/app/runtime"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

docker compose run --rm scraper worker health --runtime-dir $RuntimeDirectory
