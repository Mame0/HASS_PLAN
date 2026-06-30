@echo off
REM ============================================================
REM  Arranca HassPlan contra PostgreSQL (modo SaaS multi-tenant)
REM  Doble click o ejecutar desde una terminal en esta carpeta.
REM ============================================================
cd /d "%~dp0"

REM Conexion a PostgreSQL (rol de la app). Cambia la clave si la cambiaste.
set DATABASE_URL=postgresql://app_palta:71804217@localhost:5432/palta

REM Clave para firmar las sesiones de login. Cambiala por una propia.
set SECRET_KEY=71804217

echo Arrancando HassPlan contra PostgreSQL...
echo Abre el navegador en http://localhost:5000
echo (Cierra esta ventana o Ctrl+C para detener)
echo.
REM Sin reloader: un solo proceso, se cierra limpio al cerrar la ventana.
python -c "from app import create_app; create_app().run(host='127.0.0.1', port=5000, use_reloader=False)"

pause
