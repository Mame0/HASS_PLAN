-- ###########################################################################
--  FASE 2 — ROW LEVEL SECURITY (RLS)  (PostgreSQL >= 15)
--  Aislamiento multi-tenant forzado a nivel de motor.
--
--  EJECUTAR DESPUÉS de 01_ddl_base.sql y COMO SUPERUSUARIO (rol postgres).
--
--  -----------------------------------------------------------------------
--  MODELO DE SEGURIDAD
--    * La app se conecta como el rol app_palta (NOSUPERUSER, NOBYPASSRLS).
--      Al no ser dueño ni superusuario, RLS SIEMPRE se le aplica.
--    * El contexto del request vive en dos GUC de sesión, fijadas por la app
--      con set_config(..., is_local => true) -> TRANSACTION-LOCAL (no se filtra
--      entre requests del pool, se borra solo al COMMIT/ROLLBACK):
--          app.tenant        = productor_id del usuario logueado
--          app.is_superadmin = 'on' solo si el usuario es SUPERADMIN
--    * FORCE ROW LEVEL SECURITY: el aislamiento aplica incluso al dueño de la
--      tabla (defensa en profundidad). Solo un rol con BYPASSRLS lo evita,
--      reservado a la función de login.
--    * Default-deny: si app.tenant no está fijada, app_current_tenant() = NULL
--      y NINGUNA fila casa -> la sesión no ve nada hasta autenticar.
-- ###########################################################################

BEGIN;

-- ===========================================================================
--  1. ROLES
-- ===========================================================================

-- Rol con el que se conecta la aplicación. Sujeto a RLS.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_palta') THEN
        CREATE ROLE app_palta LOGIN PASSWORD '71804217'
            NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END $$;

-- Rol SIN login pero con BYPASSRLS: solo lo "viste" la función de login
-- (SECURITY DEFINER). Es la única superficie que puentea RLS, de forma
-- controlada y auditable.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'palta_auth') THEN
        CREATE ROLE palta_auth NOLOGIN BYPASSRLS;
    END IF;
END $$;

-- Acceso al esquema (en PG >= 15 conviene concederlo explícitamente).
GRANT USAGE ON SCHEMA public TO app_palta;

-- ===========================================================================
--  2. FUNCIONES DE CONTEXTO  (leen los GUC de la sesión)
--     missing_ok => true: si el GUC no existe aún, devuelven NULL/false
--     en vez de lanzar error (default-deny).
-- ===========================================================================

CREATE OR REPLACE FUNCTION app_current_tenant() RETURNS integer
    LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.tenant', true), '')::integer $$;

CREATE OR REPLACE FUNCTION app_is_superadmin() RETURNS boolean
    LANGUAGE sql STABLE AS
$$ SELECT current_setting('app.is_superadmin', true) = 'on' $$;

-- ===========================================================================
--  3. TABLAS DEL TENANT FILTRADAS POR productor_id
--     ENABLE + FORCE RLS, política única FOR ALL, y GRANT de DML a app_palta.
--     Se genera en bucle para garantizar que NINGUNA tabla quede sin política.
-- ===========================================================================
DO $$
DECLARE
    t text;
    tablas text[] := ARRAY[
        'campana', 'finca', 'lote', 'lote_campana', 'registro_agronomico',
        'prediccion', 'resultado_cosecha', 'plan_cosecha', 'semana_cosecha',
        'plan_mano_obra', 'mano_obra_semanal', 'inventario', 'logistica_semanal',
        'plan_transporte', 'despacho_semanal', 'alerta', 'clima_sync',
        'variable_override', 'usuario'
    ];
