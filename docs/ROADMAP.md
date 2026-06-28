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
>
> **Estado al 27-jun-2026:** **47 tests verdes.** Solo queda **F7** (cosecha real de La Joya → recalibrar + doc final).
> Las secciones "Fase N" y "Track B" de abajo se conservan como **detalle histórico**.

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
