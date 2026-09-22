# Crea un acceso directo en el Escritorio para abrir Spamed Travel en modo
# desarrollo, sin tener que escribir el comando cada vez.
#
# Se corre UNA sola vez, parado en la carpeta del proyecto:
#     .\crear_acceso_directo.ps1
#
# El acceso apunta al pythonw.exe del entorno virtual (pythonw y no python,
# para que no quede una consola negra abierta detras de la ventana) y le pasa
# src\main.py. Python agrega solo la carpeta del script al path, asi que
# encuentra el paquete 'spamed' sin necesidad de tocar ninguna variable de
# entorno del sistema.
#
# Si movés la carpeta del proyecto, volvé a correrlo.

$ErrorActionPreference = "Stop"

$proyecto = $PSScriptRoot
$pythonw  = Join-Path $proyecto ".venv\Scripts\pythonw.exe"
$entrada  = Join-Path $proyecto "src\main.py"
$icono    = Join-Path $proyecto "src\spamed\recursos\spamed.ico"

if (-not (Test-Path $pythonw)) {
    Write-Host "No existe el entorno virtual en .venv" -ForegroundColor Yellow
    Write-Host "Corre primero .\ejecutar_dev.bat una vez: crea el .venv e instala todo."
    exit 1
}
if (-not (Test-Path $entrada)) {
    Write-Host "No se encontro src\main.py en $proyecto" -ForegroundColor Yellow
    exit 1
}

$escritorio = [Environment]::GetFolderPath("Desktop")
$destino    = Join-Path $escritorio "Spamed Travel (desarrollo).lnk"

$shell  = New-Object -ComObject WScript.Shell
$acceso = $shell.CreateShortcut($destino)
$acceso.TargetPath       = $pythonw
$acceso.Arguments        = "`"$entrada`""
$acceso.WorkingDirectory = $proyecto
$acceso.Description      = "Spamed Travel en modo desarrollo (sin compilar)"
if (Test-Path $icono) { $acceso.IconLocation = $icono }
$acceso.Save()

Write-Host ""
Write-Host "Listo. Acceso directo creado en el Escritorio:" -ForegroundColor Green
Write-Host "   $destino"
Write-Host ""
Write-Host "Abre la version de desarrollo, con el codigo tal como esta ahora"
Write-Host "en la carpeta del proyecto. No reemplaza a la version instalada."
