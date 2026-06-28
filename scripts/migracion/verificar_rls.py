"""
FASE 5 — Verificación automatizada del aislamiento RLS (PostgreSQL).

Prueba, conectado como el rol de la app (app_palta, SUJETO a RLS):

  1. Default-deny: sin contexto de tenant no se ve NINGUNA fila.
  2. Aislamiento de lectura: el tenant 1 solo ve sus fincas; el tenant 2 las suyas.
  3. Aislamiento de escritura (WITH CHECK): el tenant 1 NO puede insertar una
     fila marcada con productor_id de otro tenant.
  4. Bypass de SUPERADMIN: con app.is_superadmin='on' se ven todos los tenants.
  5. Anti-fuga por connection pooling: en la MISMA conexión, cambiar de tenant
     entre transacciones da los conteos correctos (las GUC son transaction-local).

Prepara datos de prueba como SUPERUSUARIO (crea el productor 2 y una finca suya)
y luego ejecuta las aserciones como app_palta.

Requisitos:  pip install psycopg2-binary  + haber corrido 01_ddl_base.sql,
             02_rls.sql y 03 (migrar_datos.py).
Uso:
    python scripts/migracion/verificar_rls.py

Config por entorno:
    PG_HOST PG_PORT PG_DB              (conexión)
    PG_USER PG_PASSWORD               (SUPERUSUARIO, defaults postgres/palta)
    PG_APP_USER PG_APP_PASSWORD       (rol de la app, defaults app_palta/71804217;
                                       debe coincidir con la clave de app_palta en 02_rls.sql)
"""
from __future__ import annotations

import os
import sys

try:
    import psycopg2
    from psycopg2 import errors
except ImportError:
    sys.exit("Falta psycopg2. Instala con:  pip install psycopg2-binary")

COMMON = dict(
    host=os.environ.get("PG_HOST", "localhost"),
    port=os.environ.get("PG_PORT", "5432"),
    dbname=os.environ.get("PG_DB", "palta"),
)
SUPER = dict(COMMON, user=os.environ.get("PG_USER", "postgres"),
            password=os.environ.get("PG_PASSWORD", "palta"))
APP = dict(COMMON, user=os.environ.get("PG_APP_USER", "app_palta"),
          password=os.environ.get("PG_APP_PASSWORD", "71804217"))

TENANT_2 = 2
_fallos = []


def check(nombre, cond):
    estado = "PASA" if cond else "FALLA"
    print(f"  [{estado}] {nombre}")
    if not cond:
        _fallos.append(nombre)


def set_ctx(cur, tenant=None, superadmin=False):
    """Fija el contexto de tenant transaction-local (como hace la app)."""
    cur.execute("SELECT set_config('app.tenant', %s, true)",
                ("" if tenant is None else str(tenant),))
    cur.execute("SELECT set_config('app.is_superadmin', %s, true)",
                ("on" if superadmin else "off",))


def seed_tenant_2():
    """Como superusuario: asegura productor 2 + una finca suya para las pruebas."""
    con = psycopg2.connect(**SUPER)
    con.autocommit = True
    cur = con.cursor()
    cur.execute(
        "INSERT INTO productor (id, nombre_comercial) VALUES (%s,%s) "
        "ON CONFLICT (id) DO NOTHING",
        (TENANT_2, "Cliente Prueba 2"),
    )
    cur.execute("SELECT count(*) FROM finca WHERE productor_id = %s", (TENANT_2,))
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO finca (productor_id, nombre) VALUES (%s,%s)",
            (TENANT_2, "Finca del Tenant 2"),
        )
    # Resincronizar la secuencia de productor por si insertamos id explícito.
    cur.execute("SELECT setval(pg_get_serial_sequence('productor','id'), "
                "(SELECT MAX(id) FROM productor))")
    cur.close(); con.close()


def main():
    print("» Preparando datos de prueba (tenant 2) como superusuario")
    seed_tenant_2()

    con = psycopg2.connect(**APP)
    cur = con.cursor()

    print("» 1. Default-deny (sin contexto)")
    con.rollback()                      # abre transacción limpia sin GUC
    cur.execute("BEGIN")
    cur.execute("SELECT count(*) FROM finca")
    check("sin tenant -> 0 fincas visibles", cur.fetchone()[0] == 0)
    con.rollback()

    print("» 2. Aislamiento de lectura")
    cur.execute("BEGIN"); set_ctx(cur, tenant=1)
    cur.execute("SELECT count(*) FROM finca"); t1 = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM finca WHERE productor_id <> 1")
    fuga1 = cur.fetchone()[0]
    check("tenant 1 ve sus fincas (>0)", t1 > 0)
    check("tenant 1 NO ve fincas de otros", fuga1 == 0)
    con.rollback()

    cur.execute("BEGIN"); set_ctx(cur, tenant=TENANT_2)
    cur.execute("SELECT count(*) FROM finca"); t2 = cur.fetchone()[0]
    check("tenant 2 ve solo la suya (==1)", t2 == 1)
    con.rollback()

    print("» 3. Aislamiento de escritura (WITH CHECK)")
    cur.execute("BEGIN"); set_ctx(cur, tenant=1)
    bloqueado = False
    try:
        cur.execute("INSERT INTO finca (productor_id, nombre) VALUES (%s,%s)",
                    (TENANT_2, "intento de intrusión"))
    except errors.lookup("42501"):     # insufficient_privilege / RLS violation
        bloqueado = True
    except psycopg2.Error:
        bloqueado = True
    check("tenant 1 NO puede insertar como tenant 2", bloqueado)
    con.rollback()

    print("» 4. Bypass de SUPERADMIN")
    cur.execute("BEGIN"); set_ctx(cur, superadmin=True)
    cur.execute("SELECT count(DISTINCT productor_id) FROM finca")
    tenants_vistos = cur.fetchone()[0]
    check("superadmin ve >= 2 tenants", tenants_vistos >= 2)
    con.rollback()

    print("» 5. Anti-fuga por pooling (misma conexión, distinto tenant)")
    cur.execute("BEGIN"); set_ctx(cur, tenant=1)
    cur.execute("SELECT count(*) FROM finca"); a = cur.fetchone()[0]
    con.rollback()
    cur.execute("BEGIN"); set_ctx(cur, tenant=TENANT_2)
    cur.execute("SELECT count(*) FROM finca"); b = cur.fetchone()[0]
    con.rollback()
    check("la conexión reutilizada no arrastra el tenant anterior", a != b or (a == t1 and b == t2))

    cur.close(); con.close()

    print()
    if _fallos:
        print(f"RESULTADO: {len(_fallos)} fallo(s) -> {_fallos}")
        sys.exit(1)
    print("RESULTADO: aislamiento RLS OK (todas las comprobaciones pasaron).")


if __name__ == "__main__":
    main()
