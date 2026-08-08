[CmdletBinding()]
param(
    [string]$RuntimeDirectory = "/app/runtime"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

docker compose up -d fixture-server
docker compose run --rm scraper worker run-synthetic --runtime-dir $RuntimeDirectory
