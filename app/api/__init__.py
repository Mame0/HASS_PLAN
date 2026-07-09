"""
Capa API REST (JSON) del backend HassPlan.

Cada modulo define un Blueprint `bp`; `register_api(app)` los monta todos bajo /api.
El front-end (prototipo HassPlan) consume estos endpoints en lugar del estado simulado.
"""


def register_api(app):
    """Registra todos los blueprints de la API bajo el prefijo /api."""
    from app.api.health import bp as health_bp
    from app.api.auth import bp as auth_bp
    from app.api.admin import bp as admin_bp
    from app.api.fuentes import bp as fuentes_bp
    from app.api.campanas import bp as campanas_bp
    from app.api.fincas import bp as fincas_bp
    from app.api.lotes import bp as lotes_bp
    from app.api.variables import bp as variables_bp
    from app.api.clima import bp as clima_bp
    from app.api.prediccion import bp as prediccion_bp
    from app.api.cosecha import bp as cosecha_bp
    from app.api.resultado import bp as resultado_bp
    from app.api.derivados import bp as derivados_bp
    from app.api.alertas import bp as alertas_bp
    from app.api.fundo import bp as fundo_bp

    blueprints = (health_bp, auth_bp, admin_bp, fuentes_bp, campanas_bp, fincas_bp, lotes_bp,
                  variables_bp, clima_bp, prediccion_bp, cosecha_bp, resultado_bp, derivados_bp,
                  alertas_bp, fundo_bp)
    for bp in blueprints:
        app.register_blueprint(bp, url_prefix="/api")
