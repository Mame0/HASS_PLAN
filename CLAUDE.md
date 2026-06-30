# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> El proyecto se trabaja **en español** (código, comentarios, docs y commits). Es una **tesis**:
> se prioriza el planteamiento correcto sobre la velocidad — cerrar el diseño de variables/fórmulas
> antes de codificar, y verificar cada fase contra su *gate* antes de avanzar.

## Qué es esto

**Sistema de Gestión y Planificación Operativa del Cultivo de Palta Hass**. A partir de variables
agronómicas/climáticas predice el rendimiento (Tn/Ha) y, sobre esa predicción, **planifica** cosecha,
mano de obra, logística y transporte, con alertas y dashboard. **El ML es un módulo de soporte, no el
centro**: el foco es la gestión operativa. Desde jun-2026 es un **SaaS multi-tenant**: varios productores
comparten BD PostgreSQL, aislados por **Row Level Security** (cada productor solo ve sus datos), con login
y un panel de SUPERADMIN. La UX de cada cliente sigue pensada para **un** productor con **una** finca.

## Estructura del repositorio (raíz `c:\Tesis`)

- **`sistema_palta/`** — la app web (Flask). **Todo el desarrollo y los comandos van aquí.**
- `MODELO/Modelo_ml/` — notebook ML original (`therealML_PALTA.ipynb`) + dataset `Dataset_Limpio_ML.csv`.
- `REFERENCIAS/` — PDFs académicos. Doc base: investigación de Fundo Los Paltos (Nepeña).

## Comandos (ejecutar desde `sistema_palta/`)

```bash
pip install -r requirements.txt        # Flask 3, Flask-SQLAlchemy, scikit-learn, pandas, requests, pytest, psycopg2-binary

# La app corre contra PostgreSQL (modo SaaS). En Windows: doble click a iniciar_postgres.bat
DATABASE_URL=postgresql://app_palta:CLAVE@localhost:5432/palta python run.py   # → http://127.0.0.1:5000
                                       # el esquema PostgreSQL lo crean los scripts sql/ (no create_all)

python -m pytest                       # toda la suite (51 tests; usan SQLite temporal por test, no tocan PostgreSQL)
python -m pytest tests/test_aislamiento.py   # tests de aislamiento multi-tenant (RLS)
python -m pytest -q                    # resumen breve

python scripts/ml/entrenar.py          # reentrena el RF → app/ml/modelo.pkl + modelo_meta.json
python scripts/analisis/validar_flujo.py   # valida F1→F5 de punta a punta con números reales
python scripts/migracion/migrar_datos.py   # migra SQLite (instance/palta.db) → PostgreSQL
python scripts/migracion/verificar_rls.py  # comprueba el aislamiento entre tenants
```

No hay linter/formatter configurado. La API REST vive bajo `/api` (ver `app/api/__init__.py`).
Migración y arranque PostgreSQL detallados en `docs/MIGRACION_POSTGRES.md`.

## Arquitectura

**Capas (regla estricta):** `app/api/` (HTTP/JSON, un Blueprint por módulo) → `app/services/`
(lógica) → `app/models.py` (datos, SQLAlchemy). Los servicios no conocen Flask; las rutas no
tienen lógica de negocio. Validaciones centralizadas en `app/services/validacion.py`
(lanzan `ValueError` → la ruta los convierte en HTTP 400).

**Jerarquía de dominio:** `Finca` (chacra/propiedad — antes `Campo`) → `Lote` (parcela física
**permanente**, unidad de predicción) → `Campaña` → `RegistroAgronomico`. Un productor tiene
normalmente UNA finca.
⚠️ La columna `Finca` del **dataset** (ej. `F09A`) corresponde a nuestro **`Lote`**, no a `Finca`.

**Lotes por campaña (tabla puente `LoteCampana`):** el `Lote` es físico y cuelga de la finca,
pero **qué lotes se trabajan es por campaña**. La participación vive en `LoteCampana(lote_id,
campana_id, en_produccion)` con `UNIQUE(lote_id, campana_id)`. Por eso la UI lista los lotes de
**una campaña** (`GET /campanas/<id>/lotes`), no todos los de la finca: un lote agregado en 24-25
NO aparece en 25-26 salvo que se asocie. Conserva la identidad del lote entre campañas (la
comparación histórica Predicción↔Cosecha del *mismo* lote sigue intacta). Endpoints:
`POST/DELETE /campanas/<id>/lotes/<loteId>` (asociar/desasociar — al desasociar se borran los
datos de ese lote *en esa campaña*); `POST /fincas/<id>/lotes` crea el lote y lo asocia a la
campaña de trabajo (`campana_id`); `POST /campanas` acepta `copiar_lotes_de` (carry-over del set
de lotes). El resto de datos por campaña (registro, predicción, cosecha, plan, inventario,
alertas, clima) **ya** llevaban `campana_id`. Migración del esquema existente:
`scripts/migrar_lote_campana.py` (crea la tabla y backfillea desde los registros existentes).

