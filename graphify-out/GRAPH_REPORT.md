# Graph Report - .  (2026-06-16)

## Corpus Check
- 9 files · ~40,874 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 572 nodes · 1160 edges · 36 communities (32 shown, 4 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 228 edges (avg confidence: 0.57)
- Token cost: 0 input · 87,538 output

## Community Hubs (Navigation)
- [[_COMMUNITY_API comun y modelos|API comun y modelos]]
- [[_COMMUNITY_Frontend React (modulos UI)|Frontend React (modulos UI)]]
- [[_COMMUNITY_Sincronizacion climatica y variables|Sincronizacion climatica y variables]]
- [[_COMMUNITY_Proveedores meteorologicos|Proveedores meteorologicos]]
- [[_COMMUNITY_Alertas y dashboard (F6)|Alertas y dashboard (F6)]]
- [[_COMMUNITY_Derivados de cosecha (M6M7M8)|Derivados de cosecha (M6/M7/M8)]]
- [[_COMMUNITY_Bootstrap app y validacion de flujo|Bootstrap app y validacion de flujo]]
- [[_COMMUNITY_Planificacion de cosecha (F4)|Planificacion de cosecha (F4)]]
- [[_COMMUNITY_CRUD Fincas y Lotes|CRUD Fincas y Lotes]]
- [[_COMMUNITY_Geometria (centroidearea)|Geometria (centroide/area)]]
- [[_COMMUNITY_Arquitectura del sistema|Arquitectura del sistema]]
- [[_COMMUNITY_Generacion de alertas + tests|Generacion de alertas + tests]]
- [[_COMMUNITY_Predictor ML (OOD)|Predictor ML (OOD)]]
- [[_COMMUNITY_Tests CRUD (F2)|Tests CRUD (F2)]]
- [[_COMMUNITY_Tests derivados (F5)|Tests derivados (F5)]]
- [[_COMMUNITY_Capa de datos frontend (api.js)|Capa de datos frontend (api.js)]]
- [[_COMMUNITY_CRUD campanaslotes front-back|CRUD campanas/lotes front-back]]
- [[_COMMUNITY_Servicio dashboard (KPIs)|Servicio dashboard (KPIs)]]
- [[_COMMUNITY_API Campanas (CRUD+estados)|API Campanas (CRUD+estados)]]
- [[_COMMUNITY_Features del modelo y anti-fuga|Features del modelo y anti-fuga]]
- [[_COMMUNITY_Conceptos de dominio y geo|Conceptos de dominio y geo]]
- [[_COMMUNITY_Fases y reglas de arquitectura|Fases y reglas de arquitectura]]
- [[_COMMUNITY_Patron mutate-in-place (front)|Patron mutate-in-place (front)]]
- [[_COMMUNITY_Domain shift (Nepena-La Joya)|Domain shift (Nepena-La Joya)]]
- [[_COMMUNITY_Shell SPA y vistas de lote|Shell SPA y vistas de lote]]
- [[_COMMUNITY_Comparacion de sitios|Comparacion de sitios]]
- [[_COMMUNITY_Validacion clima Nepena (multi-punto)|Validacion clima Nepena (multi-punto)]]
- [[_COMMUNITY_Jerarquia de dominio y cascada|Jerarquia de dominio y cascada]]
- [[_COMMUNITY_Variable objetivo y resultado|Variable objetivo y resultado]]
- [[_COMMUNITY_Mapa Leaflet (lote)|Mapa Leaflet (lote)]]
- [[_COMMUNITY_Vision del sistema|Vision del sistema]]
- [[_COMMUNITY_Paquete motor climatico|Paquete motor climatico]]
- [[_COMMUNITY_Paquete de servicios|Paquete de servicios]]

## God Nodes (most connected - your core abstractions)
1. `Lote` - 37 edges
2. `RegistroAgronomico` - 35 edges
3. `Finca` - 33 edges
4. `Campana` - 31 edges
5. `FuenteDatos` - 20 edges
6. `Prediccion` - 19 edges
7. `Alerta` - 19 edges
8. `ClimaSync` - 19 edges
9. `useRouter()` - 18 edges
10. `ResultadoCosecha` - 18 edges

## Surprising Connections (you probably didn't know these)
- `GeoJSON como texto en vez de PostGIS` --rationale_for--> `mapa.jsx LeafletMap`  [INFERRED]
  docs/ARQUITECTURA.md → app/frontend/mapa.jsx
- `Flujo en cascada operativo` --semantically_similar_to--> `Variables y fórmulas de planificación F4–F5`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/DICCIONARIO_DATOS.md
- `Regla de capas estricta api->services->models` --rationale_for--> `campanas.crear (POST /campanas)`  [INFERRED]
  CLAUDE.md → app/api/campanas.py
- `campanas.activar (POST /campanas/<id>/activar)` --references--> `Jerarquia de dominio Finca->Lote->Campana->Registro`  [INFERRED]
  app/api/campanas.py → docs/ARQUITECTURA.md
- `campanas.activar (POST /campanas/<id>/activar)` --references--> `Patron lectura window.HP / escritura window.HP.api`  [INFERRED]
  app/api/campanas.py → CLAUDE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CRUD de Campana extremo a extremo (front->API)** — modules_a_campaigns, modules_a_campaignnew, modules_a_campaigndetail, api_hp_api, campanas_crear, campanas_activar [INFERRED 0.85]
- **Patron anti-fuga frutos/peso (front + doc)** — api_fuga_antifuga, claudemd_fuga_datos, arquitectura_15_features [INFERRED 0.85]
- **Capa de datos window.HP (api.js carga, modulos leen)** — api_cargartodo, api_fill, modules_a_dashboard, modules_a_sectors [INFERRED 0.85]

## Communities (36 total, 4 thin omitted)

### Community 0 - "API comun y modelos"
Cohesion: 0.08
Nodes (67): Alerta, Utilidades compartidas por los blueprints de la API: metadatos de variables, loo, serialize_fuente(), serialize_semana(), listar_fuentes(), M10 — Fuentes de datos: listado de proveedores meteorológicos., Alerta, Campana (+59 more)

### Community 1 - "Frontend React (modulos UI)"
Cohesion: 0.05
Nodes (25): fmtNum(), CampaignDetail(), CampaignNew(), Campaigns(), Dashboard(), SectorDetail(), SectorNew(), Sectors() (+17 more)

### Community 2 - "Sincronizacion climatica y variables"
Cohesion: 0.08
Nodes (37): clima_log(), Sincronización climática (motor de variables automáticas por API).  POST /lotes/, sync_lote(), get_campana(), get_or_create_registro(), last_sync(), Serializa una predicción. Si se pasa `resultado` (dict del Predictor),     agreg, Arma la respuesta manual/API de variables para un lote en una campaña. (+29 more)

### Community 3 - "Proveedores meteorologicos"
Cohesion: 0.09
Nodes (25): Validación del motor climático en la ubicación REAL del dataset: Fundo Los Palto, SerieHoraria, SerieHoraria, SerieHoraria, ProveedorClima, Contrato común de los proveedores meteorológicos., Interfaz: dada una ubicación y una ventana, devuelve la serie horaria., Serie horaria de una ventana de campaña para un punto (lat, lon).     Las listas (+17 more)

### Community 4 - "Alertas y dashboard (F6)"
Cohesion: 0.12
Nodes (30): actualizar(), dashboard(), generar(), listar(), _ordenadas(), Alertas + Dashboard (Fase F6 / Módulos 9 y 1).  POST /campanas/<id>/alertas/ge, Más graves primero; dentro de la misma severidad, por semana., get_campana_o_404() (+22 more)

### Community 5 - "Derivados de cosecha (M6/M7/M8)"
Cohesion: 0.11
Nodes (29): Módulos derivados de la cosecha (Fase F5): Mano de Obra (M6), Logística (M7), Tr, DespachoSemanal, ManoObraSemanal, Personal requerido por semana (calculado desde tn_planificada)., Despacho de produccion por semana (camiones/viajes/costo)., _borrar_demo(), cuadrado(), main() (+21 more)

### Community 6 - "Bootstrap app y validacion de flujo"
Cohesion: 0.10
Nodes (18): _ceil(), h(), main(), Validación end-to-end del flujo operativo (F1 → F4 → F5).  Recorre TODO el pipel, Registra todos los blueprints de la API bajo el prefijo /api., register_api(), Sirve el front-end HassPlan (prototipo React servido como estáticos).  - `GET /`, create_app() (+10 more)

### Community 7 - "Planificacion de cosecha (F4)"
Cohesion: 0.11
Nodes (19): serialize_plan_cosecha(), generar(), obtener(), Planificación de cosecha (Módulo 5 / F4).  POST /campanas/<id>/plan-cosecha  ->, reprogramar(), generar_plan_cosecha(), _pesos_campana(), Planificación de cosecha (Módulo 5 / Fase F4).  Distribuye la producción estimad (+11 more)

### Community 8 - "CRUD Fincas y Lotes"
Cohesion: 0.15
Nodes (18): _geojson(), Parsea la geometría guardada como texto a objeto GeoJSON (o None)., serialize_finca(), serialize_lote(), _aplicar_geometria(), crear(), editar(), listar() (+10 more)

### Community 9 - "Geometria (centroide/area)"
Cohesion: 0.18
Nodes (18): _anillo(), area_ha(), centroide(), _geometria(), Calculo de centroide y area desde GeoJSON (Polygon o Point), en Python puro.  Ge, Normaliza str/dict y extrae el dict de geometry (Polygon/Point)., Anillo exterior de un Polygon como lista de [lon, lat] (sin repetir el cierre)., Devuelve (lat, lon) del centroide. Para Point, el propio punto. (+10 more)

### Community 10 - "Arquitectura del sistema"
Cohesion: 0.13
Nodes (19): Modelo de dominio (Finca → Lote → Registro → Predicción → Planes), Stack tecnológico (Flask, SQLite, scikit-learn, React, Leaflet), Flujo en cascada operativo, recalcular_derivados(plan), Separación estricta de capas (api → services → models), F6 Déficits → Alertas + Dashboard, Variables y fórmulas de planificación F4–F5, F5/M7 Logística / Inventario (+11 more)

### Community 11 - "Generacion de alertas + tests"
Cohesion: 0.17
Nodes (14): Generación de alertas (Fase F6 / Módulo 9).  Convierte los déficits por semana d, Severidad por magnitud relativa del déficit: baja ≤15% · media ≤40% · alta >40%., Marca una alerta como resuelta., resolver_alerta(), _severidad(), _montar(), Pruebas F6: alertas (una por semana con déficit) + dashboard consolidado.  Gate:, Campaña activa con 2 lotes predichos + plan + M6/M7/M8. Devuelve (cid, client). (+6 more)

### Community 12 - "Predictor ML (OOD)"
Cohesion: 0.14
Nodes (9): RegistroAgronomico, Predictor, Wrapper del modelo de Machine Learning (Modulo 4: Inteligencia Agricola).  Carga, Carga perezosa del modelo serializado (modelo.pkl)., Metadata del modelo (orden de features + rangos de entrenamiento)., Lista de variables cuyo valor cae fuera del rango de entrenamiento.         Cada, Devuelve un dict:           tn_ha, tn_total, confianza, out_of_distribution[], e, get_predictor() (+1 more)

### Community 13 - "Tests CRUD (F2)"
Cohesion: 0.22
Nodes (7): _finca(), Pruebas F2: CRUD de Campaña, Finca y Lote (con geo) + validaciones y cascada., test_borrado_finca_cascada_a_lotes(), test_editar_lote_rederiva_geometria(), test_lote_poligono_deriva_area_y_centroide(), test_lote_punto_requiere_area(), test_lote_sin_geometria_requiere_area()

### Community 14 - "Tests derivados (F5)"
Cohesion: 0.28
Nodes (12): _campana_con_plan(), _ceil(), Pruebas F5: módulos derivados (mano de obra, logística, transporte) y la cascada, Crea campaña + lotes predichos + plan de cosecha. Devuelve (cid, client, plan_js, test_inventario_logistica_deficit(), test_inventario_negativo_400(), test_mano_obra_detecta_deficit(), test_mano_obra_formula_y_cuadre() (+4 more)

### Community 15 - "Capa de datos frontend (api.js)"
Cohesion: 0.35
Nodes (9): adaptAlerts(), adaptCampaigns(), adaptInventory(), adaptSources(), adaptWeeks(), cargarLotesComoFincas(), cargarTodo(), fill() (+1 more)

### Community 16 - "CRUD campanas/lotes front-back"
Cohesion: 0.22
Nodes (10): api.js cargarLotesComoFincas(), window.HP.api (write helpers), api.js VAR_MAP (snake->camel), campanas.cerrar (POST /campanas/<id>/cerrar), campanas.editar (PUT /campanas/<id>), campanas.eliminar (DELETE /campanas/<id>), modules-a CampaignDetail, modules-a CampaignNew (+2 more)

### Community 17 - "Servicio dashboard (KPIs)"
Cohesion: 0.31
Nodes (9): _area(), _kpi_alertas(), _lotes(), _pico(), Dashboard consolidado (Fase F6 / Módulo 1).  Reúne en un solo objeto los KPIs de, Devuelve (valor_máximo, numero_semana) sobre una lista de filas, o (0, None)., KPIs consolidados de la campaña: predicción, cosecha, M6/M7/M8 y alertas., Conteo de alertas activas por severidad (badge del panel). (+1 more)

### Community 18 - "API Campanas (CRUD+estados)"
Cohesion: 0.33
Nodes (6): activar(), crear(), editar(), listar(), Campañas agrícolas (Módulo 2).  GET    /campanas              -> lista POST   /c, serialize_campana()

### Community 19 - "Features del modelo y anti-fuga"
Cohesion: 0.22
Nodes (9): api.js FUGA anti-leak (frutosArbol/pesoFruto), 15 features del modelo (3 manuales + 12 climáticas), services/clima/derivar.py, scripts/ml/entrenar.py, Pipeline consistente train/inferencia (derivar.py), Fuga de datos: frutos_arbol/peso_fruto nunca features, Dataset_Limpio_ML.csv (217 registros, Nepeña), Variables de entrada al modelo (15 features) (+1 more)

### Community 20 - "Conceptos de dominio y geo"
Cohesion: 0.25
Nodes (8): Campaña (ciclo productivo), Finca (chacra/propiedad), GeoJSON como texto en vez de PostGIS, Lote (parcela, unidad de predicción), Módulo de Mapa (georreferenciación con Leaflet/Geoman), RegistroAgronomico (3 manuales + 12 clima), Motor climático (services/clima), Track B B2 Motor climático (Open-Meteo + NASA POWER)

### Community 21 - "Fases y reglas de arquitectura"
Cohesion: 0.25
Nodes (8): Capas (separacion estricta), Dos ubicaciones (Nepeña entrena, La Joya despliega), Esquema de fases F0.5–F7 (fuente de verdad), campanas.crear (POST /campanas), Regla de capas estricta api->services->models, Referencia operativa La Joya (Arequipa), Roadmap de fases (historico Track A/B), Gate de verificación por fase

### Community 22 - "Patron mutate-in-place (front)"
Cohesion: 0.33
Nodes (5): api.js cargarTodo(), api.js fill() (mutate in-place), campanas.listar (GET /campanas), Trampa: desestructuran window.HP -> mutar in-place, modules-a Campaigns (M2)

### Community 23 - "Domain shift (Nepena-La Joya)"
Cohesion: 0.33
Nodes (6): Dos ubicaciones Nepena/La Joya, Prediccion + bandera OOD, Domain shift de dos sitios (Nepeña → La Joya), Domain shift Nepena -> La Joya (OOD), modelo_meta.json (rangos OOD autoritativos), Rendimiento La Joya 14–24 t/ha

### Community 24 - "Shell SPA y vistas de lote"
Cohesion: 0.47
Nodes (6): HassPlan.html (SPA shell, no build), icons.jsx Icon, mapa.jsx LeafletMap, modules-a Dashboard (M1), modules-a SectorDetail, modules-a SectorNew (lote + mapa)

### Community 25 - "Comparacion de sitios"
Cohesion: 0.70
Nodes (4): features(), limpiar(), prom_diario(), Cuantifica la BRECHA DE DOMINIO entre el sitio de entrenamiento (Nepena, costa)

### Community 26 - "Validacion clima Nepena (multi-punto)"
Cohesion: 0.70
Nodes (4): features(), limpiar(), prom_diario(), Afina la ubicacion del Fundo Los Paltos (Nepena, Ancash) probando varios puntos

### Community 27 - "Jerarquia de dominio y cascada"
Cohesion: 0.40
Nodes (5): Jerarquia de dominio Finca->Lote->Campana->Registro, campanas.activar (POST /campanas/<id>/activar), Flujo en cascada (corazon operativo), Patron lectura window.HP / escritura window.HP.api, Referencia de diseno UI Sismagro v5.1.0

### Community 28 - "Variable objetivo y resultado"
Cohesion: 0.50
Nodes (4): Regla anti-fuga de datos (frutos/peso), Comparación predicho vs real (error_vs), Variable objetivo Tn/Ha, Variables de resultado (frutos_arbol, peso_fruto)

## Knowledge Gaps
- **32 isolated node(s):** `NAV`, `CRUMBS`, `ROUTE_TO_NAV`, `RouterCtx`, `Sistema de Gestión y Planificación Operativa Palta Hass` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RegistroAgronomico` connect `API comun y modelos` to `Sincronizacion climatica y variables`, `Derivados de cosecha (M6/M7/M8)`, `Bootstrap app y validacion de flujo`, `Generacion de alertas + tests`, `Predictor ML (OOD)`, `Tests derivados (F5)`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `Lote` connect `API comun y modelos` to `Sincronizacion climatica y variables`, `Derivados de cosecha (M6/M7/M8)`, `Bootstrap app y validacion de flujo`, `CRUD Fincas y Lotes`, `Generacion de alertas + tests`, `Tests derivados (F5)`, `Servicio dashboard (KPIs)`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Why does `derivar_features()` connect `Proveedores meteorologicos` to `Sincronizacion climatica y variables`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `Lote` (e.g. with `Alerta` and `Campana`) actually correct?**
  _`Lote` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `RegistroAgronomico` (e.g. with `Alerta` and `RegistroAgronomico`) actually correct?**
  _`RegistroAgronomico` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Finca` (e.g. with `Alerta` and `Campana`) actually correct?**
  _`Finca` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Campana` (e.g. with `Alerta` and `Campana`) actually correct?**
  _`Campana` has 11 INFERRED edges - model-reasoned connections that need verification._