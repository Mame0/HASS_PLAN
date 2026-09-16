# Roadmap de Implementación
### Sistema de Gestión y Planificación del Cultivo de Palta Hass

**Stack:** Flask + SQLAlchemy + SQLite · API REST + React (HassPlan) + Leaflet · scikit-learn
**Referencia de diseño (UI/estructura):** Sismagro v5.1.0 (jerarquía **Finca → Lote**, panel de control, módulos laterales)

**Regla del proceso:** no se avanza a la siguiente fase hasta que la actual **pase su gate de verificación**.

---

> ## 📌 Esquema de fases vigente (única fuente de verdad: `ARQUITECTURA.md` §13)
> Históricamente este roadmap usó dos pistas (Track A *Fase 0–7* y Track B *B0–B6*). Ahora
> el avance se rige por el esquema **F0.5–F7** de `ARQUITECTURA.md`. Equivalencias y estado:
>
> | Vigente | Equivale a | Estado |
> |---|---|---|
> | Cimientos + motor clima | Track A Fase 0 · Track B B0–B3 | ✅ |
> | **F1** Predicción + OOD | Track A Fase 1+3 · Track B B4 | ✅ |
> | **F0.5** Finca/Lote + geo | (nuevo) | ✅ |
> | **F2** CRUD + validaciones | Track A Fase 2 | ✅ backend |
> | **F4** Planificación de cosecha | Track A Fase 4 | ✅ backend |
> | **F5** Derivados + cascada | Track A Fase 5 · B5 | ✅ backend |
> | **F6** Alertas + dashboard | Track A Fase 6 | ✅ backend |
> | **F3 / FRONT** Integrar front + mapa | Track B B6 | ✅ **hecho** (los 10 módulos con datos reales + login/admin) |
> | **SaaS** Multi-tenant PostgreSQL + RLS | (nuevo) | ✅ **hecho** (`ARQUITECTURA.md` §14, `MIGRACION_POSTGRES.md`) |
> | **F7** Cierre + recalibración | Track A Fase 7 | 🔲 **siguiente y último** |
> | **Z** Zonas agroclimáticas (experimental) | propuesta del asesor | 🟢 **Z0 cerrado** (16-sep-2026) — siguiente **Z1** |
>
> **Estado al 29-jun-2026:** **51 tests verdes.** Solo queda **F7** (cosecha real de La Joya → recalibrar + doc final).
> Las secciones "Fase N" y "Track B" de abajo se conservan como **detalle histórico**.

---

## 🧪 Track Z — Zonas agroclimáticas en Arequipa *(experimental, sep-2026)*

**Premisa del asesor:** agrupar los polígonos de lotes en **geocercas por zona** y entrenar con el
clima histórico de cada zona para predecir mejor que el modelo de Nepeña. Se contrasta como dos hipótesis, con criterios fijados **antes** de ver resultados:

- **H1 (clima):** las zonas difieren más de lo que varía cada una entre años.
- **H2 (predicción):** un modelo agrupado de Arequipa supera a la media de la zona y a la persistencia
  (año anterior) en validación dejando un año fuera y en split temporal.

**Variable objetivo:** rendimiento de palto **por distrito MIDAGRI** (no hay cosecha real en la BD).
**Zonas (decisión 10-sep-2026): una por serie MIDAGRI, con geocerca dibujada a mano** (criterio del asesor):
- **La Joya** = valle antiguo + irrigaciones (donde están los lotes).
- **Majes** = El Pedregal + pampa irrigada (la ciudad está dentro de la pampa).

**Procedimiento Z0 → Z1:**
1. **Dibujo.** El usuario delimita cada zona en `scripts/zonas/geocercas.html`, cubriendo todo el
   bloque agrícola (una parte por área separada por desierto) → `datos/zonas/geocercas.geojson`.
2. **Validación.** `scripts/zonas/validar_geocercas.py` revisa:
   - la estructura y el catálogo de zonas;
   - que los contornos no se crucen;
   - que las zonas no se solapen;
   - que cubran las **referencias de cultivo** (`datos/zonas/referencias_cultivo.geojson`: puntos
     ubicados por el usuario y revisados sobre satélite).
