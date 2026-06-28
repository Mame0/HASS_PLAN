"""Endpoint de salud para verificar que el backend responde."""
from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return jsonify(status="ok", service="HassPlan API", version="0.1")
