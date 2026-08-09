[CmdletBinding()]
param(
    [ValidateSet('Launch', 'Backend', 'Frontend', 'Admin')]
    [string]$Mode = 'Launch'
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$configPath = Join-Path $PSScriptRoot 'dev_local.config.ps1'

if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "Missing local config: $configPath. Copy dev_local.config.example.ps1 and fill in the local values."
}

. $configPath

if (-not ($DevLocalConfig -is [hashtable])) {
    throw "`$DevLocalConfig must be a hashtable in $configPath"
}

function Get-RequiredConfigValue {
    param([Parameter(Mandatory)][string]$Name)

    if (-not $DevLocalConfig.ContainsKey($Name)) {
        throw "Missing config value: $Name"
    }
    $value = [string]$DevLocalConfig[$Name]
    if ([string]::IsNullOrWhiteSpace($value) -or $value -eq 'CHANGE_ME') {
        throw "Please fill '$Name' in $configPath"
    }
    return $value
}

function Set-DatabaseEnvironment {
    $env:TEXTRPG_STORAGE_BACKEND = 'postgres'
    $env:TEXTRPG_POSTGRES_DSN = Get-RequiredConfigValue -Name 'PostgresDsn'
}

function Clear-LlmEnvironment {
    # LLM credentials are intentionally administered through the backend UI.
    $llmEnvironmentNames = @(
        'OPENAI_API_KEY',
        'OPENAI_BASE_URL',
        'OPENAI_MODEL',
        'OPENAI_EMBEDDING_MODEL'
    )
    foreach ($environmentName in $llmEnvironmentNames) {
        Remove-Item -LiteralPath "Env:$environmentName" -ErrorAction SilentlyContinue
    }
}

function Set-BackendEnvironment {
    Set-DatabaseEnvironment

    $env:TEXTRPG_PACK_STORAGE_BACKEND = 'oss'
    $env:TEXTRPG_OSS_ENDPOINT = Get-RequiredConfigValue -Name 'OssEndpoint'
    $env:TEXTRPG_OSS_BUCKET = Get-RequiredConfigValue -Name 'OssBucket'
    $env:TEXTRPG_OSS_ACCESS_KEY_ID = Get-RequiredConfigValue -Name 'OssAccessKeyId'
    $env:TEXTRPG_OSS_ACCESS_KEY_SECRET = Get-RequiredConfigValue -Name 'OssAccessKeySecret'
    $env:TEXTRPG_OSS_REGION = Get-RequiredConfigValue -Name 'OssRegion'
    $env:TEXTRPG_OSS_PREFIX = Get-RequiredConfigValue -Name 'OssPrefix'

    Clear-LlmEnvironment
}