**El flujo en cascada es el corazón operativo:**
```
Predicción ML (por lote) → Plan de Cosecha (curva semanal) → tn_planificada por semana
   ├─▶ M6 Mano de obra   (jornales, cuadrillas, déficit)
   ├─▶ M7 Logística       (materiales por semana, déficit)     →  déficits → Alertas (F6)
   └─▶ M8 Transporte      (viajes, camiones, costo, déficit)
Reprogramar una semana → recalcula los tres módulos automáticamente.
```
La cascada se dispara con `recalcular_derivados(plan)` (en `services/derivados.py`), invocado por
`reprogramar_semana()` en `services/planificacion.py` mediante **import local** (evita el ciclo
planificacion↔derivados). Las fórmulas de F4/F5 están documentadas en `docs/DICCIONARIO_DATOS.md` §9.

**Motor climático (`services/clima/`):** para un lote+campaña deriva las **12 variables climáticas**
desde una API meteorológica (Open-Meteo, con NASA POWER de *fallback*) y las escribe en el
`RegistroAgronomico`, respetando *overrides* manuales y dejando log en `ClimaSync`. Las otras 3
features (riego, 2 edades) son **manuales**. Total: 15 features de entrada al modelo.
⚠️ **Campaña futura:** las APIs son de **archivo histórico** → no tienen datos de fechas futuras
(devuelven 400). Si `campana.fecha_inicio > hoy`, `sincronizar_clima` no llama a la API: registra
`status="error"` con un mensaje claro ("la campaña es futura, ingresa el clima manualmente") y la
ruta responde **502** (intencional). Para *predecir* una campaña futura, el clima se ingresa a mano
(o, a futuro, por climatología/año típico). El 502 con datos pasados sí indica un fallo real de API.

**Predicción (`services/prediccion.py` + `ml/predictor.py`):** carga `modelo.pkl` +
`modelo_meta.json`. Devuelve `tn_ha`, `tn_total` (= tn_ha × area_ha), confianza (dispersión entre
árboles del RF) y **bandera OOD** (variables fuera del rango de entrenamiento).

## Reglas del dominio que NO se deben romper

- **Fuga de datos:** `frutos_arbol` y `peso_fruto` (corr. ~0.88 con el rendimiento) **NUNCA** entran
  como features — solo se conocen tras cosechar. Viven en `ResultadoCosecha`, no en el modelo.
- **Domain shift de dos sitios:** el modelo se **entrena con Nepeña** (costa húmeda, dataset) pero se
  **despliega en La Joya, Arequipa** (desierto de altura, clima opuesto). Por eso el modelo extrapola
  → bandera OOD y modelo como soporte. El clima no transfiere (GroupKFold R² negativo); lo que sí
  transfiere es la columna vertebral edad/riego. La validación con cosecha real de La Joya es F7.
- **Pipeline consistente:** train e inferencia comparten la MISMA función de derivación de features
  (`services/clima/derivar.py`). Por eso el reentrenamiento (`scripts/ml/entrenar.py`) deriva el clima
  de Nepeña vía API, no de las columnas viejas del CSV.

## Front-end (HassPlan)

SPA React servida **sin build**: `app/frontend/` (HassPlan.html + React UMD + Babel-in-browser);
`app/frontend_bp.py` la sirve en `/`. **No se reescriben los 10 módulos JSX del prototipo** — solo
cambia la capa de datos.

- **`api.js`** reemplaza los datos simulados de `data.js`: hace `fetch` a `/api`, transforma a la forma
  `window.HP` (mapeo snake→camel, ej. `hfrio_19`→`hFrio19`) y expone **`window.HP.api`** (post/put +
  `crearLote`, `crearCampana`, `guardarVariable`, `asegurarFinca`, `refrescar`). `app.jsx` espera `window.HP_READY`.
- **Lectura vs escritura:** los módulos LEEN de `window.HP`; los formularios GUARDAN vía
  `window.HP.api.X()` → `refrescar()` → toast + navigate. Patrón a repetir en cada formulario nuevo.
- **Mapa:** `mapa.jsx` (`LeafletMap`) — satélite Esri + dibujo Geoman (polígono área-auto **o** punto=centroide)
  + buscador Nominatim. Modo display dibuja los lotes desde su `geometria`. Selección de lote vía
  `window.HP.selectedLoteId` (la fija la lista de Lotes; la leen SectorDetail/SectorVars).

**Trampas verificadas (clase de bug a vigilar al cablear más módulos):**
- Los módulos **desestructuran `window.HP` al cargar** → NO reasignar arrays (`window.HP.X = nuevo`); hay
  que **mutar in-place** (`fill()` en api.js) o muestran datos simulados.
