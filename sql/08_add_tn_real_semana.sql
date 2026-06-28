-- ============================================================
-- Migración: cosecha real por semana (F7)
-- ------------------------------------------------------------
-- La SemanaCosecha (M5) solo guardaba lo PLANIFICADO (tn_planificada).
-- Para comparar "real vs planificado" en el Resumen de campaña hace falta
-- registrar lo efectivamente cosechado cada semana. Esta columna lo guarda;
-- NULL = aún no se registró cosecha real para esa semana.
--
-- NOTA: esta columna YA está en 01_ddl_base.sql (esquema base completo).
--       Este script solo hace falta para una BD creada con una versión vieja
--       del DDL; en una instalación limpia es un no-op (IF NOT EXISTS).
--
-- Ejecutar como DUEÑO de la tabla (rol postgres), p. ej.:
--   psql -U postgres -d palta -f sql/08_add_tn_real_semana.sql
-- Idempotente: se puede correr varias veces sin error.
-- ============================================================

ALTER TABLE semana_cosecha ADD COLUMN IF NOT EXISTS tn_real DOUBLE PRECISION;
