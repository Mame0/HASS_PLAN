# Arquitectura Base del Proyecto
### Sistema de Gestión y Planificación Operativa del Cultivo de Palta Hass

Documento fundacional. Define terminología, modelo de dominio, capas, stack y el orden
de avance por módulos. Se actualiza cuando cambia una decisión estructural.

---

## 1. Visión y alcance

App web para **un agricultor** que gestiona **su finca** de palta Hass. El sistema:
trae el **clima automáticamente** por API, **predice el rendimiento** (módulo de soporte
con ML), y a partir de la predicción **planifica** cosecha, mano de obra, logística y
transporte, con **alertas** y un **dashboard**. Cierra el ciclo cargando la **cosecha real**
para recalibrar el modelo.

> El ML es **apoyo, no oráculo**: entrega una línea base por edad/riego + señal climática,
> con **bandera de extrapolación (OOD)** cuando los datos salen del rango entrenado.

---

## 2. Terminología (acordada)

| Término | Qué es | En el código |
|---|---|---|
| **Productor** (tenant) | El **cliente** del SaaS: dueño de sus datos, aislado del resto por RLS. | `Productor` |
| **Usuario** | Cuenta de login. Pertenece a un productor (`CLIENTE_ADMIN`) o al proveedor (`SUPERADMIN`, sin productor). | `Usuario` |
| **Finca** (chacra) | La propiedad entera del agricultor. Normalmente **una**. | `Finca` (antes `Campo`) |
| **Lote** (parcela) | Subdivisión **física y permanente** de la finca (~4 por finca). **Unidad de predicción y planificación**. | `Lote` |
| **Campaña** | Ciclo productivo, de mitad a mitad de año (ej. "24-25"). Una **activa** a la vez. | `Campana` |
| **Participación Lote↔Campaña** | Qué lotes se trabajan **en cada campaña** (puente). Un lote agregado en 24-25 NO aparece en 25-26 salvo que se asocie. | `LoteCampana` |
| **Registro Agronómico** | Datos de un lote en una campaña (3 manuales + 12 clima). | `RegistroAgronomico` |

Jerarquía: **Finca → Lote → (vía `LoteCampana`, por Campaña) Registro → Predicción → Planes**.
El sistema soporta varias fincas, pero la UX está pensada para una.

> **Lote físico vs. participación por campaña.** El `Lote` es tierra permanente (cuelga de la
> finca, conserva su identidad entre campañas → la comparación histórica Predicción↔Cosecha del
> *mismo* lote queda intacta). Lo que cambia por campaña es **qué lotes participan**, modelado en
> la tabla puente `LoteCampana`. Por eso la UI siempre lista los lotes **de una campaña**
> (`GET /campanas/<id>/lotes`), no todos los de la finca. Todos los demás datos por campaña
> (registro, predicción, cosecha, plan, inventario, alertas, clima) ya llevaban `campana_id`.

---

## 3. Modelo de dominio

```
Finca 1───* Lote 1───* RegistroAgronomico *───1 Campana
  │            │ │              │                  │
  │geometria   │ └─*LoteCampana*┘ (puente: qué lotes participan en la campaña)
  │(GeoJSON)   │geometria       └─ 3 manuales + 12 clima  → Prediccion ─┐
  └ centroide  │(GeoJSON)                                               │
              ├ centroide (→ API clima)              ResultadoCosecha (real)
              ├ area_ha (← del polígono)
              └ fuente_preferida → FuenteDatos ──* ClimaSync (log)
                                                  VariableOverride (correcciones)

Prediccion ─┬─ PlanCosecha ─* SemanaCosecha ─┬─ PlanManoObra ─* ManoObraSemanal
            │                                ├─ Logistica/Inventario ─* LogisticaSemanal
            │                                └─ PlanTransporte ─* DespachoSemanal
            └─ Alerta (déficits, clima, OOD, API caída)
```

**Campos clave nuevos / revisados**
- **Finca**: `id, nombre, distrito, geometria` (GeoJSON contorno, opcional), `centro_lat, centro_lon`.
- **Lote**: `id, finca_id, nombre, variedad, ano_plantacion, en_produccion,`
  `geometria` (GeoJSON **Polygon** o **Point**), `latitud, longitud` (centroide, derivado),
  `area_ha` (derivada del polígono o manual si es punto), `fuente_preferida_id`.
