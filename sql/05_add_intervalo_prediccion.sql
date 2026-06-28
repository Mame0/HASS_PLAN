-- ============================================================
-- Migración: intervalo de predicción p10–p90 en la tabla prediccion
-- ------------------------------------------------------------
-- Añade el rango plausible del rendimiento (percentiles 10 y 90 entre los
-- árboles del Random Forest). Es la medida de incertidumbre que se muestra
-- en el front (módulo M4) junto a la confianza.
--
-- NOTA: estas columnas YA están en 01_ddl_base.sql (esquema base completo).
--       Este script solo hace falta para una BD creada con una versión vieja
--       del DDL; en una instalación limpia es un no-op (IF NOT EXISTS).
--
-- Ejecutar como DUEÑO de la tabla (rol postgres), p. ej.:
--   psql -U postgres -d palta -f sql/05_add_intervalo_prediccion.sql
-- Idempotente: se puede correr varias veces sin error.
-- ============================================================

ALTER TABLE prediccion ADD COLUMN IF NOT EXISTS intervalo_p10 DOUBLE PRECISION;
ALTER TABLE prediccion ADD COLUMN IF NOT EXISTS intervalo_p90 DOUBLE PRECISION;

-- Los GRANT a nivel de tabla del rol de la app (app_palta) ya cubren las
-- columnas nuevas en PostgreSQL, así que no hace falta re-otorgar permisos.
