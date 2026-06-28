-- ============================================================
-- Migración: densidad de plantación (plantas/Ha) en la tabla lote
-- ------------------------------------------------------------
-- Reemplaza la constante hardcodeada 350 plantas/Ha del front: ahora el
-- número de árboles del lote se deriva de su marco de plantación real.
-- NULL = sin registrar -> el front cae al default 350 solo para estimar.
--
-- NOTA: esta columna YA está en 01_ddl_base.sql (esquema base completo).
--       Este script solo hace falta para una BD creada con una versión vieja
--       del DDL; en una instalación limpia es un no-op (IF NOT EXISTS).
--
-- Ejecutar como DUEÑO de la tabla (rol postgres), p. ej.:
--   psql -U postgres -d palta -f sql/06_add_densidad_lote.sql
-- Idempotente: se puede correr varias veces sin error.
-- ============================================================

ALTER TABLE lote ADD COLUMN IF NOT EXISTS densidad_plantas_ha DOUBLE PRECISION;
