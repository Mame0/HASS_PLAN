@echo off
REM ============================================================
REM  Respalda la base PostgreSQL 'palta' a un archivo .dump
REM  para llevarla por USB a otra PC.
REM
REM  Se conecta como SUPERUSUARIO 'postgres' (ignora RLS, asi el
REM  respaldo sale COMPLETO, no filtrado por tenant).
REM  Te pedira la clave del usuario 'postgres'.
REM ============================================================
setlocal
cd /d "%~dp0"

set PGBIN=C:\Program Files\PostgreSQL\18\bin
set PGHOST=localhost
set PGDB=palta

REM Nombre de archivo con fecha (AAAA-MM-DD).
for /f "tokens=1-3 delims=/-. " %%a in ("%date%") do set HOY=%%c-%%b-%%a
set SALIDA=palta_backup_%HOY%.dump

echo Respaldando la base "%PGDB%" a:  %~dp0%SALIDA%
echo (te pedira la clave del usuario postgres)
echo.

"%PGBIN%\pg_dump.exe" -U postgres -h %PGHOST% -Fc -f "%SALIDA%" %PGDB%

if errorlevel 1 (
    echo.
    echo ERROR: no se pudo generar el respaldo. Revisa la clave o que PostgreSQL este corriendo.
) else (
    echo.
    echo LISTO. Copia este archivo al USB:
    echo    %~dp0%SALIDA%
)
echo.
pause