function Test-HttpEndpoint {
    param([Parameter(Mandatory)][string]$Uri)

    try {
        $requestParams = @{
            Uri         = $Uri
            Method      = 'Get'
            TimeoutSec  = 2
            ErrorAction = 'Stop'
        }
        $response = Invoke-WebRequest @requestParams
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Start-WorkerWindow {
    param(
        [Parameter(Mandatory)][ValidateSet('Backend', 'Frontend', 'Admin')]
        [string]$WorkerMode
    )

    $shellExe = (Get-Process -Id $PID).Path
    $nativeArgs = @(
        '-NoLogo'
        '-NoProfile'
        '-NoExit'
        '-File'
        $PSCommandPath
        '-Mode'
        $WorkerMode
    )

    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $shellExe
    $processInfo.WorkingDirectory = $projectRoot
    $processInfo.UseShellExecute = $true
    foreach ($nativeArg in $nativeArgs) {
        $processInfo.ArgumentList.Add($nativeArg)
    }
    [void][System.Diagnostics.Process]::Start($processInfo)
}

if ($Mode -eq 'Backend') {
    Set-BackendEnvironment
    $pythonExe = Get-RequiredConfigValue -Name 'PythonExe'
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        throw "Python executable not found: $pythonExe"
    }

    $backendHost = Get-RequiredConfigValue -Name 'BackendHost'
    $backendPort = Get-RequiredConfigValue -Name 'BackendPort'
    $nativeArgs = @(
        '-m'
        'uvicorn'
        'backend.main:app'
        '--reload'
        '--host'
        $backendHost
        '--port'
        $backendPort
    )

    Write-Host "Starting backend at http://${backendHost}:${backendPort}" -ForegroundColor Cyan
    Set-Location -LiteralPath $projectRoot
    & $pythonExe @nativeArgs
    exit $LASTEXITCODE
}

if ($Mode -eq 'Frontend') {
    $backendPort = Get-RequiredConfigValue -Name 'BackendPort'
    $frontendHost = Get-RequiredConfigValue -Name 'FrontendHost'
    $frontendPort = Get-RequiredConfigValue -Name 'FrontendPort'
    $apiBaseUrl = "http://127.0.0.1:$backendPort"
    $env:NEXT_PUBLIC_API_BASE_URL = $apiBaseUrl
    $env:API_BASE_URL = $apiBaseUrl

    $npmCommand = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
    if ($null -eq $npmCommand) {
        throw 'npm.cmd was not found. Install Node.js and reopen PowerShell.'
    }

    $frontendRoot = Join-Path $projectRoot 'frontend'
    $nativeArgs = @(
        'run'
        'dev'
        '--'
        '--hostname'
        $frontendHost
        '--port'
        $frontendPort
    )

    Write-Host "Starting frontend at http://${frontendHost}:${frontendPort}" -ForegroundColor Cyan
    Set-Location -LiteralPath $frontendRoot
    & $npmCommand.Source @nativeArgs
    exit $LASTEXITCODE
}

if ($Mode -eq 'Admin') {
    Set-DatabaseEnvironment
    Clear-LlmEnvironment
    $pythonExe = Get-RequiredConfigValue -Name 'PythonExe'
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        throw "Python executable not found: $pythonExe"
    }

    $adminHost = Get-RequiredConfigValue -Name 'AdminHost'
    $adminPort = Get-RequiredConfigValue -Name 'AdminPort'
    $nativeArgs = @(
        '-m'
        'streamlit'
        'run'
        'scripts/admin_billing_console.py'
        '--server.address'
        $adminHost
        '--server.port'
        $adminPort
        '--server.headless'
        'true'
    )

    Write-Host "Starting admin console at http://${adminHost}:${adminPort}" -ForegroundColor Cyan
    Set-Location -LiteralPath $projectRoot
    & $pythonExe @nativeArgs
    exit $LASTEXITCODE
}

# Launcher mode: validate private configuration before opening worker windows.
Set-BackendEnvironment
$pythonExe = Get-RequiredConfigValue -Name 'PythonExe'
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "Python executable not found: $pythonExe"
}

$npmCommand = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
if ($null -eq $npmCommand) {
    throw 'npm.cmd was not found. Install Node.js and reopen PowerShell.'
}

$frontendRoot = Join-Path $projectRoot 'frontend'
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules') -PathType Container)) {
    Write-Host 'Installing frontend dependencies...' -ForegroundColor Yellow
    Push-Location -LiteralPath $frontendRoot
    try {
        & $npmCommand.Source 'install'
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

$backendPort = Get-RequiredConfigValue -Name 'BackendPort'
$frontendPort = Get-RequiredConfigValue -Name 'FrontendPort'
$adminPort = Get-RequiredConfigValue -Name 'AdminPort'
$backendHealthUrl = "http://127.0.0.1:$backendPort/health"
$frontendUrl = "http://127.0.0.1:$frontendPort"
$adminUrl = "http://127.0.0.1:$adminPort"
$adminHealthUrl = "$adminUrl/_stcore/health"

if (Test-HttpEndpoint -Uri $backendHealthUrl) {
    Write-Host "Backend is already running: $backendHealthUrl" -ForegroundColor Green
}
else {
    Start-WorkerWindow -WorkerMode 'Backend'
    Write-Host 'Backend window started.' -ForegroundColor Green
}

if (Test-HttpEndpoint -Uri $frontendUrl) {
    Write-Host "Frontend is already running: $frontendUrl" -ForegroundColor Green
}
else {
    Start-WorkerWindow -WorkerMode 'Frontend'
    Write-Host 'Frontend window started.' -ForegroundColor Green
}

if (Test-HttpEndpoint -Uri $adminHealthUrl) {
    Write-Host "Admin console is already running: $adminUrl" -ForegroundColor Green
}
else {
    Start-WorkerWindow -WorkerMode 'Admin'
    Write-Host 'Admin console window started.' -ForegroundColor Green
}

Write-Host ''
Write-Host "Game:    $frontendUrl" -ForegroundColor Cyan
Write-Host "API:     http://127.0.0.1:$backendPort/docs" -ForegroundColor Cyan
Write-Host "Health:  $backendHealthUrl" -ForegroundColor Cyan
Write-Host "Admin:   $adminUrl" -ForegroundColor Cyan
Write-Host 'Close the three worker windows, or press Ctrl+C in each, to stop development services.'