- **Ids/tipos cambiados** rompen lookups del prototipo: `SOURCES.find(id==='nasa-power')` (real `nasa_power`)
  y `s.id.toLowerCase()` (id ahora numérico) **crasheaban la vista entera → pantalla en blanco**. Usar
  fallbacks / `String()` y guards `if(!s) return <empty>`.
- **Scroll:** `.main` y `.content` necesitan `min-height:0` (patrón flex/grid) o no scrollean.

**Verificación sin Playwright/Node:** `chrome --headless=new --virtual-time-budget=12000 --screenshot=...`
(ejecuta Babel+React+fetch). Para una vista interna, cambiar temporalmente la ruta inicial en `app.jsx`
(`useState('dashboard')`→`'sector_new'`) y revertir. **Un screenshot NO prueba scroll** — inyectar
auto-scroll y comprobar que aparece el contenido de abajo. El server (`python run.py`) se cae al editar
archivos (reloader de Flask); relanzar.

## Parámetros operativos de referencia (La Joya)

Al configurar/demostrar los módulos de planificación usa **valores reales de La Joya**, no
inventados (detalle y fuentes en `docs/REFERENCIA_LA_JOYA.md`):

- **Plan de cosecha:** campaña **feb–jul**, `semanas_total` **≈ 16–20** (la cosecha dura 3–5 meses).
  Con pocas semanas (8) la curva campana concentra el pico y dispara los requerimientos a cifras irreales.
- **M6:** `rendimiento_jornal` **≈ 0.10 t/jornal·día** (≈100 kg/día — el parámetro más sensible),
  `tam_cuadrilla` **6**, `dias_cosecha_semana` **6**.
- **M7:** jaba `consumo_por_tn` **≈ 45** (canasta 20–25 kg), pallet **≈ 1**.
- **M8:** `cap_camion_tn` **3.5** (camiones 3–4 t, **no** 10), `viajes_por_camion_semana` **≈ 12**.
- **Rendimiento esperado:** La Joya **14–24 t/ha**. El modelo predice ~20 t/ha → marca **OOD** por el
  clima pero el rendimiento es **plausible** (transfiere edad/riego, no el clima).

## Proceso por fases

El avance se rige por el esquema **F0.5–F7** — única fuente de verdad: **`docs/ARQUITECTURA.md` §13**
(el `ROADMAP.md` conserva el histórico). Regla: no se avanza de fase sin pasar su *gate* (validaciones,
integridad referencial en cascada, casos borde, pytest verde); un commit por fase cerrada.

- **Hecho:** F0.5 (geo) · F1 (predicción+OOD) · F2 (CRUD) · F4 (cosecha) · F5 (derivados+cascada) ·
  F6 (alertas+dashboard) · **FRONT** (HassPlan, los 10 módulos con datos reales + login/admin) ·
  **SaaS** (PostgreSQL multi-tenant con RLS — ver `docs/MIGRACION_POSTGRES.md` y `ARQUITECTURA.md` §14).
- **Siguiente y último:** **F7** — cargar la **cosecha real de La Joya** (`ResultadoCosecha`), comparar
  predicho vs real (`error_vs()`), evaluar reentrenamiento y redactar la documentación final de la tesis.
- **51 tests verdes** (incl. `test_aislamiento.py` para el aislamiento multi-tenant).

## Particularidades del entorno

- **Migraciones de BD:** no hay Alembic. En **PostgreSQL** el esquema lo crean los scripts `sql/`
  (`01_ddl_base` + `02_rls` con FK compuestas y RLS); **no** se usa `create_all` (no sabe de eso).
  Un cambio de esquema = un nuevo `sql/NN_*.sql` con su `ALTER TABLE` (ver `05_*`, `06_*`) aplicado con
  `psql`. En los **tests** (SQLite temporal) `create_all` sí basta. Detalle en `docs/MIGRACION_POSTGRES.md`.
- **Consola Windows (cp1252):** los scripts que imprimen símbolos Unicode (✓, →, ═) deben hacer
  `sys.stdout.reconfigure(encoding="utf-8")` al inicio, o `python` lanza `UnicodeEncodeError`.

## Documentos de referencia

- `docs/ARQUITECTURA.md` — diseño del sistema, capas, flujo en cascada, fases (§13 = fuente de verdad).
- `docs/DICCIONARIO_DATOS.md` — variables (entrada/salida/resultado), validaciones y **fórmulas F4/F5 (§9)**.
- `docs/REFERENCIA_LA_JOYA.md` — **valores reales de La Joya** (rendimiento, temporada, parámetros M6/M7/M8) que anclan la planificación.
- `docs/ROADMAP.md` — fases con sus *gates* (detalle histórico de los tracks A/B).
