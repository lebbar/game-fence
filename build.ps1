$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

Write-Host "Installation des dependances (execution + build)..." -ForegroundColor Cyan
python -m pip install -q -r "$root\requirements-build.txt"

Write-Host "Compilation PyInstaller -> dist\GameFence.exe ..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean "$root\GameFence.spec"

if (Test-Path "$root\dist\GameFence.exe") {
    Write-Host "OK : $root\dist\GameFence.exe" -ForegroundColor Green
} else {
    Write-Host "Echec : GameFence.exe introuvable dans dist\" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Installateur Windows : installe Inno Setup (https://jrsoftware.org/isinfo.php), puis compile installer.iss (ISCC.exe ou menu Fichiers > Compiler)." -ForegroundColor Yellow
