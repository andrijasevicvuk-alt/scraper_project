[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Named runtime volumes are preserved because this command never uses `down --volumes`.
docker compose stop
