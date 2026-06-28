"""
Autenticación y selección de tenant.

POST /api/auth/login    -> valida credenciales y fija el tenant en la sesión
POST /api/auth/logout   -> limpia la sesión
GET  /api/auth/me       -> usuario/tenant actual

En PostgreSQL el lookup usa la función SECURITY DEFINER app_login_lookup(), única
superficie que puentea RLS para encontrar al usuario ANTES de conocer su tenant.
En SQLite (tests) se consulta el modelo Usuario directamente.
"""
from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.security import check_password_hash
from sqlalchemy import text

from app.models import db, Usuario
from app.tenant_ctx import set_tenant

bp = Blueprint("auth", __name__)


def _buscar_usuario(identificador):
    """Devuelve un dict con los datos mínimos de login, o None."""
    if current_app.config.get("IS_POSTGRES"):
        row = db.session.execute(
            text("""
                SELECT id, productor_id, nombre_usuario, contrasena_hash,
                       tipo_usuario, activo
                FROM app_login_lookup(:ident)
            """),
            {"ident": identificador},
        ).mappings().first()
        return dict(row) if row else None

    u = Usuario.query.filter(
        ((Usuario.correo == identificador) | (Usuario.nombre_usuario == identificador)),
        Usuario.activo.is_(True),
    ).first()
    if not u:
        return None
    return {
        "id": u.id, "productor_id": u.productor_id,
        "nombre_usuario": u.nombre_usuario,
        "contrasena_hash": u.contrasena_hash,
        "tipo_usuario": u.tipo_usuario, "activo": u.activo,
    }


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    identificador = (data.get("usuario") or data.get("correo") or "").strip()
    clave = data.get("clave") or data.get("password") or ""
    if not identificador or not clave:
        return jsonify(error="Faltan credenciales"), 400

    u = _buscar_usuario(identificador)
    if not u or not u["activo"] or not check_password_hash(u["contrasena_hash"], clave):
        return jsonify(error="Credenciales inválidas"), 401

    es_super = u["tipo_usuario"] == "SUPERADMIN"
    # Persistir en la sesión Flask (la lee before_request en cada request).
    session["usuario_id"] = u["id"]
    session["productor_id"] = u["productor_id"]
    session["nombre_usuario"] = u["nombre_usuario"]
    session["tipo_usuario"] = u["tipo_usuario"]
    session["is_superadmin"] = es_super
    # Y fijarlo ya para lo que reste de ESTE request.
    set_tenant(u["productor_id"], es_super)

    return jsonify(
        usuario_id=u["id"],
        productor_id=u["productor_id"],
        nombre_usuario=u["nombre_usuario"],
        tipo_usuario=u["tipo_usuario"],
        is_superadmin=es_super,
    )


@bp.post("/auth/logout")
def logout():
    session.clear()
    set_tenant(None, False)
    return jsonify(ok=True)


@bp.get("/auth/me")
def me():
    if "usuario_id" not in session:
        return jsonify(error="No autenticado"), 401
    return jsonify(
        usuario_id=session.get("usuario_id"),
        productor_id=session.get("productor_id"),
        nombre_usuario=session.get("nombre_usuario"),
        tipo_usuario=session.get("tipo_usuario"),
        is_superadmin=session.get("is_superadmin", False),
    )
