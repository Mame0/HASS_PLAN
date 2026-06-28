-- ###########################################################################
--  FASE 5 (manual) — Verificación rápida del aislamiento RLS
--  Conéctate como app_palta:  psql -U app_palta -d palta
--  (Para el chequeo automatizado completo usa scripts/migracion/verificar_rls.py)
-- ###########################################################################

-- 1) DEFAULT-DENY: sin contexto no se ve nada -----------------------------
SELECT count(*) AS debe_ser_0 FROM finca;

-- 2) AISLAMIENTO DE LECTURA: como tenant 1 ---------------------------------
SELECT set_config('app.tenant', '1', true);
SELECT count(*) AS fincas_tenant_1 FROM finca;            -- > 0
SELECT count(*) AS fuga_otros_tenants FROM finca WHERE productor_id <> 1;  -- 0

-- 3) AISLAMIENTO DE ESCRITURA (WITH CHECK): debe FALLAR --------------------
-- (ejecútalo dentro de la misma sesión con app.tenant='1')
--   INSERT INTO finca (productor_id, nombre) VALUES (2, 'intrusión');
--   -> ERROR: new row violates row-level security policy for table "finca"

-- 4) BYPASS DE SUPERADMIN --------------------------------------------------
SELECT set_config('app.is_superadmin', 'on', true);
SELECT count(DISTINCT productor_id) AS tenants_visibles FROM finca;  -- todos
SELECT set_config('app.is_superadmin', 'off', true);

-- 5) Comprobar que RLS está activo y forzado en todas las tablas del tenant
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relkind = 'r'
  AND relname IN ('finca','lote','campana','registro_agronomico','prediccion',
                  'resultado_cosecha','plan_cosecha','semana_cosecha',
                  'plan_mano_obra','mano_obra_semanal','inventario',
                  'logistica_semanal','plan_transporte','despacho_semanal',
                  'alerta','clima_sync','variable_override','lote_campana',
                  'usuario','productor')
ORDER BY relname;
-- Todas deben tener relrowsecurity = t y relforcerowsecurity = t
