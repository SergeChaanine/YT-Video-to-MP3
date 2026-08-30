param(
    [string]$FfmpegDirectory = "",
    [string]$DenoPath = "",
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvDirectory = Join-Path $repositoryRoot ".venv"
$venvPython = Join-Path $venvDirectory "Scripts\python.exe"
$vendorDirectory = Join-Path $repositoryRoot "vendor\ffmpeg"
$vendorDenoPath = Join-Path $repositoryRoot "vendor\deno\deno.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv $venvDirectory
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e "${repositoryRoot}[dev,build]"

if ($FfmpegDirectory) {
    $resolvedFfmpegDirectory = (Resolve-Path -LiteralPath $FfmpegDirectory).Path
    $env:YT_TO_MP3_FFMPEG_DIR = $resolvedFfmpegDirectory
    $ffmpeg = Join-Path $resolvedFfmpegDirectory "ffmpeg.exe"
    $ffprobe = Join-Path $resolvedFfmpegDirectory "ffprobe.exe"
}
else {
    $ffmpeg = Join-Path $vendorDirectory "ffmpeg.exe"
    $ffprobe = Join-Path $vendorDirectory "ffprobe.exe"
}
if (-not (Test-Path -LiteralPath $ffmpeg) -or -not (Test-Path -LiteralPath $ffprobe)) {
    throw "Place ffmpeg.exe and ffprobe.exe in vendor\ffmpeg or use -FfmpegDirectory."
}

if ($DenoPath) {
    $resolvedDenoPath = (Resolve-Path -LiteralPath $DenoPath).Path
    if ((Get-Item -LiteralPath $resolvedDenoPath).PSIsContainer) {
        $resolvedDenoPath = Join-Path $resolvedDenoPath "deno.exe"
    }
    $env:YT_TO_MP3_DENO_PATH = $resolvedDenoPath
    $deno = $resolvedDenoPath
}
else {
    $deno = $vendorDenoPath
}
if (-not (Test-Path -LiteralPath $deno -PathType Leaf)) {
    throw "Place deno.exe in vendor\deno or use -DenoPath."
}

Push-Location $repositoryRoot
try {
    & $venvPython -m pytest
    & $venvPython -m ruff check .
    & $venvPython -m PyInstaller --noconfirm --clean "packaging\app.spec"

    if (-not $SkipInstaller) {
        $isccCandidates = @(
            "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )
        $iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if ($iscc) {
            & $iscc "packaging\installer.iss"
        }
        else {
            Write-Warning "Inno Setup 6 was not found; the application was built without an installer."
        }
    }
}
finally {
    Pop-Location
}
