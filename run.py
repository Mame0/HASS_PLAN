"""Punto de entrada del Sistema de Gestion y Planificacion del Cultivo de Palta Hass."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
