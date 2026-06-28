"""
Tests de AISLAMIENTO e INTEGRIDAD de la jerarquía (a nivel de aplicación).

Jerarquía: Productor -> Finca -> Campaña (1 activa por finca) -> Lotes/Planes/...

Verifica que los datos quedan separados por finca y que la app no permite mezclarlos.
(El aislamiento entre PRODUCTORES por RLS se prueba en scripts/migracion/verificar_rls.py,
que requiere PostgreSQL; aquí se corre sobre el SQLite aislado de los tests.)
"""
from datetime import date


def _finca(c, nombre):
    return c.post("/api/fincas", json={"nombre": nombre}).get_json()


def _camp(c, finca_id, nombre):
    return c.post("/api/campanas", json={
        "nombre": nombre, "finca_id": finca_id,
        "fecha_inicio": "2024-07-01", "fecha_fin": "2025-06-30",
    }).get_json()


def test_campanas_separadas_por_finca(app):
    """Cada finca solo ve SUS campañas; el filtro por finca no trae las de otra."""
    c = app.test_client()
    fa = _finca(c, "Finca A")["id"]
    fb = _finca(c, "Finca B")["id"]
    _camp(c, fa, "A1")
    _camp(c, fb, "B1")
    _camp(c, fb, "B2")

    a = c.get(f"/api/campanas?finca_id={fa}").get_json()
    b = c.get(f"/api/campanas?finca_id={fb}").get_json()
    assert {x["nombre"] for x in a} == {"A1"}
    assert {x["nombre"] for x in b} == {"B1", "B2"}
    assert all(x["finca_id"] == fa for x in a)
    assert all(x["finca_id"] == fb for x in b)


def test_una_activa_por_finca_es_independiente(app):
    """Activar una campaña cierra solo la activa de SU finca; otras fincas no se tocan."""
    c = app.test_client()
    fa = _finca(c, "A")["id"]
    fb = _finca(c, "B")["id"]
    a1 = _camp(c, fa, "A1")
    a2 = _camp(c, fa, "A2")
    b1 = _camp(c, fb, "B1")

    c.post(f"/api/campanas/{a1['id']}/activar")
    c.post(f"/api/campanas/{b1['id']}/activar")   # otra finca: no afecta a A1
    c.post(f"/api/campanas/{a2['id']}/activar")   # misma finca: cierra A1

    est = {x["nombre"]: x["estado"] for x in c.get("/api/campanas").get_json()}
    assert est["A2"] == "activa"
    assert est["A1"] == "cerrada"
    assert est["B1"] == "activa"      # intacta: es de otra finca


def test_campana_requiere_finca(app):
    """No se puede crear una campaña sin finca (pertenece a una finca)."""
    c = app.test_client()
    r = c.post("/api/campanas", json={
        "nombre": "x", "fecha_inicio": "2024-07-01", "fecha_fin": "2025-06-30"})
    assert r.status_code == 400


def test_lote_de_otra_finca_no_entra_a_campana(app):
    """Un lote solo puede vivir en campañas de su MISMA finca."""
    c = app.test_client()
    fa = _finca(c, "A")["id"]
    fb = _finca(c, "B")["id"]
    campA = _camp(c, fa, "A1")
    # Intentar crear un lote en la finca B asociándolo a una campaña de la finca A.
    r = c.post(f"/api/fincas/{fb}/lotes",
               json={"nombre": "LB", "area_ha": 3.0, "campana_id": campA["id"]})
    assert r.status_code == 400
    # Y no debe haber quedado ningún lote huérfano en la finca B.
    assert c.get(f"/api/fincas/{fb}/lotes").get_json() == []


def test_lote_misma_finca_si_entra(app):
    """Caso feliz: lote en la finca de la campaña -> se crea y asocia."""
    c = app.test_client()
    fa = _finca(c, "A")["id"]
    campA = _camp(c, fa, "A1")
    r = c.post(f"/api/fincas/{fa}/lotes",
               json={"nombre": "LA", "area_ha": 4.0, "campana_id": campA["id"]})
    assert r.status_code == 201
    lotes = c.get(f"/api/campanas/{campA['id']}/lotes").get_json()
    assert {l["nombre"] for l in lotes} == {"LA"}


def test_operar_lote_en_campana_donde_no_participa_409(app):
    """Predicción/variables exigen que el lote PARTICIPE en esa campaña (lote_campana)."""
    c = app.test_client()
    fa = _finca(c, "A")["id"]
    campA1 = _camp(c, fa, "A1")
    campA2 = _camp(c, fa, "A2")
    # Lote creado y asociado SOLO a A1 (misma finca que A2, pero no participa en A2).
    lote = c.post(f"/api/fincas/{fa}/lotes",
                  json={"nombre": "LA", "area_ha": 3.0, "campana_id": campA1["id"]}).get_json()
    assert c.post(f"/api/lotes/{lote['id']}/prediccion?campana_id={campA2['id']}").status_code == 409
    assert c.get(f"/api/lotes/{lote['id']}/variables?campana_id={campA2['id']}").status_code == 409
    # En su campaña sí participa: variables responde 200.
    assert c.get(f"/api/lotes/{lote['id']}/variables?campana_id={campA1['id']}").status_code == 200


def test_borrar_finca_cascada_a_sus_campanas_y_lotes(app):
    """Borrar una finca elimina SUS campañas y lotes (cascada), sin tocar otra finca."""
    c = app.test_client()
    fa = _finca(c, "A")["id"]
    fb = _finca(c, "B")["id"]
    campA = _camp(c, fa, "A1")
    _camp(c, fb, "B1")
    c.post(f"/api/fincas/{fa}/lotes", json={"nombre": "LA", "area_ha": 2.0, "campana_id": campA["id"]})

    c.delete(f"/api/fincas/{fa}")

    assert c.get(f"/api/campanas?finca_id={fa}").get_json() == []
    assert c.get(f"/api/fincas/{fa}/lotes").status_code == 404   # finca ya no existe
    # La otra finca sigue intacta.
    assert {x["nombre"] for x in c.get(f"/api/campanas?finca_id={fb}").get_json()} == {"B1"}
