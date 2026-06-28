"""Factory de la aplicacion Flask."""
import os
from flask import Flask
from config import Config
from app.models import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    es_postgres = str(app.config.get("SQLALCHEMY_DATABASE_URI", "")).startswith("postgresql")

    # Asegurar que exista la carpeta instance/ para la base de datos SQLite
    os.makedirs(os.path.join(app.root_path, "..", "instance"), exist_ok=True)

    db.init_app(app)

    # Capa multi-tenant: propaga el tenant del request a PostgreSQL (RLS).
    # Importa modelos Productor/Usuario al estar en app.models.
    from app.tenant import init_tenant
    init_tenant(app, db)

    with app.app_context():
        # En PostgreSQL el esquema lo crean los scripts sql/ (DDL + RLS), no el
        # ORM: create_all NO sabe de FK compuestas ni de políticas RLS. Solo se
        # usa create_all en SQLite (desarrollo/tests).
        if not es_postgres:
            db.create_all()
        from app.seed import seed_fuentes
        seed_fuentes()            # siembra las fuentes de datos si la tabla esta vacia

    # API REST (JSON) que consume el front HassPlan
    from app.api import register_api
    register_api(app)

    # Front-end HassPlan (SPA servida como estáticos en /)
    from app.frontend_bp import bp as frontend_bp
    app.register_blueprint(frontend_bp)

    return app
