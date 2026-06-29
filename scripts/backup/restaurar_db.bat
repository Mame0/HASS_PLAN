@echo off
REM ============================================================
REM  Restaura la base PostgreSQL 'palta' en una PC NUEVA desde
REM  un archivo palta_backup_*.dump (generado por respaldar_db.bat).
REM
REM  Requisitos en la PC destino:
REM    - PostgreSQL 18 instalado y corriendo.
REM    - Conoces la clave del usuario 'postgres'.
REM
REM  Uso:  restaurar_db.bat  palta_backup_AAAA-MM-DD.dump
REM ============================================================
setlocal
cd /d "%~dp0"

set PGBIN=C:\Program Files\PostgreSQL\18\bin
set PGHOST=localhost
set PGDB=palta

if "%~1"=="" (
    echo Uso:  restaurar_db.bat  ruta\al\palta_backup_AAAA-MM-DD.dump
    echo.
    pause
    exit /b 1
)
set DUMP=%~1

echo === 1/4  Creando los roles de la app (si no existen) ===
"%PGBIN%\psql.exe" -U postgres -h %PGHOST% -d postgres -v ON_ERROR_STOP=0 -c "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_palta') THEN CREATE ROLE app_palta LOGIN PASSWORD '71804217' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE; END IF; IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='palta_auth') THEN CREATE ROLE palta_auth NOLOGIN BYPASSRLS; END IF; END $$;"

echo === 2/4  Creando la base de datos "%PGDB%" (vacia) ===
"%PGBIN%\psql.exe" -U postgres -h %PGHOST% -d postgres -c "CREATE DATABASE %PGDB%;"

echo === 3/4  Restaurando los datos desde %DUMP% ===
"%PGBIN%\pg_restore.exe" -U postgres -h %PGHOST% -d %PGDB% "%DUMP%"

echo === 4/4  Verificando ===
"%PGBIN%\psql.exe" -U postgres -h %PGHOST% -d %PGDB% -c "SELECT 'fincas='||count(*) FROM finca;"

echo.
echo LISTO. Ahora puedes arrancar la app con iniciar_postgres.bat
echo.
pause
