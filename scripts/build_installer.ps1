param(
    [string]$Compiler,
    [string]$Python = (Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'),
    [switch]$SkipPortableBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $PSScriptRoot 'assert_app_closed.ps1')
Assert-TwicAppClosed

if (-not $Compiler) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    )
    $Compiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $Compiler) {
    throw 'Inno Setup 6 is required to build the installer. Install it or supply -Compiler with the path to ISCC.exe.'
}
$compilerPath = (Resolve-Path -LiteralPath $Compiler).Path

if (-not $SkipPortableBuild) {
    & (Join-Path $PSScriptRoot 'build_portable.ps1') -Python $Python
}
$portableExe = Join-Path $projectRoot 'dist\TWIC Archive Manager\TWIC Archive Manager.exe'
if (-not (Test-Path -LiteralPath $portableExe)) {
    throw "Build the portable app first: $portableExe"
}
$allowedDocumentationNames = @('LICENSE', 'THIRD_PARTY_NOTICES.md', 'LGPL-3.0.txt')
$unexpectedFiles = @(Get-ChildItem -LiteralPath (Split-Path $portableExe) -Recurse -File -Force |
    Where-Object {
        $_.Extension -notin @('.exe', '.dll', '.pyd') -and
        $_.Name -notin $allowedDocumentationNames
    })
if ($unexpectedFiles.Count -gt 0) {
    throw 'The portable build contains unexpected non-program files. Installer packaging stopped; no user data or settings may be included.'
}

$projectText = Get-Content -LiteralPath (Join-Path $projectRoot 'pyproject.toml') -Raw
$versionMatch = [regex]::Match($projectText, '(?m)^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
if (-not $versionMatch.Success) { throw 'Cannot read the app version from pyproject.toml.' }
$version = $versionMatch.Groups[1].Value
& $compilerPath "/DProjectRoot=$projectRoot" "/DAppVersion=$version" (Join-Path $projectRoot 'installer\TWIC Archive Manager.iss')
if ($LASTEXITCODE -ne 0) { throw "Installer compiler failed with exit code $LASTEXITCODE." }
Write-Output "Built installer: $projectRoot\dist\TWIC-Archive-Manager-Setup.exe"
Write-Output "Portable launch unchanged: $portableExe"
