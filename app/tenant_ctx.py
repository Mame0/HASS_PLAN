"""
Contexto de tenant (productor) para el aislamiento multi-tenant.

Aislado en su propio módulo SIN dependencias de SQLAlchemy para que tanto los
modelos (app/models.py) como la capa de sesión (app/tenant.py) puedan importarlo
sin ciclos.

El tenant "actual" vive en un contextvars.ContextVar: es seguro frente a hilos y
a corrutinas, y NO se comparte entre requests del pool de Flask. La capa de
sesión (app/tenant.py) lo fija por request y lo propaga a PostgreSQL vía
set_config(..., is_local=true) dentro de la transacción.
"""
from __future__ import annotations

import contextvars

# Productor por defecto cuando no hay contexto explícito (modo single-tenant:
# tests sobre SQLite y la data migrada en Fase 3, toda del productor 1).
DEFAULT_TENANT_ID = 1

_tenant_id = contextvars.ContextVar("productor_id", default=DEFAULT_TENANT_ID)
_is_superadmin = contextvars.ContextVar("is_superadmin", default=False)


def set_tenant(productor_id, is_superadmin=False):
    """Fija el tenant del contexto actual. productor_id=None => sin tenant."""
    _tenant_id.set(productor_id)
    _is_superadmin.set(bool(is_superadmin))


def get_current_tenant():
    """productor_id del contexto actual (lo usan los modelos como default)."""
    return _tenant_id.get()


def is_superadmin():
    return _is_superadmin.get()


def reset_tenant():
    """Restaura el default (útil al cerrar un request o en pruebas)."""
    _tenant_id.set(DEFAULT_TENANT_ID)
    _is_superadmin.set(False)