3. **Muestreo climático.** El mismo script corta la geocerca con la rejilla de 0.1° de ERA5-Land (una
   serie de clima por celda). Cada celda cubierta en ≥ 100 ha aporta un punto **dentro de la geocerca**
   y su altitud → `datos/zonas/muestreo_clima.json` (`--guardar`). El punto se elige, en este orden:
   **`referencia`** (punto de cultivo verificado por el usuario en esa celda), **`centroide`** del área
   cubierta, o **`interior`** si ese centroide cae fuera de la geocerca. Importa porque Open-Meteo
   corrige la temperatura por la altitud del punto pedido (~0.65 °C por cada 100 m).
4. **Cierre de Z0.** Revisión visual de geocercas y puntos sobre satélite.

> **Limitación declarada (decisión 16-sep-2026).** Las geocercas dibujadas abarcan también pampa sin
> cultivo, así que el **peso** de cada celda (hectáreas cubiertas) no equivale a superficie cultivada:
> el promedio climático de la zona está sesgado hacia el terreno que domina la geocerca. Se prefirió
> conservar el dibujo del asesor y corregir solo la **ubicación** de los puntos con las referencias
> verificadas. Las celdas sin referencia mantienen el punto calculado, que puede caer en pampa
> (hoy: `la_joya -16.5_-71.9`, `majes -16.4_-72.1` y `majes -16.3_-72.1`). Hay que decirlo en la tesis
> al describir el clima zonal, y se corrige añadiendo referencias o ciñendo la geocerca.

**Alcance:** scripts fuera de la app; **sin cambios de BD ni de la app** salvo que H2 se cumpla (Z4).

| Fase | Contenido | Estado |
|---|---|---|
| **Z0** Geocercas | `app/services/geo/zonas.py` + `tests/test_geo_zonas.py` + `scripts/zonas/geocercas.html` + `scripts/zonas/validar_geocercas.py` | ✅ **hecho** (16-sep-2026): geocercas dibujadas (La Joya 20 630 ha · Majes 30 195 ha), validadas y `muestreo_clima.json` con 13 cuadrantes |
| **Z1** Clima + separabilidad (H1) | una serie por celda cubierta, pedida en su punto de `muestreo_clima.json` · Open-Meteo `models=era5_land` fijo · `derivar_features` de producción · clima de zona = promedio ponderado por área cubierta | 🔲 |
| **Z2** Objetivo MIDAGRI | CSV por distrito (La Joya, Majes) · validación · controles (expansión de superficie, vecería). ⚠️ El compendio público de MIDAGRI trae palta **solo por región**; la serie distrital hay que pedirla (GRA Arequipa / MIDAGRI) | 🔲 |
| **Z3** Experimento (H2) | líneas base B0/B1 · Ridge/RF · LOYO + temporal + dejando zona fuera | 🔲 |
| **Z4** Integración | tabla `zona` (catálogo sin RLS) · `lote.zona_id` · modelo por zona con fallback | ⏸ solo si H2 se cumple |

**Gate Z0 — CUMPLIDO (16-sep-2026):** 86 tests verdes ✅ · `validar_geocercas.py` sin errores ni avisos ✅ ·
geocercas y los 13 puntos de clima revisados sobre satélite ✅ (6 puntos vienen de referencias verificadas;
3 caen en pampa — ver la limitación declarada arriba).

---

## Buenas prácticas transversales (aplican en TODAS las fases)

| Práctica | Cómo se verifica |
|---|---|
| Separación de capas | `routes/` (HTTP) → `services/` (lógica) → `models.py` (datos) |
| Validación de entrada | Ningún formulario guarda sin validar tipos, rangos y obligatorios (ver `DICCIONARIO_DATOS.md` §3) |
| Integridad referencial | FK + borrado en cascada probados (borrar Finca borra sus Lotes) |
| Casos borde | Nulos, división por cero, listas vacías manejados explícitamente |
| Pruebas | Cada fase agrega `pytest` que pasa antes de avanzar |
| Control de versiones | Un commit por fase cerrada |
| Sin fuga de datos (ML) | `frutos_arbol` / `peso_fruto` nunca entran como feature |

---

## ✅ Fase 0 — Cimientos *(COMPLETADA)*

Estructura Flask, base de datos (18 tablas), jerarquía Finca→Lote, wrapper del predictor.

