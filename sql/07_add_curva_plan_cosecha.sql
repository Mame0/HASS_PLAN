-- ============================================================
-- Migración: curva de distribución del plan de cosecha
-- ------------------------------------------------------------
-- El plan de cosecha (M5) repartía el total SIEMPRE con una curva campana.
-- Ahora el agricultor elige la forma del reparto: 'campana' (pico al centro),
-- 'uniforme' (igual cada semana), 'creciente' (pico al final) o 'decreciente'
-- (pico al inicio). Esta columna guarda la elegida para poder regenerar el plan.
-- Default 'campana' = comportamiento previo (los planes existentes no cambian).
--
-- NOTA: esta columna YA está en 01_ddl_base.sql (esquema base completo).
--       Este script solo hace falta para una BD creada con una versión vieja
--       del DDL; en una instalación limpia es un no-op (IF NOT EXISTS).
--
-- Ejecutar como DUEÑO de la tabla (rol postgres), p. ej.:
--   psql -U postgres -d palta -f sql/07_add_curva_plan_cosecha.sql
-- Idempotente: se puede correr varias veces sin error.
-- ============================================================

ALTER TABLE plan_cosecha ADD COLUMN IF NOT EXISTS curva VARCHAR(20) NOT NULL DEFAULT 'campana';
