"""Pruebas F2: CRUD de Campaña, Finca y Lote (con geo) + validaciones y cascada."""
import math

# Cuadrado de ~1 ha en La Joya para el dibujo de lotes (polígono).
LAT0, LON0 = -16.59, -71.92
DLAT = 100 / 110574
DLON = 100 / (111320 * math.cos(math.radians(LAT0)))
POLY = {"type": "Polygon", "coordinates": [[
    [LON0, LAT0], [LON0 + DLON, LAT0],
    [LON0 + DLON, LAT0 + DLAT], [LON0, LAT0 + DLAT], [LON0, LAT0],
]]}
PUNTO = {"type": "Point", "coordinates": [LON0, LAT0]}


# ---------------------------- Campañas ----------------------------

def test_campana_crud_y_una_sola_activa(app):
    c = app.test_client()
    fid = c.post("/api/fincas", json={"nombre": "Chacra"}).get_json()["id"]
    a = c.post("/api/campanas", json={"nombre": "23-24", "finca_id": fid,
               "fecha_inicio": "2023-07-01", "fecha_fin": "2024-06-30"}).get_json()
    b = c.post("/api/campanas", json={"nombre": "24-25", "finca_id": fid,
               "fecha_inicio": "2024-07-01", "fecha_fin": "2025-06-30"}).get_json()
    assert a["estado"] == "borrador"

    c.post(f"/api/campanas/{a['id']}/activar")
    c.post(f"/api/campanas/{b['id']}/activar")     # activar B debe cerrar A

    estados = {x["nombre"]: x["estado"] for x in c.get("/api/campanas").get_json()}
    assert estados["24-25"] == "activa"
    assert estados["23-24"] == "cerrada"


def test_campana_fechas_invalidas_400(app):
    r = app.test_client().post("/api/campanas", json={
        "nombre": "x", "fecha_inicio": "2025-01-01", "fecha_fin": "2024-01-01"})
    assert r.status_code == 400


# ----------------------------- Fincas -----------------------------

def test_finca_con_geometria_deriva_centroide(app):
    f = app.test_client().post("/api/fincas", json={
        "nombre": "Chacra La Joya", "distrito": "La Joya, Arequipa",
        "geometria": POLY}).get_json()
    assert f["centro_lat"] is not None and f["centro_lon"] is not None
    assert f["n_lotes"] == 0


def test_finca_nombre_obligatorio_400(app):
    assert app.test_client().post("/api/fincas", json={"distrito": "x"}).status_code == 400


def test_finca_area_total_suma_lotes(app):
    c = app.test_client()
    fid = c.post("/api/fincas", json={"nombre": "F"}).get_json()["id"]
    c.post(f"/api/fincas/{fid}/lotes", json={"nombre": "L1", "area_ha": 2.0})
    c.post(f"/api/fincas/{fid}/lotes", json={"nombre": "L2", "area_ha": 3.5})
    f = c.get(f"/api/fincas/{fid}").get_json()
    assert f["area_total_ha"] == 5.5


# ------------------------- Lotes (con geo) ------------------------

def _finca(c):
    return c.post("/api/fincas", json={"nombre": "F"}).get_json()["id"]


def test_lote_poligono_deriva_area_y_centroide(app):
    c = app.test_client()
    fid = _finca(c)
    l = c.post(f"/api/fincas/{fid}/lotes", json={"nombre": "Lote 1", "geometria": POLY}).get_json()
    assert abs(l["area_ha"] - 1.0) < 0.02            # área derivada del polígono
    assert l["latitud"] is not None
    assert l["finca_id"] == fid


def test_lote_punto_requiere_area(app):
    c = app.test_client()
    fid = _finca(c)
    # punto sin área -> 400
    r = c.post(f"/api/fincas/{fid}/lotes", json={"nombre": "L", "geometria": PUNTO})
    assert r.status_code == 400
    # punto con área -> ok, centroide = punto
    l = c.post(f"/api/fincas/{fid}/lotes",
               json={"nombre": "L", "geometria": PUNTO, "area_ha": 3.5}).get_json()
    assert l["area_ha"] == 3.5
    assert abs(l["latitud"] - LAT0) < 1e-9


def test_lote_sin_geometria_requiere_area(app):
    c = app.test_client()
    fid = _finca(c)
    assert c.post(f"/api/fincas/{fid}/lotes", json={"nombre": "L"}).status_code == 400
    l = c.post(f"/api/fincas/{fid}/lotes", json={"nombre": "L", "area_ha": 2.0}).get_json()
    assert l["area_ha"] == 2.0


def test_borrado_finca_cascada_a_lotes(app):
    c = app.test_client()
    fid = _finca(c)
    c.post(f"/api/fincas/{fid}/lotes", json={"nombre": "L1", "area_ha": 1})
    c.post(f"/api/fincas/{fid}/lotes", json={"nombre": "L2", "area_ha": 1})
    assert len(c.get(f"/api/fincas/{fid}/lotes").get_json()) == 2
    assert c.delete(f"/api/fincas/{fid}").status_code == 204
    # la finca ya no existe y sus lotes tampoco
    assert c.get(f"/api/fincas/{fid}").status_code == 404


def test_editar_lote_rederiva_geometria(app):
    c = app.test_client()
    fid = _finca(c)
    l = c.post(f"/api/fincas/{fid}/lotes", json={"nombre": "L", "area_ha": 9}).get_json()
    # al asignar un polígono, el área pasa a derivarse (~1 ha)
    edit = c.put(f"/api/lotes/{l['id']}", json={"geometria": POLY}).get_json()
    assert abs(edit["area_ha"] - 1.0) < 0.02