**Gate cumplido:**
- [x] BD se crea con 18 tablas
- [x] Jerarquía `Finca → Lote` con FK verificada
- [x] 15 features en orden correcto (`to_features()`)
- [x] Variables separadas: entrada / salida / resultado (ver `DICCIONARIO_DATOS.md`)

---

## ✅ Fase 1 — Modelo ML productivo *(= F1, COMPLETADA)*

Reentrenado sobre el **pipeline de la API** (`scripts/ml/entrenar.py`) y exportado a `modelo.pkl` + `modelo_meta.json`.

**Gate cumplido:**
- [x] R²/MAE/RMSE documentados (`random_state=42`): R² 0.57 split · −0.88 GroupKFold · MAE 5.01
- [x] `modelo.pkl` carga y predice desde `predictor.py` (con bandera OOD)
- [x] 0 variables de cosecha entre las features (anti-fuga: frutos/peso excluidos)
- [x] Rangos de entrenamiento guardados para la bandera de extrapolación

---

## 🟡 Fase 2 — Registro base: Fincas y Lotes *(Módulos 2 y 3)* — BACKEND HECHO

> Terminología acordada: **Finca** (chacra, la propiedad — antes `Campo`) → **Lote** (parcela).
> Base F0.5 hecha: renombre `Campo`→`Finca`, geometría GeoJSON + centroide/área (`services/geo/`).

CRUD REST de Campañas, **Fincas** y **Lotes** (`api/campanas.py`, `fincas.py`, `lotes.py`) + validaciones (`services/validacion.py`). El agricultor manda un polígono/punto GeoJSON y el backend deriva centroide+área. El **mapa Leaflet (UI)** se monta en F3. Ver `ARQUITECTURA.md`.

**Gate de salida:**
- [x] Una Finca agrupa varios Lotes; el lote se crea desde geometría (polígono→área/centroide, punto→área manual)
- [x] Lote con estado `en_producción` / inactivo
- [x] Solo una campaña `activa` a la vez (`POST /campanas/<id>/activar` cierra las demás)
- [x] Validaciones aplicadas (área > 0, edades ≥ 0, fechas válidas, nombre obligatorio)
- [x] Borrado en cascada verificado · 9 tests CRUD pasan
- [ ] Mapa satelital con dibujo (Leaflet) → **F3**

---

## ✅ Fase 3 — Inteligencia Agrícola *(Módulo 4)* — HECHO (backend F1 + front)

Conectar predictor → BD. Predicción por lote y total de campaña. Backend = F1; el front
(`Intelligence` → `HP.api.predecirLote`) la ejecuta y muestra con datos reales.

**Gate de salida:**
- [x] Predicción se guarda en `prediccion` y se relee
- [x] Maneja lotes con datos faltantes sin romper (solo predecibles con variables completas)
- [x] `tn_total = tn_ha × area_ha` verificado
- [x] Nivel de confianza mostrado y coherente (dispersión entre árboles del RF)

---

## ✅ Fase 4 — Planificación de Cosecha *(Módulo 5)* — HECHO (backend + front)

Distribución semanal de la producción estimada. Front `Harvest` → `HP.api.reprogramarSemana`.

**Gate de salida:**
- [x] Σ(tn semanas) = tn_total predicho (sin descuadre)
- [x] Σ(porcentajes) = 100%
- [x] Reprogramación manual recalcula bien (propaga a M6/M7/M8)

---

## ✅ Fase 5 — Módulos derivados *(Módulos 6, 7, 8)* — BACKEND HECHO

Mano de Obra, Logística y Transporte — todos consumen las semanas de cosecha
(`services/derivados.py`, `api/derivados.py`). Decisiones de fórmula (jun-2026):
mano de obra con `dias_cosecha_semana`; transporte con flota (`camiones_disponibles`,
`viajes_por_camion_semana`); inventario por **pico semanal vs stock**.

```
M6  jornales_req   = tn_semana / rendimiento_jornal
    cuadrillas_req = ceil(jornales_req / (tam_cuadrilla · dias_cosecha_semana))
M7  requerido      = tn_semana · consumo_por_tn           (déficit = req − stock)
M8  viajes         = ceil(tn_semana / cap_camion_tn)
    camiones_req   = ceil(viajes / viajes_por_camion_semana);  costo = viajes · costo_por_viaje
```

