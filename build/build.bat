@echo off
setlocal enabledelayedexpansion
title Compilar Spamed Travel

rem ---------------------------------------------------------------------
rem  Compila Spamed Travel en una PC con Windows.
rem
rem  Uso:  build\build.bat     (desde la raiz del proyecto o desde build\)
rem
rem  Hace todo solo: entorno virtual, dependencias, chequeo de sintaxis,
rem  PyInstaller, zip portable y -- si Inno Setup esta instalado -- el
rem  instalador de un solo clic. Tarda entre 3 y 8 minutos la primera vez.
rem
rem  El entorno virtual (.venv) se REUSA si ya existe. Solo hay que borrarlo
rem  si se corrompe.
rem ---------------------------------------------------------------------

cd /d "%~dp0.."
set RAIZ=%CD%
echo.
echo ===============================================
echo   Spamed Travel - compilacion
echo   Carpeta: %RAIZ%
echo ===============================================
echo.

rem --- 1 de 6: Python -------------------------------------------------
echo [1/6] Buscando Python...
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    set PY=py -3
) else (
    where python >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo.
        echo ERROR: no se encontro Python. Instalalo de python.org
        echo        y tildar "Add python.exe to PATH".
        goto :error
    )
    set PY=python
)
%PY% --version
echo.

rem --- 2 de 6: entorno virtual ----------------------------------------
echo [2/6] Entorno virtual...
if exist ".venv\Scripts\python.exe" (
    echo       .venv ya existe, se reusa.
) else (
    %PY% -m venv .venv
    if %ERRORLEVEL% NEQ 0 goto :error
)
set VPY=%RAIZ%\.venv\Scripts\python.exe
echo.

rem --- 3 de 6: dependencias -------------------------------------------
echo [3/6] Instalando dependencias (puede tardar: QtWebEngine es pesado)...
"%VPY%" -m pip install --upgrade pip --quiet
if %ERRORLEVEL% NEQ 0 goto :error
"%VPY%" -m pip install -r requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 goto :error
"%VPY%" -m pip install pyinstaller --quiet
if %ERRORLEVEL% NEQ 0 goto :error
echo.

rem --- 4 de 6: chequeo de sintaxis ------------------------------------
rem  Este paso NO es decorativo. PyInstaller enmascara un SyntaxError como
rem  "invalid module" o como un falso "circular import", larguisimo de
rem  diagnosticar. Aca el error aparece con su traceback real.
echo [4/6] Verificando sintaxis (compileall)...
"%VPY%" -m compileall -q src
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR de sintaxis en src\. El detalle esta arriba.
    goto :error
)
echo       OK.
echo.

rem --- 5 de 6: PyInstaller --------------------------------------------
echo [5/6] Compilando con PyInstaller...
if exist "dist\SpamedTravel" rmdir /s /q "dist\SpamedTravel"
"%VPY%" -m PyInstaller --noconfirm --clean build\spamed.spec
if %ERRORLEVEL% NEQ 0 goto :error

if not exist "dist\SpamedTravel\SpamedTravel.exe" (
    echo ERROR: PyInstaller termino pero no aparecio el .exe.
    goto :error
)

rem  Defensa del bug del paquete duplicado: si el bundle materializa una
rem  carpeta "spamed" real, el .exe falla al importar sus propios modulos.
if exist "dist\SpamedTravel\_internal\spamed" (
    echo.
    echo ERROR: quedo una carpeta _internal\spamed en el bundle.
    echo        Algo volvio a copiar el paquete a disco. Revisar build\spamed.spec.
    goto :error
)
echo       OK.
echo.

rem --- 6 de 6: zip portable + instalador ------------------------------
echo [6/6] Empaquetando...
if exist "dist\SpamedTravel_portable.zip" del /q "dist\SpamedTravel_portable.zip"
powershell -NoProfile -Command ^
    "Compress-Archive -Path 'dist\SpamedTravel\*' -DestinationPath 'dist\SpamedTravel_portable.zip' -Force"

set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe

if defined ISCC (
    "%ISCC%" build\installer.iss
    if !ERRORLEVEL! NEQ 0 goto :error
) else (
    echo.
    echo       AVISO: no se encontro Inno Setup 6, no se genera el instalador.
    echo       No es un error: dist\SpamedTravel\SpamedTravel.exe ya funciona.
    echo       Para tenerlo: winget install --id JRSoftware.InnoSetup -e
)

echo.
echo ===============================================
echo   LISTO
echo ===============================================
echo   Programa : dist\SpamedTravel\SpamedTravel.exe
echo   Portable : dist\SpamedTravel_portable.zip
if defined ISCC echo   Instalador: dist\instalador\SpamedTravel_Setup_1.1.0.exe
echo.
pause
exit /b 0

:error
echo.
echo ===============================================
echo   LA COMPILACION FALLO
echo ===============================================
echo.
pause
exit /b 1
