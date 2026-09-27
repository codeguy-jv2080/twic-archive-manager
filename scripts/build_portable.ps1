param(
    [string]$Python = (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe")
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'assert_app_closed.ps1')
Assert-TwicAppClosed

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = (Resolve-Path $Python).Path
$iconPath = Join-Path $projectRoot ".venv\Lib\site-packages\PySide6\scripts\deploy_lib\pyside_icon.ico"
$distRoot = Join-Path $projectRoot "dist"
$deploymentRoot = Join-Path $projectRoot "deployment"
$stagedFolder = Join-Path $deploymentRoot "twic_archive_manager.dist"
$portableFolder = Join-Path $distRoot "TWIC Archive Manager"
$generatedExecutable = Join-Path $stagedFolder "TWIC Archive Manager.exe"

foreach ($target in @($deploymentRoot, $stagedFolder, $portableFolder)) {
    Assert-TwicBuildTarget -ProjectRoot $projectRoot -Target $target
}

if (-not (Test-Path -LiteralPath $iconPath)) {
    throw "PySide6 deployment icon not found: $iconPath"
}

$oldCacheDirectory = $env:NUITKA_CACHE_DIR
Push-Location $projectRoot
try {
    New-Item -ItemType Directory -Force -Path $distRoot | Out-Null
    if (Test-Path -LiteralPath $deploymentRoot) {
        Remove-Item -LiteralPath $deploymentRoot -Recurse -Force
    }

    $env:NUITKA_CACHE_DIR = Join-Path $projectRoot "build\nuitka-cache"
    $outputDirectoryOption = "--output-dir=$deploymentRoot"
    $outputNameOption = "--output-filename=TWIC Archive Manager.exe"
    $iconOption = "--windows-icon-from-ico=$iconPath"
    & $pythonPath -m nuitka `
        "$projectRoot\twic_archive_manager.py" `
        --follow-imports `
        --enable-plugin=pyside6 `
        $outputDirectoryOption `
        $outputNameOption `
        --standalone `
        --windows-console-mode=disable `
        --noinclude-qt-translations `
        --noinclude-dlls=*.cpp.o `
        --noinclude-dlls=*.qsb `
        $iconOption `
        --include-qt-plugins=platforminputcontexts `
        --assume-yes-for-downloads
    $deployExitCode = $LASTEXITCODE

    if ($deployExitCode -ne 0 -or -not (Test-Path -LiteralPath $generatedExecutable)) {
        throw "Qt deployment did not produce $generatedExecutable"
    }

    Assert-TwicAppClosed
    if (Test-Path -LiteralPath $portableFolder) {
        Remove-Item -LiteralPath $portableFolder -Recurse -Force
    }
    Move-Item -LiteralPath $stagedFolder -Destination $portableFolder

    # Preserve the project's license documents and bundled runtime notices.
    Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE") -Destination $portableFolder
    Copy-Item -LiteralPath (Join-Path $projectRoot "THIRD_PARTY_NOTICES.md") -Destination $portableFolder
    $portableLicenses = Join-Path $portableFolder "licenses"
    New-Item -ItemType Directory -Force -Path $portableLicenses | Out-Null
    Copy-Item -LiteralPath (Join-Path $projectRoot "licenses\LGPL-3.0.txt") -Destination $portableLicenses
    Copy-Item -LiteralPath (Join-Path $projectRoot "licenses\Python-LICENSE.txt") -Destination $portableLicenses
}
finally {
    if ($null -eq $oldCacheDirectory) {
        Remove-Item Env:NUITKA_CACHE_DIR -ErrorAction SilentlyContinue
    }
    else {
        $env:NUITKA_CACHE_DIR = $oldCacheDirectory
    }
    Pop-Location
}

Write-Host "Built: $projectRoot\dist\TWIC Archive Manager\TWIC Archive Manager.exe"
