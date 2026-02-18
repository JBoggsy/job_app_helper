#
# Build the Flask backend as a standalone binary using PyInstaller,
# then place it in src-tauri/binaries/ with the Tauri target-triple naming.
#
# Windows equivalent of build_sidecar.sh
#

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot

try {
    # Detect architecture
    $arch = if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -eq [System.Runtime.InteropServices.Architecture]::Arm64) {
        "aarch64"
    } else {
        "x86_64"
    }

    $triple = "${arch}-pc-windows-msvc"
    $binaryName = "flask-backend-${triple}.exe"
    $outputDir = "src-tauri\binaries"

    Write-Host "Building sidecar for target: ${triple}"
    Write-Host "Output: ${outputDir}\${binaryName}"

    if (-not (Test-Path $outputDir)) {
        New-Item -ItemType Directory -Path $outputDir | Out-Null
    }

    # Build with PyInstaller
    uv run pyinstaller `
        --onefile `
        --name "flask-backend" `
        --hidden-import backend `
        --hidden-import backend.app `
        --hidden-import backend.config `
        --hidden-import backend.config_manager `
        --hidden-import backend.data_dir `
        --hidden-import backend.database `
        --hidden-import backend.models `
        --hidden-import backend.routes `
        --hidden-import backend.llm `
        --hidden-import backend.agent `
        main.py

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed"
    }

    # Copy to Tauri binaries directory with target-triple name
    Copy-Item "dist\flask-backend.exe" "${outputDir}\${binaryName}"

    Write-Host "Sidecar built successfully: ${outputDir}\${binaryName}"

} finally {
    # Clean up PyInstaller artifacts
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "flask-backend.spec") { Remove-Item -Force "flask-backend.spec" }

    Pop-Location
}
