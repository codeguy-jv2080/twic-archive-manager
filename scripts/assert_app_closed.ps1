function Assert-TwicAppClosed {
    $runningApps = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.Name -in @('TWIC Archive Manager.exe', 'twic_archive_manager.exe') -or
        ($_.Name -match '^pythonw?\.exe$' -and
         $_.CommandLine -match 'twic_archive_manager|twic-archive-manager| -m app( |$)')
    })
    if ($runningApps.Count -gt 0) {
        throw 'TWIC Archive Manager is running. Close it, then run the build again. No application will be closed automatically.'
    }
}

function Assert-TwicBuildTarget {
    param([string]$ProjectRoot, [string]$Target)
    $resolvedTarget = [System.IO.Path]::GetFullPath($Target)
    if (-not $resolvedTarget.StartsWith($ProjectRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Build target is outside the project: $resolvedTarget"
    }
    if (Test-Path -LiteralPath $resolvedTarget) {
        $targetItem = Get-Item -LiteralPath $resolvedTarget -Force
        if ($targetItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "Build target is a linked folder: $resolvedTarget"
        }
    }
}
