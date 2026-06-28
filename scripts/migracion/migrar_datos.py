"""
FASE 3 — Migración de datos SQLite -> PostgreSQL (ETL)

Lee instance/palta.db y carga los datos en la base PostgreSQL ya creada con
01_ddl_base.sql (estructura) y 02_rls.sql (RLS). Concretamente:

  1. Crea el productor inicial "Chacra La Joya" (id=1) y le asigna TODA la data
     existente (backfill de productor_id en cascada).
  2. Crea dos usuarios de arranque (1 SUPERADMIN del proveedor + 1 CLIENTE_ADMIN
     de Chacra La Joya) con contraseña por defecto.
  3. Copia fuente_datos (catálogo compartido, sin productor_id).
  4. Copia las 18 tablas de tenant PRESERVANDO los IDs originales y añadiendo
     productor_id = 1.
  5. Resincroniza las secuencias IDENTITY (setval) para que los próximos INSERT
     no choquen con los IDs migrados.

IMPORTANTE — conexión:
  Conéctate como SUPERUSUARIO (rol 'postgres'). Los superusuarios IGNORAN RLS,
  así que el ETL puede insertar en todos los tenants. Si te conectaras como
  app_palta, FORCE RLS bloquearía los INSERT (no hay contexto de tenant).

Requisitos:  pip install psycopg2-binary
Uso:
    # base de datos vacía (recién creada con 01 y 02):
    python scripts/migracion/migrar_datos.py
    # volver a empezar (borra datos y recarga):
    python scripts/migracion/migrar_datos.py --reset

Config por variables de entorno (con defaults para Docker local):
    PG_HOST (localhost)  PG_PORT (5432)  PG_DB (palta)
    PG_USER (postgres)   PG_PASSWORD (palta)
    SQLITE_PATH (instance/palta.db)
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    sys.exit("Falta psycopg2. Instala con:  pip install psycopg2-binary")

try:
    from werkzeug.security import generate_password_hash
except ImportError:
    # La app ya usa werkzeug; si no está, degradamos a un placeholder visible.
    def generate_password_hash(p):  # type: ignore
        return f"PLACEHOLDER_SIN_HASH::{p}"

# --------------------------------------------------------------------------- #
#  Configuración
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

SQLITE_PATH = os.environ.get(
    "SQLITE_PATH", os.path.join(PROJECT_ROOT, "instance", "palta.db")
)
PG_DSN = dict(
    host=os.environ.get("PG_HOST", "localhost"),
    port=os.environ.get("PG_PORT", "5432"),
    dbname=os.environ.get("PG_DB", "palta"),
    user=os.environ.get("PG_USER", "postgres"),
    password=os.environ.get("PG_PASSWORD", "palta"),
)

PRODUCTOR_ID = 1  # tenant al que se asigna toda la data existente
CLAVE_DEFECTO = "palta2026"  # contraseña inicial de los usuarios sembrados

# Tablas de tenant en orden seguro para las FK (padres antes que hijas).
# A cada una se le INYECTA productor_id = PRODUCTOR_ID durante la carga.
TENANT_TABLES = [
    "campana", "finca", "lote", "lote_campana", "registro_agronomico",
    "prediccion", "resultado_cosecha", "plan_cosecha", "semana_cosecha",
    "plan_mano_obra", "mano_obra_semanal", "inventario", "logistica_semanal",
    "plan_transporte", "despacho_semanal", "alerta", "clima_sync",
    "variable_override",
]

# Catálogo compartido (sin productor_id).
SHARED_TABLES = ["fuente_datos"]

# Todas las tablas con columna id IDENTITY (para resincronizar secuencias).
ALL_ID_TABLES = ["productor", "usuario"] + SHARED_TABLES + TENANT_TABLES

# Columnas booleanas por tabla: SQLite guarda 0/1, PostgreSQL espera TRUE/FALSE.
BOOL_COLUMNS = {
    "fuente_datos": {"activa"},
    "lote": {"en_produccion"},
    "lote_campana": {"en_produccion"},
}

# Saneamiento de datos huérfanos del origen (SQLite no forzaba FK; el destino sí,
# por las FK compuestas). (columna, tabla_padre):
#   DROP -> descartar la fila si su FK NOT NULL apunta a un padre inexistente.
#   NULL -> poner la FK a NULL si es nullable y apunta a un padre inexistente.
DROP_IF_ORPHAN = {
    "logistica_semanal": [("semana_id", "semana_cosecha")],
}
NULL_IF_ORPHAN = {
    "alerta": [("semana_id", "semana_cosecha")],
}

_id_cache = {}


def _valid_ids(scur, table):
    """Conjunto (cacheado) de ids existentes de una tabla en el origen SQLite."""
    if table not in _id_cache:
        _id_cache[table] = {r[0] for r in scur.execute(f"SELECT id FROM {table}")}
    return _id_cache[table]


def sanitize(scur, table, cols, rows):
    """Descarta/anula referencias FK huérfanas. Devuelve (rows, dropped, nulled)."""
    drop_rules = DROP_IF_ORPHAN.get(table, [])
    null_rules = NULL_IF_ORPHAN.get(table, [])
    if not drop_rules and not null_rules:
        return rows, 0, 0
    out, dropped, nulled = [], 0, 0
    for r in rows:
        d = dict(zip(cols, r))
        if any(d[c] is not None and d[c] not in _valid_ids(scur, par)
               for c, par in drop_rules):
            dropped += 1
            continue
        for c, par in null_rules:
            if d[c] is not None and d[c] not in _valid_ids(scur, par):
                d[c] = None
                nulled += 1
        out.append([d[c] for c in cols])
    return out, dropped, nulled

# Orden de borrado para --reset (inverso a la inserción; TRUNCATE CASCADE igual).
RESET_ORDER = list(reversed(TENANT_TABLES)) + SHARED_TABLES + ["usuario", "productor"]


# --------------------------------------------------------------------------- #
#  Utilidades
# --------------------------------------------------------------------------- #
def sqlite_columns(scur, table):
    """Devuelve los nombres de columna de una tabla SQLite en orden."""
    return [r[1] for r in scur.execute(f"PRAGMA table_info({table})")]


def convert_bools(table, cols, row):
    """Convierte 0/1 -> bool en las columnas booleanas conocidas."""
    bset = BOOL_COLUMNS.get(table, set())
    if not bset:
        return list(row)
    out = []
    for col, val in zip(cols, row):
        if col in bset and val is not None:
            out.append(bool(val))
        else:
            out.append(val)
    return out


def copy_table(scur, pcur, table, inject_productor):
    """Copia una tabla de SQLite a PostgreSQL preservando IDs."""
    cols = sqlite_columns(scur, table)
    rows = scur.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
    if not rows:
        print(f"  {table:24} 0 filas (omitida)")
        return 0

    rows, dropped, nulled = sanitize(scur, table, cols, rows)
    extra = ""
    if dropped:
        extra += f"  [descartadas {dropped} huérfanas]"
    if nulled:
        extra += f"  [{nulled} FK huérfana(s) a NULL]"

    if inject_productor:
        dest_cols = cols + ["productor_id"]
        values = [convert_bools(table, cols, r) + [PRODUCTOR_ID] for r in rows]
    else:
        dest_cols = cols
        values = [convert_bools(table, cols, r) for r in rows]

    collist = ", ".join(f'"{c}"' for c in dest_cols)
    execute_values(
        pcur,
        f'INSERT INTO {table} ({collist}) VALUES %s',
        values,
    )
    print(f"  {table:24} {len(values)} filas{extra}")
    return len(values)


def resync_sequences(pcur):
    """Pone cada secuencia IDENTITY por encima del MAX(id) migrado."""
    for table in ALL_ID_TABLES:
        pcur.execute(
            """
            SELECT setval(
                pg_get_serial_sequence(%s, 'id'),
                COALESCE((SELECT MAX(id) FROM {tbl}), 1),
                (SELECT MAX(id) IS NOT NULL FROM {tbl})
            )
            """.format(tbl=table),
            (table,),
        )


def seed_productor_y_usuarios(pcur):
    """Crea el productor inicial y los dos usuarios de arranque."""
    pcur.execute(
        """
        INSERT INTO productor (id, nombre_comercial, ruc_dni, correo_contacto,
                               telefono, activo)
        VALUES (%s, %s, %s, %s, %s, TRUE)
        """,
        (PRODUCTOR_ID, "Chacra La Joya", None, "lajoya@productor.pe", None),
    )

    pcur.execute(
        """
        INSERT INTO usuario (productor_id, nombre_usuario, correo,
                             contrasena_hash, tipo_usuario, activo)
        VALUES
            (NULL, %s, %s, %s, 'SUPERADMIN',    TRUE),
            (%s,   %s, %s, %s, 'CLIENTE_ADMIN', TRUE)
        """,
        (
            "superadmin", "admin@paltaplan.pe", generate_password_hash(CLAVE_DEFECTO),
            PRODUCTOR_ID, "lajoya", "lajoya@productor.pe",
            generate_password_hash(CLAVE_DEFECTO),
        ),
    )
    print(f"  productor 'Chacra La Joya' (id={PRODUCTOR_ID}) + 2 usuarios "
          f"(clave: {CLAVE_DEFECTO})")


def reset_target(pcur):
    """Vacía las tablas destino para poder re-ejecutar la migración."""
    tablas = ", ".join(RESET_ORDER)
    pcur.execute(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE")
    print(f"  RESET: truncadas {len(RESET_ORDER)} tablas")


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="ETL SQLite -> PostgreSQL")
    parser.add_argument("--reset", action="store_true",
                        help="Vacía las tablas destino antes de cargar")
    args = parser.parse_args()

    if not os.path.exists(SQLITE_PATH):
        sys.exit(f"No existe la BD SQLite: {SQLITE_PATH}")

    sconn = sqlite3.connect(SQLITE_PATH)
    scur = sconn.cursor()
    pconn = psycopg2.connect(**PG_DSN)
    pconn.autocommit = False
    pcur = pconn.cursor()

    total = 0
    try:
        if args.reset:
            print("» Reset")
            reset_target(pcur)

        print("» Tenant inicial")
        seed_productor_y_usuarios(pcur)

        print("» Catálogo compartido")
        for t in SHARED_TABLES:
            total += copy_table(scur, pcur, t, inject_productor=False)

        print("» Tablas de tenant (productor_id = %d)" % PRODUCTOR_ID)
        for t in TENANT_TABLES:
            total += copy_table(scur, pcur, t, inject_productor=True)

        print("» Resincronizando secuencias IDENTITY")
        resync_sequences(pcur)

        pconn.commit()
        print(f"\nOK — {total} filas operativas migradas al tenant {PRODUCTOR_ID}.")
    except Exception:
        pconn.rollback()
        print("\nERROR — se hizo ROLLBACK, la base destino quedó intacta.")
        raise
    finally:
        scur.close(); sconn.close()
        pcur.close(); pconn.close()


if __name__ == "__main__":
    main()
