# Migración a PostgreSQL + Multi-tenant (SaaS) con RLS

Guía de orquestación. Convierte la base SQLite (`instance/palta.db`) a PostgreSQL
con aislamiento por cliente (Productor) forzado por **Row Level Security**.

> **Estado: migración CERRADA.** La base PostgreSQL `palta` ya está migrada,
> operativa y es la **única fuente de verdad**. Verificado end-to-end: esquema
> (01+02) construye limpio con todas las columnas, `verificar_rls.py` pasa las 6
> comprobaciones, y la app arranca y sirve datos contra PostgreSQL. El ETL
> `migrar_datos.py` fue un paso **histórico de un solo uso**; el SQLite origen
> quedó atrás respecto del modelo (su `campana` no tiene `finca_id`), así que el
> ETL **ya no es re-ejecutable** desde él — y no hace falta que lo sea. Esta guía
> se conserva como referencia de cómo se hizo y para montar la BD desde cero.

## Arquitectura del aislamiento

- **Patrón:** `productor_id` denormalizado en todas las tablas operativas (Opción A:
  RLS sin JOINs).
- **Integridad entre tenants:** FK compuestas `(padre_id, productor_id)` + `UNIQUE(id,
  productor_id)` → un hijo no puede colgar de un padre de otro tenant.
- **RLS:** `ENABLE` + `FORCE ROW LEVEL SECURITY`; políticas con
  `current_setting('app.tenant')`. Bypass de `SUPERADMIN` por flag.
- **Anti-fuga por pooling:** la app fija el tenant con `set_config(..., is_local=true)`
  (transaction-local) vía el listener `after_begin` de SQLAlchemy (`app/tenant.py`).
- **Login antes de conocer el tenant:** función `app_login_lookup()` `SECURITY DEFINER`.
- **Catálogo compartido:** `fuente_datos` no lleva `productor_id` ni RLS.

## Requisitos

```bash
pip install psycopg2-binary           # añadido a requirements.txt
docker run --name palta-pg -e POSTGRES_PASSWORD=palta -e POSTGRES_DB=palta \
       -p 5432:5432 -d postgres:16    # PostgreSQL >= 15
```

## Orden de ejecución y gates

| # | Paso | Comando | Gate (verificación) |
|---|------|---------|---------------------|
| 1 | Estructura | `psql -U postgres -d palta -f sql/01_ddl_base.sql` | Termina en COMMIT sin error; `\d finca` muestra `productor_id` |
| 2 | RLS | `psql -U postgres -d palta -f sql/02_rls.sql` | Crea roles `app_palta`/`palta_auth` y políticas |
| 3 | Datos | `python scripts/migracion/migrar_datos.py` | Conteos coinciden (finca=2, lote=11, campana=5, alerta=16…), todo con `productor_id=1` |
| 4 | App | `DATABASE_URL=postgresql://app_palta:CLAVE@localhost/palta python run.py` | La app arranca contra PostgreSQL |
| 5 | Aislamiento | `python scripts/migracion/verificar_rls.py` | Todas las comprobaciones PASA |

> **Esquema base completo:** `01_ddl_base.sql` ya incluye TODAS las columnas
> (incl. `prediccion.intervalo_p10/p90` y `lote.densidad_plantas_ha`). Los scripts
> `sql/05_*` y `sql/06_*` solo hacen falta para una BD creada con una versión vieja
> del DDL; en una instalación limpia son no-ops idempotentes y **no** hay que correrlos.
>
> **Clave de `app_palta`:** está fijada en `sql/02_rls.sql` (`71804217`). Si la cambias,
> actualízala también en `DATABASE_URL` (ver `iniciar_postgres.bat`) y en
> `PG_APP_PASSWORD` para `verificar_rls.py` — los tres deben coincidir.

## Usuarios sembrados (Fase 3)

- `superadmin` / `admin@paltaplan.pe` — SUPERADMIN (proveedor), `productor_id` NULL.
- `lajoya` / `lajoya@productor.pe` — CLIENTE_ADMIN del productor 1 (Chacra La Joya).
- Clave inicial de ambos: `palta2026` (hash werkzeug). **Cámbiala.**

Login: `POST /api/auth/login {"usuario":"lajoya","clave":"palta2026"}`.

## Notas

- **La app trabaja SIEMPRE con PostgreSQL.** `config.py` se conecta por defecto al
  PostgreSQL local (rol `app_palta`); `DATABASE_URL` lo sobreescribe. Ya NO hay
  fallback a SQLite para la app. En PostgreSQL el esquema lo crean los scripts `sql/`
  (no `create_all`, que no sabe de FK compuestas ni RLS).
- **SQLite solo queda para:** (a) ser la FUENTE histórica de la migración
  (`instance/palta.db`, esquema antiguo — no ejecutes la app contra él, y NO está
  sincronizado con el modelo actual: el ETL ya no corre desde él) y (b) los tests,
  que usan un SQLite temporal y aislado vía su propio `TestConfig` (rápido y sin
  tocar nada real).
- Money (`costo`, `costo_por_viaje`) es `NUMERIC(12,2)` en PostgreSQL; el ORM lo mapea
  como `Float` para que la API lo serialice como número.
- Sin login, la app opera como tenant por defecto (`DEFAULT_TENANT_ID=1`) para no
  romper el front actual. Al integrar login en el front, cada cliente fija su tenant.
