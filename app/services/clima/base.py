"""Contrato común de los proveedores meteorológicos."""
from dataclasses import dataclass, field


@dataclass
class SerieHoraria:
    """
    Serie horaria de una ventana de campaña para un punto (lat, lon).
    Las listas están alineadas por hora. `eto` puede venir vacía si la fuente
    no entrega evapotranspiración (p. ej. el fallback NASA POWER).
    """
    temperatura: list = field(default_factory=list)    # °C por hora
    humedad: list = field(default_factory=list)        # % HR por hora
    precipitacion: list = field(default_factory=list)  # mm por hora
    eto: list = field(default_factory=list)            # mm por hora (opcional)

    def horas(self):
        return len(self.temperatura)


class ProveedorClima:
    """Interfaz: dada una ubicación y una ventana, devuelve la serie horaria."""

    tipo = "base"

    def obtener_serie(self, lat, lon, desde, hasta) -> SerieHoraria:
        raise NotImplementedError