- **LoteCampana** (puente): `id, lote_id, campana_id, en_produccion` con `UNIQUE(lote_id, campana_id)`.
  Marca la participación de un lote en una campaña; `en_produccion` es **por campaña** (un lote
  puede producir una campaña e inactivo otra). Cascada desde `Lote` y `Campana`.
- **Productor / Usuario** (multi-tenant): `Productor` es el tenant; `Usuario` la cuenta de login.
  Todas las tablas operativas llevan `productor_id` denormalizado (Opción A: RLS sin JOINs).
  El catálogo compartido `FuenteDatos` **no** lleva `productor_id` (ver §14).
- **Total: 21 tablas** (las 19 de dominio + `Productor` + `Usuario`).

---

## 4. Capas (separación estricta)

```
Presentación   HassPlan (React UMD) + Leaflet (mapa satelital + dibujo de lotes) + login/admin
     │ fetch JSON  (sesión Flask)
API REST       Flask Blueprints  →  /api/...   (auth, admin, fundo + módulos de dominio)
     │ before_request fija el tenant (app/tenant.py)
Servicios      clima/      motor de variables climáticas (API → 12 features)
               geo/        GeoJSON → centroide + área (Python puro)
               prediccion  carga modelo.pkl + bandera OOD
               planificacion  cascada cosecha → mano obra/logística/transporte
               alertas     generación automática
               fundo       resumen consolidado del fundo
     │
Datos          SQLAlchemy + PostgreSQL   (RLS por tenant; GeoJSON como TEXT)
               └ tenant.py: SELECT set_config('app.tenant', …, is_local=true) por transacción
```

Regla: `api/` (HTTP) → `services/` (lógica) → `models.py` (datos). Nada de lógica en las rutas.
El aislamiento entre tenants NO depende de la app: lo fuerza PostgreSQL con RLS (§14).

---

## 5. Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Flask + Flask-SQLAlchemy |
| BD (runtime) | **PostgreSQL ≥ 15** — multi-tenant con **Row Level Security** (ver §14). GeoJSON como TEXT |
| BD (tests) | SQLite temporal por test (aislado; RLS es no-op) — también es la **fuente** de la migración |
| Auth/SaaS | Login por sesión Flask (werkzeug hash) + aislamiento por tenant forzado en BD (RLS) |
| ML | scikit-learn (Random Forest) + joblib |
| Clima | Open-Meteo Archive (primaria) · NASA POWER (respaldo) |
| Front | HassPlan (React 18 UMD + Babel) — paleta cálida, 10 módulos + login/admin |
| Mapa | **Leaflet** + **Esri World Imagery** (satélite, sin key) + **Leaflet-Geoman** (dibujo) |
| Geo | **Python puro** (centroide + área desde el polígono; sin shapely/PostGIS) |

> **Cambio estructural (jun-2026):** la BD de runtime pasó de SQLite a **PostgreSQL
> multi-tenant (SaaS)**. SQLite queda solo para los tests y como origen de la migración.
> El esquema en PostgreSQL lo crean los scripts `sql/` (FK compuestas + RLS), **no**
> `create_all`. Detalle en §14 y en `MIGRACION_POSTGRES.md`.

---

## 5.1 Estructura de carpetas

