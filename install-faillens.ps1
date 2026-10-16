<#
    FailLens - finish the GitHub first publish
    -----------------------------------------
    Run in a NORMAL (non-elevated) PowerShell window:

        powershell -NoProfile -ExecutionPolicy Bypass -File D:\testtool\install-faillens.ps1

    Add -Push to also push in the same run:

        powershell -NoProfile -ExecutionPolicy Bypass -File D:\testtool\install-faillens.ps1 -Push

    What this script does:
      1. Creates docs\assets\diagnosis-detail.png (second README figure)
      2. Refreshes .gitignore so local junk never reaches GitHub
      3. Removes test leftovers and scratch files
      4. Commits everything on top of the existing history
      5. Points origin at the GitHub repository, then pushes (with -Push)

    This file is deliberately ASCII-only: Windows PowerShell 5.1 reads .ps1
    files as the legacy ANSI code page unless they carry a UTF-8 BOM, which
    would corrupt any non-ASCII text in the console output.
#>

[CmdletBinding()]
param(
    [switch]$Push,
    [string]$AuthorName  = 'Pan Xiaoli',
    [string]$AuthorEmail = 'pmy20051018@foxmail.com',
    [string]$RemoteUrl   = 'https://github.com/xiaoli50823/FailLens.git'
)

$ErrorActionPreference = 'Stop'

$Repo         = 'D:\testtool'
$SourceShot   = Join-Path $Repo 'tmp\faillens-report.png'
$ShotTarget   = Join-Path $Repo 'docs\assets\diagnosis-detail.png'
$CropScript   = Join-Path $Repo '.crop-screenshot.py'
$Gitignore    = Join-Path $Repo '.gitignore'
$CommitMsg    = 'docs: tidy project page and add failure-diagnosis screenshot'

function Write-Step([string]$Message) {
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-Writable([string]$Path) {
    $probe = Join-Path $Path ('probe-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        Set-Content -LiteralPath $probe -Value 'x' -ErrorAction Stop
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        return $true
    }
    catch {
        return $false
    }
}

function Find-Python {
    $bundled = Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
    foreach ($candidate in @('python', $bundled)) {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    return $null
}

# --------------------------------------------------------------------------
Write-Step 'Checking prerequisites'

foreach ($pair in @(
    @{ Path = $Repo;                          Label = 'repository root' },
    @{ Path = (Join-Path $Repo '.git');       Label = '.git directory' },
    @{ Path = (Join-Path $Repo 'docs\assets'); Label = 'docs\assets directory' }
)) {
    if (-not (Test-Writable $pair.Path)) {
        throw "$($pair.Label) is not writable: $($pair.Path). Run this from your own account (xiaoli\panxiaoli)."
    }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'git was not found on PATH.'
}
Write-Host 'Directories writable, git available.' -ForegroundColor Green

# --------------------------------------------------------------------------
Write-Step 'Creating the failure-diagnosis screenshot'

if (-not (Test-Path -LiteralPath $SourceShot)) {
    throw "Source screenshot not found: $SourceShot"
}

$python = Find-Python
$cropped = $false

if ($python) {
    # Trim the empty page background so the figure has no dead space.
    $cropSource = @'
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])

try:
    import numpy as np
    from PIL import Image
except ImportError:
    raise SystemExit(3)

image = Image.open(source).convert("RGB")
pixels = np.asarray(image).astype("int16")
# The page background is a very light grey; anything differing from the
# top-left corner pixel by more than the tolerance counts as content.
delta = np.abs(pixels - pixels[0, 0]).max(axis=2)
mask = delta > 6
# Require a row/column to hold enough content pixels so page-edge rules are
# not mistaken for content and the trim stays tight.
rows = np.flatnonzero(mask.sum(axis=1) > 40)
cols = np.flatnonzero(mask.sum(axis=0) > 40)
if rows.size == 0 or cols.size == 0:
    raise SystemExit(4)

margin = 24
box = (
    max(int(cols[0]) - margin, 0),
    max(int(rows[0]) - margin, 0),
    min(int(cols[-1]) + 1 + margin, image.width),
    min(int(rows[-1]) + 1 + margin, image.height),
)
cropped = image.crop(box)
target.parent.mkdir(parents=True, exist_ok=True)
cropped.save(target, format="PNG", optimize=True)
print("    source {0} -> cropped {1}, {2} bytes".format(image.size, cropped.size, target.stat().st_size))
'@
    Set-Content -LiteralPath $CropScript -Value $cropSource -Encoding ASCII
    & $python $CropScript $SourceShot $ShotTarget
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $ShotTarget)) {
        $cropped = $true
    }
    else {
        Write-Warning "Cropping unavailable (exit $LASTEXITCODE); falling back to a straight copy."
    }
    Remove-Item -LiteralPath $CropScript -Force -ErrorAction SilentlyContinue
}
else {
    Write-Warning 'Python not found; falling back to a straight copy.'
}

