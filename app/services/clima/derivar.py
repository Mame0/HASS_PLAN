"""
Deriva las 12 variables climáticas del modelo a partir de una serie horaria.

Cada hora de la serie cuenta como 1 hora, por lo que los umbrales de horas frío/calor
son conteos directos. Estas 12 claves coinciden con las columnas climáticas de
RegistroAgronomico (CLIMATE_FEATURES) y con las del dataset original.
"""
from statistics import mean

from app.services.clima.base import SerieHoraria


def _limpiar(valores):
    """Quita None y sentinelas (NASA POWER usa -999 para faltantes)."""
    return [v for v in valores if v is not None and v > -900]


def _promedio_diario(valores, agg, horas_por_dia=24):
    """
    Agrega por día (chunks de 24 h) y promedia el resultado entre días.
    Con agg=min -> promedio de las mínimas diarias; agg=max -> de las máximas.
    Es la convención agro-meteorológica para T° mín/máx (no el extremo absoluto).
    """
    dias = []
    for i in range(0, len(valores), horas_por_dia):
        dia = _limpiar(valores[i:i + horas_por_dia])
        if dia:
            dias.append(agg(dia))
    return round(mean(dias), 2) if dias else None


def derivar_features(serie: SerieHoraria) -> dict:
    """
    Devuelve un dict con las 12 features climáticas.
    Lanza ValueError si no hay datos de temperatura (sin temperatura no hay nada que derivar).
    """
    T = _limpiar(serie.temperatura)
    if not T:
        raise ValueError("La serie no contiene datos de temperatura.")

    RH = _limpiar(serie.humedad)
    P = _limpiar(serie.precipitacion)
    E = _limpiar(serie.eto)

    return {
        # Horas frío (Σ horas por debajo del umbral)
        "hfrio_19":    float(sum(1 for t in T if t < 19)),
        "hfrio_15":    float(sum(1 for t in T if t < 15)),
        "hfrio_14":    float(sum(1 for t in T if t < 14)),
        "hfrio_14_19": float(sum(1 for t in T if 14 <= t < 19)),
        # Horas calor (Σ horas en cada franja)
        "hac_20_25":   float(sum(1 for t in T if 20 <= t < 25)),
        "hac_25":      float(sum(1 for t in T if t > 25)),
        # Temperatura (t_min/t_max = promedio de extremos diarios, no absolutos)
        "t_prom":      round(mean(T), 2),
        "t_min":       _promedio_diario(serie.temperatura, min),
        "t_max":       _promedio_diario(serie.temperatura, max),
        # Resto de clima
        "humedad":     round(mean(RH), 2) if RH else None,
        "lluvia":      round(sum(P), 2) if P else None,
        "eto":         round(sum(E), 2) if E else None,
    }
