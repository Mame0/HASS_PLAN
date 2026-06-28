"""
Motor de variables climáticas por API.

Convierte la ubicación de un lote + la ventana de una campaña en las 12 variables
climáticas que consume el modelo, llamando a un proveedor meteorológico (Open-Meteo
como primario, NASA POWER como fallback) y derivando las features de la serie horaria.
"""