```
sistema_palta/
├── app/                      # aplicación Flask (todo el código de producción)
│   ├── __init__.py           #   factory: create_app() (cablea tenant + RLS)
│   ├── models.py             #   modelo de datos (21 tablas; TenantMixin → productor_id)
│   ├── tenant.py             #   sesión multi-tenant: set_config('app.tenant', …) por transacción
│   ├── tenant_ctx.py         #   contexto de tenant del request (productor_id, is_superadmin)
│   ├── seed.py               #   datos semilla (fuentes de datos)
│   ├── api/                  #   capa HTTP — Blueprints REST (/api/...)
│   │   ├── _common.py        #     helpers + VAR_META compartidos
│   │   ├── auth.py · admin.py #     login/logout/me · gestión de productores y usuarios (SUPERADMIN)
│   │   ├── health.py · fuentes.py · campanas.py · fincas.py · lotes.py
│   │   ├── variables.py · clima.py · prediccion.py · cosecha.py
│   │   └── derivados.py · alertas.py · fundo.py
│   ├── services/             #   capa de lógica de negocio (sin HTTP)
│   │   ├── clima/            #     motor climático (open_meteo, nasa_power, derivar, sync)
│   │   ├── geo/              #     GeoJSON → centroide + área (calculo.py)
│   │   └── prediccion.py · planificacion.py · derivados.py · alertas.py · dashboard.py · fundo.py
│   ├── ml/                   #   modelo entrenado + wrapper
│   │   ├── predictor.py · modelo.pkl · modelo_meta.json
│   └── frontend/             #   front HassPlan servido por Flask (FRONT)
│       └── *.jsx / api.js     #     shell, módulos a/b/c, mapa, auth, admin, fincas
├── tests/                    # pruebas pytest (BD temporal aislada) — 47 verdes
│   ├── conftest.py           #   fixtures (app + BD por test)
│   ├── test_geo.py · test_models.py · test_aislamiento.py (RLS) · …
├── scripts/                  # utilidades fuera del runtime (no se importan en la app)
│   ├── ml/entrenar.py        #   reentrena el RF sobre el pipeline de la API
│   ├── analisis/             #   validación del motor (Nepeña, comparación de sitios)
│   └── migracion/            #   migrar_datos.py · verificar_rls.py (SQLite → PostgreSQL)
├── sql/                      # esquema PostgreSQL: 01_ddl_base · 02_rls · 04..06 (ALTERs)
├── docs/                     # documentación de tesis
│   ├── ARQUITECTURA.md · ROADMAP.md · DICCIONARIO_DATOS.md · MIGRACION_POSTGRES.md · REFERENCIA_LA_JOYA.md
├── instance/                 # SQLite local (palta.db) — solo fuente de migración / no se versiona
├── iniciar_postgres.bat      # arranca la app contra PostgreSQL (modo SaaS)
├── config.py · run.py · requirements.txt · .gitignore
```

**Reglas de ubicación:**
- **Código de producción** → `app/`. Nunca scripts sueltos en la raíz.
- **Pruebas** → `tests/`, una por módulo (`test_<modulo>.py`), corren con `pytest` desde la raíz.
- **Scripts one-off** (entrenamiento, validación, análisis) → `scripts/`; pueden importar `app`, pero la app **nunca** importa de `scripts/`.
- **Componentes del front** → `app/frontend/` (servido por Flask, sin build).
- **Esquema PostgreSQL** → `sql/` (DDL + RLS); **migración** → `scripts/migracion/`.
- **Documentación** → `docs/`.

---

## 6. Módulo de Mapa (georreferenciación de lotes)

**Objetivo:** el agricultor abre el mapa de su finca, ve el **satélite**, y **separa sus lotes**
dibujándolos o marcándolos.

**Flujo:**
1. Mapa Leaflet centrado en la finca, capa satelital Esri.
2. El agricultor **dibuja el contorno** de un lote (polígono) con Geoman, **o** marca un **punto**.
3. Al guardar:
   - Polígono → backend (`services/geo/`) calcula **centroide** (lat/lon) y **área (ha)**.
   - Punto → se usa como centroide; el área se ingresa a mano.
4. El **centroide** alimenta el motor de clima (sync por API).
5. La geometría se guarda como **GeoJSON** (texto) en `Lote.geometria`.

**Por qué GeoJSON y no PostGIS:** no hacemos consultas espaciales (intersecciones, vecindad),
solo **guardar + dibujar + centroide/área**. GeoJSON como texto + shapely en Python basta y
mantiene SQLite simple. Migrable a PostGIS si algún día se necesitan consultas geográficas.

---

## 7. Variables del modelo (15 features)

Orden del backend (`RegistroAgronomico.FEATURES`):
`edad_campo, edad_prod, riego_m3ha, hfrio_19, hfrio_14_19, hfrio_14, hfrio_15,`
`hac_20_25, hac_25, humedad, eto, t_min, t_max, t_prom, lluvia`

| Tipo | Variables | Origen |
|---|---|---|
| **Manuales (3)** | edad_campo, edad_prod, riego_m3ha | El agricultor |
| **Climáticas (12)** | horas frío/calor, T° prom/min/máx, humedad, lluvia, ETO | **API** (motor) |

