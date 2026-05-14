# Compile installer.iss avec Inno Setup (si installé dans le chemin par défaut)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot

$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Host "ISCC.exe introuvable. Installe Inno Setup 6 : https://jrsoftware.org/isinfo.php puis relance ce script." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "$here\dist\GameFence.exe")) {
    Write-Host "dist\GameFence.exe manquant. Lance d'abord .\build.ps1" -ForegroundColor Red
    exit 1
}

Push-Location $here
try {
    & $iscc "$here\installer.iss"
    Write-Host "OK : sortie dans .\installer_output\" -ForegroundColor Green
} finally {
    Pop-Location
}
