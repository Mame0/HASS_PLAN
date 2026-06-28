"""
Panel del PROVEEDOR (SUPERADMIN): gestión de productores (clientes) y sus usuarios.

Todas las rutas exigen sesión de SUPERADMIN (guard de blueprint -> 403 si no).
El SUPERADMIN opera entre tenants porque su contexto fija app.is_superadmin='on'
(ver app/tenant.py), y las políticas RLS permiten el bypass para ese rol.

  GET  /api/admin/productores                 -> lista de productores + conteos
  POST /api/admin/productores                 -> crea productor (+ admin opcional)
  PUT  /api/admin/productores/<id>            -> edita / activa-desactiva productor
  GET  /api/admin/productores/<id>/usuarios   -> usuarios de un productor
  POST /api/admin/usuarios                     -> crea usuario para un productor
  PUT  /api/admin/usuarios/<id>               -> edita / resetea clave / activa
"""
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models import db, Productor, Usuario, Finca

bp = Blueprint("admin", __name__)

TIPOS_CLIENTE = ("CLIENTE_ADMIN", "CLIENTE_CAMPO")


@bp.before_request
def _solo_superadmin():
    if not session.get("is_superadmin"):
        return jsonify(error="Acceso restringido al proveedor (SUPERADMIN)."), 403
    return None


def _productor_json(p, n_usuarios=0, n_fincas=0):
    return {
        "id": p.id, "nombre_comercial": p.nombre_comercial, "ruc_dni": p.ruc_dni,
        "correo_contacto": p.correo_contacto, "telefono": p.telefono,
        "activo": p.activo,
        "fecha_registro": p.fecha_registro.isoformat() if p.fecha_registro else None,
        "n_usuarios": n_usuarios, "n_fincas": n_fincas,
    }


def _usuario_json(u):
    return {
        "id": u.id, "productor_id": u.productor_id,
        "nombre_usuario": u.nombre_usuario, "correo": u.correo,
        "tipo_usuario": u.tipo_usuario, "activo": u.activo,
    }


# --------------------------------------------------------------------------- #
#  Productores
# --------------------------------------------------------------------------- #
@bp.get("/admin/productores")
def listar_productores():
    usu = dict(db.session.query(Usuario.productor_id, func.count())
               .group_by(Usuario.productor_id).all())
    fin = dict(db.session.query(Finca.productor_id, func.count())
               .group_by(Finca.productor_id).all())
    out = [_productor_json(p, usu.get(p.id, 0), fin.get(p.id, 0))
           for p in Productor.query.order_by(Productor.id).all()]
    return jsonify(out)


@bp.post("/admin/productores")
def crear_productor():
    d = request.get_json(silent=True) or {}
    nombre = (d.get("nombre_comercial") or "").strip()
    if not nombre:
        return jsonify(error="nombre_comercial es obligatorio"), 400

    p = Productor(
        nombre_comercial=nombre,
        ruc_dni=(d.get("ruc_dni") or None),
        correo_contacto=(d.get("correo_contacto") or None),
        telefono=(d.get("telefono") or None),
        activo=bool(d.get("activo", True)),
    )
    db.session.add(p)

    # Admin inicial opcional (un CLIENTE_ADMIN del nuevo productor).
    admin = d.get("admin") or None
    usuario_creado = None
    try:
        db.session.flush()                 # asigna p.id
        if admin and (admin.get("nombre_usuario") and admin.get("clave")):
            usuario_creado = Usuario(
                productor_id=p.id,
                nombre_usuario=admin["nombre_usuario"].strip(),
                correo=(admin.get("correo") or "").strip(),
                contrasena_hash=generate_password_hash(admin["clave"]),
                tipo_usuario="CLIENTE_ADMIN",
                activo=True,
            )
            db.session.add(usuario_creado)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(error="Datos duplicados (RUC/usuario/correo ya existen)."), 400

    res = _productor_json(p, 1 if usuario_creado else 0, 0)
    if usuario_creado:
        res["admin"] = _usuario_json(usuario_creado)
    return jsonify(res), 201


@bp.put("/admin/productores/<int:pid>")
def editar_productor(pid):
    p = db.session.get(Productor, pid)
    if not p:
        return jsonify(error="Productor no encontrado"), 404
    d = request.get_json(silent=True) or {}
    for campo in ("nombre_comercial", "ruc_dni", "correo_contacto", "telefono"):
        if campo in d:
            setattr(p, campo, (d[campo] or None))
    if "activo" in d:
        p.activo = bool(d["activo"])
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="RUC/DNI duplicado."), 400
    return jsonify(_productor_json(p))


# --------------------------------------------------------------------------- #
#  Usuarios
# --------------------------------------------------------------------------- #
@bp.get("/admin/productores/<int:pid>/usuarios")
def listar_usuarios(pid):
    us = Usuario.query.filter_by(productor_id=pid).order_by(Usuario.id).all()
    return jsonify([_usuario_json(u) for u in us])


@bp.post("/admin/usuarios")
def crear_usuario():
    d = request.get_json(silent=True) or {}
    pid = d.get("productor_id")
    nombre = (d.get("nombre_usuario") or "").strip()
    correo = (d.get("correo") or "").strip()
    clave = d.get("clave") or ""
    tipo = d.get("tipo_usuario") or "CLIENTE_CAMPO"
    if not (pid and nombre and correo and clave):
        return jsonify(error="productor_id, nombre_usuario, correo y clave son obligatorios"), 400
    if tipo not in TIPOS_CLIENTE:
        return jsonify(error="tipo_usuario debe ser CLIENTE_ADMIN o CLIENTE_CAMPO"), 400
    if not db.session.get(Productor, pid):
        return jsonify(error="Productor no encontrado"), 404

    u = Usuario(
        productor_id=pid, nombre_usuario=nombre, correo=correo,
        contrasena_hash=generate_password_hash(clave),
        tipo_usuario=tipo, activo=True,
    )
    db.session.add(u)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="nombre_usuario o correo ya existen."), 400
    return jsonify(_usuario_json(u)), 201


@bp.put("/admin/usuarios/<int:uid>")
def editar_usuario(uid):
    u = db.session.get(Usuario, uid)
    if not u:
        return jsonify(error="Usuario no encontrado"), 404
    d = request.get_json(silent=True) or {}
    if "correo" in d:
        u.correo = (d["correo"] or "").strip()
    if "tipo_usuario" in d:
        if d["tipo_usuario"] not in TIPOS_CLIENTE:
            return jsonify(error="tipo_usuario inválido"), 400
        u.tipo_usuario = d["tipo_usuario"]
    if "activo" in d:
        u.activo = bool(d["activo"])
    if d.get("clave"):
        u.contrasena_hash = generate_password_hash(d["clave"])
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="Correo duplicado."), 400
    return jsonify(_usuario_json(u))