- `frutos_arbol` / `peso_fruto`: se **muestran** (muestreo) pero **NO entran al modelo** (anti-fuga, corr. 0.88).
- **Importancia:** edad_prod + edad_campo + riego ≈ **70%** (manuales, transfieren a cualquier sitio).
  El clima pesa ~30% y **no generaliza** a un clima nuevo (ver §11).

---

## 8. Motor climático (resumen)

`services/clima/`: `open_meteo` (primaria, trae ETO FAO-56) → `nasa_power` (respaldo) →
`derivar` (serie horaria → 12 features) → `sync` (orquesta + log + respeta overrides).
**Validado** en Nepeña: temperaturas y horas frío dentro de pocos % del dataset.

---

## 9. Predicción + bandera OOD

`services/prediccion`: carga `modelo.pkl` + `modelo_meta.json` (orden de features + **rangos
de entrenamiento**). Devuelve: `tn_ha`, `tn_total` (= tn_ha × area_ha), **confianza**
(dispersión entre árboles), y **`out_of_distribution`** (variables fuera del rango entrenado).

---

## 10. Flujo en cascada (corazón operativo)

```
Confirmar Predicción → genera Plan de Cosecha (curva semanal)
        → propaga a Mano de Obra (jornales) + Logística (jabas) + Transporte (camiones)
        → cada déficit genera una Alerta
Reprogramar cosecha → recalcula los tres módulos
```

---

## 11. Dos ubicaciones (clave del proyecto)

| Sitio | Rol | Clima |
|---|---|---|
| **Nepeña, Áncash** (Fundo Los Paltos) | **Entrenamiento** (origen del dataset) | Costa húmeda |
| **La Joya, Arequipa** (`H42X+PF3`) | **Despliegue** (donde predice el agricultor) | Desierto de altura, seco |

Son climas **opuestos** → el modelo **extrapola** al predecir en La Joya (humedad/ETO fuera de
rango). Por eso: **bandera OOD** + el modelo como **soporte** + **Fase 7** (cargar cosecha real
de La Joya y recalibrar). El GroupKFold por campaña (R² negativo) confirma que el clima no
transfiere; lo que sí transfiere es la columna vertebral edad/riego.

---

## 12. Buenas prácticas (gate en cada fase)

| Práctica | Verificación |
|---|---|
| Separación de capas | `api/` → `services/` → `models.py` |
| Validación de entrada | tipos, rangos, obligatorios (`DICCIONARIO_DATOS.md`) |
| Integridad referencial | FK + borrado en cascada probados |
| Casos borde | nulos, división por cero, listas vacías |
| Pruebas | `pytest` por fase antes de avanzar |
| Sin fuga de datos | frutos/peso nunca como feature |

---

## 13. Orden de avance por fases

| Fase | Qué | Estado |
|---|---|---|
| **F0.5** Renombre + geo | `Campo`→`Finca`; `geometria`/centroide/área en Finca y Lote; `services/geo/` | ✅ hecho (8 tests) |
| **F1** Servicio de predicción + OOD | `predictor`+`modelo_meta`, `services/prediccion`, `POST/GET /api/lotes/<id>/prediccion`, `GET /api/campanas/<id>/prediccion` | ✅ hecho (4 tests) |
| **F2** Registro base + Mapa | CRUD Campaña/Finca/Lote + validaciones + geo (polígono→área/centroide). Backend ✅ (9 tests). Mapa Leaflet = en F3 | ✅ backend |
| **F4** Planificación de cosecha | curva semanal desde Σ predicciones + reprogramación (`services/planificacion.py`, `api/cosecha.py`) | ✅ backend (4 tests) |
| **F5** Derivados + cascada | mano obra / logística / transporte + propagación (`services/derivados.py`, `api/derivados.py`) | ✅ backend (8 tests) |
| **F6** Alertas + Dashboard | déficits→alertas por semana (bajo demanda) + panel KPIs (`services/alertas.py`, `dashboard.py`, `api/alertas.py`) | ✅ backend (6 tests) |
| **FRONT** Integración HassPlan (10 módulos) | servido por Flask (`app/frontend/`); `data.js`→`api.js` (`window.HP` por `fetch`); escritura vía `window.HP.api`; mapa Leaflet+Esri+Geoman+buscador; "Sectores"→**Lotes**; anti-fuga frutos/peso | ✅ **hecho** (los 10 módulos con datos reales) |
| **SaaS** Multi-tenant PostgreSQL + RLS | migración SQLite→PostgreSQL; `productor_id` + FK compuestas + RLS; login/admin (`auth.py`, `admin.py`, `tenant.py`); ver §14 y `MIGRACION_POSTGRES.md` | ✅ **hecho** (test_aislamiento.py) |
| **F7** Cierre + recalibración | cosecha real de La Joya → reentrenar | 🔲 **siguiente** |