**Gate de salida:**
- [x] Fórmulas validadas: jornales, cuadrillas, camiones, viajes, costos
- [x] Déficits detectados (disponible vs requerido) en los 3 módulos
- [x] Cambiar el plan de cosecha (reprogramar semana) propaga a los 3 módulos (`recalcular_derivados`)
- [x] 8 tests F5 pasan · 34 tests verdes en total

---

## ✅ Fase 6 — Alertas + Dashboard *(Módulos 9 y 1)* — BACKEND HECHO

Alertas de déficit **por semana** (decisión jun-2026) generadas **bajo demanda**
(`services/alertas.py`, endpoint `POST /campanas/<id>/alertas/generar`) + panel de control
consolidado (`services/dashboard.py`, `GET /campanas/<id>/dashboard`). Severidad por magnitud
relativa del déficit (baja ≤15 % · media ≤40 % · alta). Generar es idempotente.

**Gate de salida:**
- [x] Cada déficit genera su alerta (personal/material/transporte), ligada a su semana
- [x] Dashboard integra KPIs reales de todos los módulos (predicción, cosecha, M6/M7/M8)
- [x] Badge de alertas activas correcto (conteo por severidad)
- [x] 6 tests F6 pasan · 40 tests verdes en total

---

## 🔲 Fase 7 — Validación del ciclo + cierre

Cargar `resultado_cosecha` real, comparar predicho vs real, evaluar reentrenamiento.

**Gate de salida:**
- [ ] Comparativo predicho vs real funcional (`error_vs()`)
- [ ] Pruebas integrales del flujo completo
- [ ] Documentación final para la tesis

---

**Orden de dependencias:** `1 → 2 → 3 → 4 → 5 → 6 → 7` (cada fase necesita datos de la anterior).

---

## Track B — Backend para el front HassPlan (variables manual/API + M10)

Dimensión nueva sobre los 9 módulos: el prototipo **HassPlan** separa las variables del
modelo en **5 manuales** (las ingresa el productor) y **12 climáticas automáticas por API**
(NASA POWER / Open-Meteo), más el módulo **M10 Fuentes de datos**. Plan completo en
`C:\Users\garay\.claude\plans\estamos-viendo-la-planificacion-fancy-hopper.md`.

| Fase | Qué | Estado |
|---|---|---|
| **B0** Andamiaje | `services/`, `api/`, factory, `/api/health` | ✅ hecho |
| **B1** BD fuentes/sync | `FuenteDatos`, `ClimaSync`, `VariableOverride`, `Lote.fuente_preferida_id`, seed 5 fuentes | ✅ hecho |
| **B2** ⭐ Motor climático | `services/clima/` (Open-Meteo + NASA POWER fallback → 12 features) | ✅ hecho y verificado contra API real |
| **B3** API variables/clima | `GET/PUT variables`, `POST clima/sync`, `GET fuentes`, `GET clima/log` | ✅ hecho |
| **B4** Servicio ML | `prediccion.py` + endpoint + bandera OOD | ✅ hecho (= Fase F1) |
| **B5** Flujos en cascada | predicción→cosecha→(mano obra/logística/transporte) + alertas | ✅ cascada (F5) + alertas/dashboard (F6) |
| **B6** Integrar front | servido por Flask; `data.js`→`api.js` (`window.HP` por `fetch`) + escritura `window.HP.api`; mapa Leaflet/Esri/Geoman+buscador | ✅ **hecho** (los 10 módulos con datos reales: Predicción, Cosecha, M6/M7/M8, Alertas, Fuentes + login/admin) |
| **SaaS** Multi-tenant | PostgreSQL + RLS (`productor_id`, FK compuestas, login/admin) | ✅ **hecho** — ver `MIGRACION_POSTGRES.md` y `ARQUITECTURA.md` §14 |

**Documentos de referencia:**
- `DICCIONARIO_DATOS.md` — planteamiento de variables (entrada / salida / resultado, validaciones)
- `app/models.py` — esquema de la base de datos (18 tablas)
- `app/services/clima/` — motor de variables climáticas por API (núcleo del Track B)