BEGIN
    FOREACH t IN ARRAY tablas LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE  ROW LEVEL SECURITY', t);
        EXECUTE format($f$
            CREATE POLICY tenant_isolation ON %I
                FOR ALL
                USING      (app_is_superadmin() OR productor_id = app_current_tenant())
                WITH CHECK (app_is_superadmin() OR productor_id = app_current_tenant())
        $f$, t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO app_palta', t);
    END LOOP;
END $$;

-- ===========================================================================
--  4. TABLA productor  (se filtra por id, no por productor_id)
--     Política partida por comando: cada cliente ve/edita SU ficha; solo el
--     SUPERADMIN da de alta o elimina productores (onboarding del proveedor).
-- ===========================================================================
ALTER TABLE productor ENABLE ROW LEVEL SECURITY;
ALTER TABLE productor FORCE  ROW LEVEL SECURITY;

CREATE POLICY productor_select ON productor
    FOR SELECT USING (app_is_superadmin() OR id = app_current_tenant());

CREATE POLICY productor_update ON productor
    FOR UPDATE USING      (app_is_superadmin() OR id = app_current_tenant())
               WITH CHECK (app_is_superadmin() OR id = app_current_tenant());

CREATE POLICY productor_insert ON productor
    FOR INSERT WITH CHECK (app_is_superadmin());

CREATE POLICY productor_delete ON productor
    FOR DELETE USING (app_is_superadmin());

GRANT SELECT, INSERT, UPDATE, DELETE ON productor TO app_palta;

-- ===========================================================================
--  5. CATÁLOGO COMPARTIDO fuente_datos  (sin RLS: igual para todos)
--     La app solo lo lee; las altas del catálogo las hace el proveedor (dueño).
-- ===========================================================================
GRANT SELECT ON fuente_datos TO app_palta;

-- ===========================================================================
--  6. SECUENCIAS  (las columnas IDENTITY necesitan USAGE para autogenerar id)
-- ===========================================================================
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_palta;

-- ===========================================================================
--  7. FUNCIÓN DE LOGIN  (superficie controlada que puentea RLS)
--     SECURITY DEFINER + propiedad de palta_auth (BYPASSRLS) => puede buscar
--     al usuario en CUALQUIER tenant durante la autenticación, ANTES de
--     conocer el tenant. Devuelve lo MÍNIMO para verificar la contraseña en
--     la app; nunca expone datos operativos.
--     SET search_path: evita ataques por search_path (best practice en DEFINER).
-- ===========================================================================
-- palta_auth ejecuta la función (SECURITY DEFINER). BYPASSRLS salta las POLÍTICAS,
-- pero NO concede privilegios de tabla: necesita SELECT explícito sobre usuario.
GRANT SELECT ON usuario TO palta_auth;

DROP FUNCTION IF EXISTS app_login_lookup(text);
CREATE FUNCTION app_login_lookup(p_identificador text)
    RETURNS TABLE (
        id              integer,
        productor_id    integer,
        nombre_usuario  varchar,
        contrasena_hash varchar,
        tipo_usuario    varchar,
        activo          boolean
    )
    LANGUAGE sql
    SECURITY DEFINER
    STABLE
    SET search_path = public
AS $$
    SELECT u.id, u.productor_id, u.nombre_usuario, u.contrasena_hash,
           u.tipo_usuario, u.activo
    FROM usuario u
    WHERE (u.correo = p_identificador OR u.nombre_usuario = p_identificador)
      AND u.activo = TRUE
$$;

ALTER FUNCTION app_login_lookup(text) OWNER TO palta_auth;
REVOKE EXECUTE ON FUNCTION app_login_lookup(text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION app_login_lookup(text) TO app_palta;

COMMIT;

-- ###########################################################################
--  CÓMO USA ESTO LA APP  (la implementación Flask completa va en la Fase 4)
--  -----------------------------------------------------------------------
--  1) Login (sesión aún sin tenant):
--         SELECT * FROM app_login_lookup('garay@correo.com');
--     -> verificar contrasena_hash en Python (werkzeug/bcrypt).
--
--  2) Tras autenticar, al inicio de CADA transacción del request:
--         SELECT set_config('app.tenant',        '5',   true);   -- productor_id
--         SELECT set_config('app.is_superadmin', 'off', true);   -- 'on' si SUPERADMIN
--     (is_local => true las hace transaction-local: el pool NO las filtra.)
--
--  3) Para el SUPERADMIN: set_config('app.is_superadmin','on',true) y
--     app.tenant a '' (ve todos los tenants).
--
--  VERIFICACIÓN MANUAL (gate Fase 2), conectado como app_palta:
--     -- sin contexto: no se ve nada
--     SELECT count(*) FROM finca;                       -- => 0
--     -- como tenant 1:
--     SELECT set_config('app.tenant','1',true);
--     SELECT count(*) FROM finca;                       -- => solo fincas del productor 1
--     -- intentar colar datos de otro tenant: debe FALLAR por WITH CHECK
--     INSERT INTO finca (productor_id,nombre) VALUES (2,'hack');  -- ERROR
-- ###########################################################################