> **Estado (27-jun-2026):** **47 tests verdes.** Backend de dominio (F0.5–F6) + FRONT (10 módulos
> con datos reales) + capa SaaS multi-tenant (PostgreSQL/RLS, login, admin) **completos**.
>
> **FRONT — qué quedó cableado:** Dashboard, Lotes, Campaña, **Predicción IA** (`predecirLote`),
> **Cosecha** (curva semanal + `reprogramarSemana`), **Mano de obra**, **Logística**, **Transporte**,
> **Alertas** y **Fuentes de datos**, más login y panel de admin (SUPERADMIN). Trampas en `CLAUDE.md` (§Front-end).
>
> **Único pendiente — F7 (cierre de tesis):** cargar la **cosecha real de La Joya** en `ResultadoCosecha`,
> comparar predicho vs real (`error_vs()`), evaluar reentrenamiento y redactar la documentación final.

**Hecho previo:** B0-B3 (backend + motor climático + API variables/clima/fuentes) y `modelo.pkl`
reentrenado sobre el pipeline de la API.

**Dependencias:** F0.5 (renombre + geo) y F2 son base. Luego F1 → F2 → F4 → F5 → F6 → FRONT → SaaS → **F7**.

---

## 14. Multi-tenant (SaaS) con Row Level Security

El sistema pasó de app de un solo usuario a **SaaS**: varios productores comparten la misma
base PostgreSQL, **aislados a nivel de motor** (no por la app). Guía operativa completa en
`MIGRACION_POSTGRES.md`.

**Patrón de aislamiento (Opción A — RLS sin JOINs):**
- `productor_id` **denormalizado** en toda tabla operativa (vía `TenantMixin`).
- Integridad entre tenants: FK compuestas `(padre_id, productor_id)` + `UNIQUE(id, productor_id)`
  → un hijo no puede colgar de un padre de otro tenant.
- RLS: `ENABLE` + `FORCE ROW LEVEL SECURITY`; políticas filtran por `current_setting('app.tenant')`.
  El **SUPERADMIN** (proveedor) hace bypass por flag `app.is_superadmin`.
- **Catálogo compartido:** `FuenteDatos` no lleva `productor_id` ni RLS.

**Cómo la app fija el tenant (anti-fuga por pooling):** `app/tenant.py` escucha `after_begin` de
SQLAlchemy y, al abrir cada transacción, ejecuta `set_config('app.tenant', …, is_local=true)`. El
`is_local=true` hace la variable **transaction-local**: se borra al COMMIT/ROLLBACK, así no se
filtra a otro request que reutilice la conexión del pool. En SQLite (tests) es **no-op**.

**Login:** `POST /api/auth/login` resuelve el usuario con una función `SECURITY DEFINER`
(`app_login_lookup()`) antes de conocer el tenant; luego la sesión Flask guarda `productor_id`.
Con `REQUIRE_LOGIN` activo, `/api` exige sesión (salvo `/health` y `/auth/*`). Sin login, la app
opera como tenant por defecto (`DEFAULT_TENANT_ID=1`) para no romper el front actual ni los tests.

**Roles PostgreSQL:** `app_palta` (la app, sujeta a RLS) y `palta_auth` (solo el lookup de login).
El esquema lo crean `sql/01_ddl_base.sql` + `sql/02_rls.sql` (+ ALTERs `04..06`); `create_all` **no**
se usa contra PostgreSQL (no sabe de FK compuestas ni RLS). Verificación: `scripts/migracion/verificar_rls.py`
y `tests/test_aislamiento.py`.
