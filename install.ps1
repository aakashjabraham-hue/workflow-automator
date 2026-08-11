# workflow-automator — one-liner installer (Windows / PowerShell)
#
# Downloads the latest from GitHub, installs it, then hands off to the
# interactive wizard (daemon setup + summary).  Everything comes fresh
# from GitHub so you always get the newest version.
#
# Usage (PowerShell 5.1+):
#   irm https://raw.githubusercontent.com/aakashjabraham-hue/workflow-automator/master/install.ps1 | iex

$ErrorActionPreference = "Stop"

$repo  = "aakashjabraham-hue/workflow-automator"
$branch = "master"
$base  = Join-Path $env:LOCALAPPDATA "workflow-automator"
$bin   = Join-Path $base "bin"
$cur   = Join-Path $base "current"
$tmp   = Join-Path $env:TEMP ("workflow-automator-install-" + [guid]::NewGuid().ToString("N"))
$zip   = Join-Path $tmp "wa.zip"

New-Item -ItemType Directory -Force -Path $base, $bin | Out-Null
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

Write-Host "  Downloads latest workflow-automator..."
$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest -UseBasicParsing -Uri "https://codeload.github.com/$repo/zip/refs/heads/$branch" -OutFile $zip
$ProgressPreference = 'Continue'

Write-Host "  Extracting..."
Expand-Archive -Path $zip -DestinationPath $tmp -Force

# GitHub zips wrap everything in a single top-level folder — flatten it.
$inner = Get-ChildItem -Path $tmp -Directory | Where-Object { $_.Name -ne "__MACOSX" } | Select-Object -First 1
if (Test-Path $cur) { Remove-Item -Recurse -Force $cur }
Move-Item $inner.FullName $cur

# Write the .cmd launcher shim.
$shimPath = Join-Path $bin "workflow-automator.cmd"
$launcher = Join-Path $cur "launcher.py"
@"
@echo off
py -3 "$launcher" %*
"@ | Set-Content -Path $shimPath -Encoding ASCII
Write-Host "  Installed launcher -> $shimPath"

# Make sure the bin dir is on the user PATH.
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$bin*") {
    [Environment]::SetEnvironmentVariable("Path", ($userPath.TrimEnd(';') + ";" + $bin), "User")
    Write-Host "  Added $bin to your user PATH - open a NEW terminal for it to take effect."
}

Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "  Running the setup wizard..."
& (Join-Path $bin "workflow-automator.cmd") install --skip-download