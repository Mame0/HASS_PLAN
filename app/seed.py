"""Datos semilla del sistema (se ejecuta al crear la app si las tablas están vacías)."""
from app.models import db, FuenteDatos

# Las 5 fuentes meteorológicas del módulo M10 (Fuentes de datos)
FUENTES = [
    {"nombre": "Open-Meteo Historical", "tipo": "open_meteo",
     "endpoint": "https://archive-api.open-meteo.com/v1/archive",
     "resolucion": "horario · 0.1°", "activa": True},
    {"nombre": "NASA POWER", "tipo": "nasa_power",
     "endpoint": "https://power.larc.nasa.gov/api/temporal/hourly/point",
     "resolucion": "horario · 0.5°", "activa": True},
    {"nombre": "AgERA5 (Copernicus)", "tipo": "agera5",
     "endpoint": "https://cds.climate.copernicus.eu/api/v2",
     "resolucion": "diario · 0.1°", "activa": False},
    {"nombre": "Estaciones Davis (local)", "tipo": "davis",
     "endpoint": "", "resolucion": "horario · estación", "activa": False},
    {"nombre": "Override manual", "tipo": "manual",
     "endpoint": "", "resolucion": "—", "activa": True},
]


def seed_fuentes():
    """Inserta las fuentes de datos solo si la tabla está vacía (idempotente)."""
    if FuenteDatos.query.count() > 0:
        return
    for f in FUENTES:
        db.session.add(FuenteDatos(**f))
    db.session.commit()
