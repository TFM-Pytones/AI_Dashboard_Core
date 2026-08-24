# dbt_run.ps1
# Carga las variables del .env (raíz del proyecto) y corre dbt, todo en un solo paso.
#
# Uso:
#   Desde la raíz del proyecto (AI_Dashboard_Core):
#   .\dbt_project\dbt_run.ps1 run --select tag:booking
#
#   Cualquier argumento que le pases después del nombre del script se lo pasa
#   directo a dbt (run, test, build, --select algo, etc.)

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$DbtArgs
)

# --- 1. Cargar el .env de la raíz del proyecto ---
$envPath = Join-Path $PSScriptRoot "..\.env"

if (-not (Test-Path $envPath)) {
    Write-Host "[ERROR] No se encontró .env en: $envPath" -ForegroundColor Red
    exit 1
}

Get-Content $envPath | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        Set-Item -Path "Env:$name" -Value $value
    }
}

Write-Host "[OK] Variables de entorno cargadas desde .env" -ForegroundColor Green

# --- 2. Correr dbt, apuntando al profiles.yml de esta misma carpeta ---
Push-Location $PSScriptRoot
try {
    dbt @DbtArgs --profiles-dir .
}
finally {
    Pop-Location
}
