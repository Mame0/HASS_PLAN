"""
Capa de sesión multi-tenant: propaga el tenant del request a PostgreSQL (RLS).

Dos piezas:

  1. before_request: lee el usuario logueado de la sesión Flask y fija el
     contexto (productor_id, is_superadmin) en app/tenant_ctx.py.

  2. Listener SQLAlchemy 'after_begin': al ABRIR cada transacción ejecuta
        SELECT set_config('app.tenant', :t, true);
        SELECT set_config('app.is_superadmin', :s, true);
     El tercer parámetro (is_local => true) hace las variables TRANSACTION-LOCAL:
     se borran solas al COMMIT/ROLLBACK, por lo que NO se filtran a otro request
     que reutilice la misma conexión del pool (la trampa clásica de RLS + pool).

Solo actúa sobre PostgreSQL; en SQLite (tests) es un no-op, así RLS no estorba.
"""
from __future__ import annotations

from flask import session, request, jsonify
from sqlalchemy import event, text

from app.tenant_ctx import set_tenant, reset_tenant, get_current_tenant, is_superadmin


def _apply_tenant_guc(connection):
    """Ejecuta los set_config sobre la conexión PostgreSQL de la transacción."""
    if connection.dialect.name != "postgresql":
        return
    tid = get_current_tenant()
    connection.execute(
        text("SELECT set_config('app.tenant', :t, true)"),
        {"t": "" if tid is None else str(tid)},
    )
    connection.execute(
        text("SELECT set_config('app.is_superadmin', :s, true)"),
        {"s": "on" if is_superadmin() else "off"},
    )


def init_tenant(app, db):
    """Cablea el contexto de tenant a la app Flask y a la sesión SQLAlchemy."""

    # (1) Resolver el tenant desde la sesión de login en cada request.
    #     Sin usuario logueado se cae al default single-tenant (DEFAULT_TENANT_ID),
    #     para no romper el front actual ni los tests (que aún no hacen login).
    #     El SUPERADMIN sí puede tener productor_id None (+ flag is_superadmin).
    @app.before_request
    def _load_tenant_from_session():
        if session.get("usuario_id"):
            set_tenant(session.get("productor_id"), session.get("is_superadmin", False))
        else:
            reset_tenant()

    # (1b) Exigir login en /api cuando REQUIRE_LOGIN está activo (modo SaaS).
    #      Públicos: los assets del front (no /api), /api/health y /api/auth/*.
    @app.before_request
    def _require_login():
        if not app.config.get("REQUIRE_LOGIN"):
            return None
        p = request.path
        if not p.startswith("/api/"):
            return None
        if p == "/api/health" or p.startswith("/api/auth/"):
            return None
        if not session.get("usuario_id"):
            return jsonify(error="No autenticado"), 401
        return None

    # (2) Inyectar el GUC al comenzar cada transacción (pooling-safe).
    @event.listens_for(db.session, "after_begin")
    def _set_tenant_guc(sess, transaction, connection):
        _apply_tenant_guc(connection)