if (-not $cropped) {
    Copy-Item -LiteralPath $SourceShot -Destination $ShotTarget -Force
    Write-Host '    copied the original capture without trimming.'
}

Write-Host "Screenshot ready: $ShotTarget" -ForegroundColor Green

# --------------------------------------------------------------------------
Write-Step 'Refreshing .gitignore'

@(
    '__pycache__/',
    '*.py[cod]',
    '*.egg-info/',
    '.pytest_cache/',
    '.coverage',
    'htmlcov/',
    'dist/',
    'build/',
    '.venv/',
    'venv/',
    '.idea/',
    '.vscode/',
    'output/',
    'tmp/',
    'test-results/',
    '*.pdf',
    'Thumbs.db',
    '.DS_Store'
) | Set-Content -LiteralPath $Gitignore -Encoding ASCII

Write-Host '.gitignore refreshed (resume PDF, temp dirs and test output stay local).' -ForegroundColor Green

# --------------------------------------------------------------------------
Write-Step 'Removing scratch files and test leftovers'

$junk = @(
    'README.fixed.md',
    'diag-shot.b64',
    'dashboard-backup.png',
    '.git-alt',
    'docs\assets\probe-write-test.txt',
    'docs\assets\child-probe.txt',
    '.git\probe-write-test.txt'
)
foreach ($item in $junk) {
    $path = Join-Path $Repo $item
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "    removed $item"
    }
}

# Leftovers from the test run that was blocked by file permissions.
Get-ChildItem -LiteralPath $Repo -Directory -Filter 'tmp*' -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne 'tmp' } |
    ForEach-Object {
        try {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop
            Write-Host "    removed $($_.Name)"
        }
        catch {
            Write-Warning "    could not remove $($_.Name): $($_.Exception.Message)"
        }
    }

# --------------------------------------------------------------------------
Write-Step 'Committing on top of the existing history'

$before = (& git -C $Repo rev-parse --short HEAD 2>$null)
if ($before) { Write-Host "    HEAD before: $before" }

& git -C $Repo add --all
& git -C $Repo -c user.name=$AuthorName -c user.email=$AuthorEmail commit -m $CommitMsg

if ($LASTEXITCODE -ne 0) {
    throw 'git commit failed; see the output above.'
}

Write-Host ''
& git -C $Repo log --oneline -3
Write-Host ''
Write-Host 'Files in this commit:' -ForegroundColor Cyan
& git -C $Repo show --stat --oneline HEAD | Select-Object -Skip 1

# --------------------------------------------------------------------------
Write-Step 'Configuring the remote'

$existing = (& git -C $Repo remote get-url origin 2>$null)
if ($existing) {
    & git -C $Repo remote set-url origin $RemoteUrl
}
else {
    & git -C $Repo remote add origin $RemoteUrl
}
& git -C $Repo remote -v

# --------------------------------------------------------------------------
Write-Step 'Publishing'

if ($Push) {
    & git -C $Repo push -u origin main
    if ($LASTEXITCODE -ne 0) {
        throw 'git push failed. If it asked for credentials, sign in to GitHub and run the push again.'
    }
    Write-Host ''
    Write-Host 'Done: https://github.com/xiaoli50823/FailLens' -ForegroundColor Green
}
else {
    Write-Host 'Stopped at the commit (no -Push switch). Publish with:' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '    git -C D:\testtool push -u origin main' -ForegroundColor White
    Write-Host ''
    Write-Host 'A GitHub sign-in window appears on the first push.'
    Write-Host ''
    Write-Host 'Suggested repository settings (Settings page):'
    Write-Host '  Description: Explainable diagnosis and flaky-test analysis for JUnit test reports'
    Write-Host '  Topics: python, pytest, junit, test-automation, flaky-tests, test-reporting, qa'
}
