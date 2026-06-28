"""
Validaciones de entrada de los CRUD (Fase 2).

Cada función limpia/valida y devuelve el valor correcto, o lanza ValueError con un
mensaje claro. Los endpoints capturan ValueError -> HTTP 400. Centralizar aquí evita
repetir reglas y cumple el gate del DICCIONARIO_DATOS.md.
"""
from datetime import date


def texto_requerido(valor, campo):
    if valor is None or str(valor).strip() == "":
        raise ValueError(f"'{campo}' es obligatorio.")
    return str(valor).strip()


def fecha(valor, campo):
    """Acepta 'YYYY-MM-DD' (o date) y devuelve un date."""
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except (ValueError, TypeError):
        raise ValueError(f"'{campo}' debe tener formato YYYY-MM-DD.")


def numero_positivo(valor, campo):
    try:
        v = float(valor)
    except (ValueError, TypeError):
        raise ValueError(f"'{campo}' debe ser un número.")
    if v <= 0:
        raise ValueError(f"'{campo}' debe ser mayor que 0.")
    return v


def entero_no_negativo(valor, campo, permitir_none=True):
    if valor is None:
        if permitir_none:
            return None
        raise ValueError(f"'{campo}' es obligatorio.")
    try:
        v = int(valor)
    except (ValueError, TypeError):
        raise ValueError(f"'{campo}' debe ser un entero.")
    if v < 0:
        raise ValueError(f"'{campo}' no puede ser negativo.")
    return v


def ventana_campana(inicio, fin):
    """Valida que fecha_inicio < fecha_fin."""
    di, df = fecha(inicio, "fecha_inicio"), fecha(fin, "fecha_fin")
    if di >= df:
        raise ValueError("La fecha de inicio debe ser anterior a la de fin.")
    return di, df
