# Diccionario de Datos y Planteamiento de Variables
### Sistema de Gestión y Planificación del Cultivo de Palta Hass

Este documento define **qué variables entran al modelo**, **qué se predice** y **qué se compara**.
Es la referencia base antes de desarrollar los módulos. Fundamentado en el análisis del
dataset real (`Dataset_Limpio_ML.csv`: 217 registros, 35 lotes, 7 campañas).

---

## 1. Jerarquía de entidades

```
Finca            chacra / propiedad        ej. "Chacra La Joya"   (en dataset: prefijo F09)
  └── Lote       parcela                   ej. "Lote 1" / F09A    ← unidad que predice el modelo
        └── [por Campaña]  18-19 ... 24-25
              ├── RegistroAgronomico   → ENTRADA   (15 features)
              ├── Predicción           → SALIDA    (Tn/Ha predicho)
              └── ResultadoCosecha     → REAL      (Tn/Ha real + datos de cosecha)
```

> ⚠️ **Colisión de términos a tener clara:** la **columna `Finca` del dataset** (ej. `F09A`)
> corresponde a nuestro **`Lote`** — NO a nuestra entidad `Finca`. Nuestra **`Finca`** (la
> chacra/propiedad, tabla `finca`) se infiere del prefijo del código (`F09` agrupa `F09A/F09J/F09N`).
> En el código la entidad raíz se llama `Finca` (antes `Campo`); el agricultor tiene normalmente
> UNA finca con varios lotes.

---

## 2. Clasificación de las 18 columnas del dataset

| Columna original | Rol en el sistema | ¿Entra al modelo? |
|---|---|---|
| `Finca` | Identidad → **Lote** | No (identificador) |
| `Campaña` | Identidad → **Campaña** | No (identificador) |
| **`Tn/Ha`** | 🔵 **OBJETIVO** (lo que se predice) | No (es el target) |
| `Frutos/Árbol` | 🟠 Resultado de cosecha | ❌ **NO — fuga de datos** |
| `Peso Fruto (g)` | 🟠 Resultado de cosecha | ❌ **NO — fuga de datos** |
| `Edad Campo` | 🟢 Feature | ✅ Sí |
| `Edad Prod.` | 🟢 Feature | ✅ Sí |
| `M3/Ha Riego` | 🟢 Feature | ✅ Sí |
| `H.Frío <19°C` | 🟢 Feature | ✅ Sí |
| `H.Frío <15°C` | 🟢 Feature | ✅ Sí |
| `H.Frío <14°C` | 🟢 Feature | ✅ Sí |
| `H.Frío 14-19°C` | 🟢 Feature | ✅ Sí |
| `H.Ac. 20-25°C` | 🟢 Feature | ✅ Sí |
| `H.Ac. >25°C` | 🟢 Feature | ✅ Sí |
| `Humedad Prom (%)` | 🟢 Feature | ✅ Sí |
| `ETO (mm)` | 🟢 Feature | ✅ Sí |
| `T_Min (°C)` | 🟢 Feature | ✅ Sí |
| `T_Max (°C)` | 🟢 Feature | ✅ Sí |
| `T_Prom (°C)` | 🟢 Feature | ✅ Sí |
| `Lluvia (mm)` | 🟢 Feature | ✅ Sí |

**Resumen:** 15 features de entrada · 1 objetivo · 2 de resultado (no entran) · 2 identificadores.

---

## 3. 🟢 Variables de ENTRADA al modelo (15 features)

Ordenadas por importancia en el Random Forest. `min/max` son del **dataset original (Nepeña)**;
`validación` es el rango aceptado en los formularios.

> ⚠️ **Rangos del OOD ≠ estos rangos.** El modelo se reentrenó sobre el **pipeline de la API**
> (clima derivado de Open-Meteo), así que los rangos **autoritativos** para la bandera de
> extrapolación (out-of-distribution) viven en **`app/ml/modelo_meta.json`** y difieren de los de
> abajo (ej. humedad API 74.8–77.2 vs dataset 81–90; ETO API 1391–1552 vs dataset 260–1294).
> Los de esta tabla son del dataset histórico, útiles como referencia agronómica, no para el OOD.

| # | Campo BD | Columna dataset | Unidad | min – max | Importancia | Validación |
|---|---|---|---|---|---|---|
| 1 | `edad_campo` | Edad Campo | años | -1 – 13 | **0.217** | entero ≥ 0 ⚠️ |
| 2 | `edad_prod` | Edad Prod. | años | -3 – 11 | **0.209** | entero ≥ 0 ⚠️ |
| 3 | `riego_m3ha` | M3/Ha Riego | m³/ha | 10685 – 22022 | **0.163** | > 0 |
| 4 | `hfrio_19` | H.Frío <19°C | horas | 71 – 6016 | **0.113** | ≥ 0 |
| 5 | `hac_20_25` | H.Ac. 20-25°C | horas | 205 – 3820 | 0.063 | ≥ 0 |
| 6 | `humedad` | Humedad Prom | % | 81 – 90.2 | 0.044 | 0 – 100 |
| 7 | `eto` | ETO | mm | 260 – 1294 | 0.043 | ≥ 0 |
| 8 | `hfrio_14_19` | H.Frío 14-19°C | horas | 1659 – 8284 | 0.043 | ≥ 0 |
| 9 | `t_min` | T_Min | °C | 14.4 – 20.8 | 0.033 | -10 – 50 |
| 10 | `lluvia` | Lluvia | mm | 2 – 70 | 0.024 | ≥ 0 |
| 11 | `hfrio_14` | H.Frío <14°C | horas | 39.5 – 1894 | 0.014 | ≥ 0 |
| 12 | `hfrio_15` | H.Frío <15°C | horas | 194 – 2978 | 0.011 | ≥ 0 |
| 13 | `hac_25` | H.Ac. >25°C | horas | 2.5 – 1482 | 0.008 | ≥ 0 |
| 14 | `t_max` | T_Max | °C | 19.9 – 25.9 | 0.007 | -10 – 50 |
| 15 | `t_prom` | T_Prom | °C | 16.1 – 22.7 | 0.007 | -10 – 50 |

**Orden exacto que espera el modelo** (`RegistroAgronomico.FEATURES`):
`edad_campo, edad_prod, riego_m3ha, hfrio_19, hfrio_14_19, hfrio_14, hfrio_15, hac_20_25, hac_25, humedad, eto, t_min, t_max, t_prom, lluvia`

---

## 4. 🔵 Variable OBJETIVO

| Campo BD | Columna dataset | Unidad | min – max | media |
|---|---|---|---|---|
| `tn_ha_predicho` (salida) / `tn_ha_real` (real) | Tn/Ha | Tn/ha | 0.81 – 44.89 | 20.52 |

Producción total del lote = `tn_ha × area_ha`.

---

## 5. 🟠 Variables de RESULTADO — NO entran al modelo (fuga de datos)

| Campo BD | Columna dataset | Correlación con Tn/Ha | Por qué se excluye |
|---|---|---|---|
| `frutos_arbol` | Frutos/Árbol | **+0.839** | Solo se conoce al cosechar |
| `peso_fruto` | Peso Fruto (g) | -0.006 (pero…) | Solo se conoce al cosechar |
| `frutos_arbol × peso_fruto` | — | **+0.881** | Es prácticamente la fórmula del rendimiento |

> **Regla de oro:** el rendimiento ≈ (frutos/árbol × peso × árboles/ha). Usar estas variables
> como entrada sería "hacer trampa": el R² subiría artificialmente pero el sistema sería inútil
> en la práctica, porque al momento de predecir (antes de cosechar) no las tienes.
> Se guardan en `ResultadoCosecha` para: **(a)** comparar predicho vs real, **(b)** histórico, **(c)** reentrenar.

---

## 6. La comparación central del sistema

```
   Predicción.tn_ha_predicho   ⟷   ResultadoCosecha.tn_ha_real
        (módulo ML, ANTES)            (cosecha, DESPUÉS)
                         │
                         ▼
              error = | real − predicho |     → método ResultadoCosecha.error_vs()
```
Esta comparación alimenta la alerta *"Producción inferior a la planificada"* (Módulo 9) y
la validación del modelo (Fase 7).

---

## 7. ⚠️ Observaciones de calidad de datos

| Hallazgo | Detalle | Estado |
|---|---|---|
| **Edades negativas** | `edad_campo` mín = -1, `edad_prod` mín = -3 (finca F46) | ✅ Resuelto: clip a ≥0 en `scripts/ml/entrenar.py` + validación ≥0 en la API |
| **Nulos climáticos** | campaña 18-19 sin clima en el dataset | ✅ N/A: el clima ahora lo deriva la API por campaña (no se usan las columnas viejas) |
| **Nulos productivos** | 0.9% en riego/frutos/peso | Filas sin riego se excluyen del entrenamiento |
| **Separador decimal** | El CSV usa coma decimal y `N/D` para nulos | ✅ Limpieza al cargar |

---

## 8. Mapeo rápido dataset → base de datos

| Dataset | Tabla BD | Campo BD |
|---|---|---|
| Prefijo del código (ej. F09) → la chacra | `finca` | `nombre` |
| Columna `Finca` del dataset (ej. F09A) → la parcela | `lote` | `nombre` |
| Campaña | `campana` | `nombre` |
| 15 variables climáticas/edad | `registro_agronomico` | (ver §3) |
| Tn/Ha (al predecir) | `prediccion` | `tn_ha_predicho` |
| Tn/Ha (real) | `resultado_cosecha` | `tn_ha_real` |
| Frutos/Árbol, Peso Fruto | `resultado_cosecha` | `frutos_arbol`, `peso_fruto` |

---

## 9. ⚙️ Variables y fórmulas de planificación (F4–F5)

Estas variables **no** alimentan al modelo ML: derivan de la **predicción confirmada** y
las ingresa el productor como parámetros operativos. Todas consumen la **semana de cosecha**
(`SemanaCosecha.tn_planificada`) como insumo. Verificadas de punta a punta en
`scripts/analisis/validar_flujo.py`.

### 9.1 Cadena de cálculo (cascada)

```
Σ Predicciones (Tn) ─▶ Plan de Cosecha ─▶ tn_planificada por semana ─┬─▶ M6 Mano de obra
   (F4: curva campana)                                               ├─▶ M7 Logística
   reprogramar 1 semana ─▶ recalcula los tres módulos (cascada)      └─▶ M8 Transporte
```

### 9.2 F4 · Plan de Cosecha (Módulo 5)

| Parámetro | Tipo | Validación | Significado |
|---|---|---|---|
| `fecha_inicio` | fecha | YYYY-MM-DD | arranque de la cosecha |
| `semanas_total` | entero | ≥ 1 | nº de semanas a repartir |

- **Distribución:** curva tipo campana `w_i = sin(π·(i+0.5)/n)` normalizada → más cosecha al centro.
- **Invariante:** `Σ tn_planificada = tn_total` (el residuo de redondeo se absorbe en la semana mayor) y `Σ porcentaje = 100`.
- **Reprogramar** una semana fija su valor y redistribuye el resto **proporcional al peso actual**, manteniendo el total.

### 9.3 F5/M6 · Mano de Obra

| Parámetro | Validación | Default | Significado |
|---|---|---|---|
| `rendimiento_jornal` | > 0 | — | Tn que cosecha 1 jornal en 1 día |
| `tam_cuadrilla` | ≥ 1 | — | personas por cuadrilla |
| `cuadrillas_disponibles` | ≥ 0 | 0 | flota de personal disponible |
| `dias_cosecha_semana` | ≥ 1 | 6 | días laborables por semana (lun–sáb) |

```
jornales_req   = tn_semana / rendimiento_jornal           (jornal-días)
cuadrillas_req = ceil(jornales_req / (tam_cuadrilla · dias_cosecha_semana))
deficit        = max(0, cuadrillas_req − cuadrillas_disponibles)
```
> **Supuesto:** una cuadrilla rinde `tam_cuadrilla · dias_cosecha_semana` jornal-días por semana.
> El déficit solo aparece si la cuadrilla disponible no cubre la semana pico.

### 9.4 F5/M7 · Logística / Inventario

| Parámetro (por material) | Validación | Significado |
|---|---|---|
| `material` | obligatorio | jaba · pallet · herramienta · EPP |
| `cantidad_disponible` | ≥ 0 | stock actual |
| `consumo_por_tn` | ≥ 0 | unidades que se gastan por Tn |

```
requerido_semana = tn_semana · consumo_por_tn
deficit          = max(0, requerido_semana − cantidad_disponible)     (pico semanal vs stock)
```
> **Supuesto (decisión jun-2026):** se compara la demanda de **cada semana** contra el stock,
> tratando el material como **reutilizable** (jabas/EPP que rotan): el riesgo es la semana de
> mayor demanda simultánea, no el acumulado. ⚠️ *Pendiente de calibrar con datos reales:*
> `consumo_por_tn` de la jaba depende de su capacidad (una jaba de ~20 kg ≈ 50/Tn) y de cuántas
> veces rota dentro de la semana.

### 9.5 F5/M8 · Transporte

| Parámetro | Validación | Default | Significado |
|---|---|---|---|
| `cap_camion_tn` | > 0 | — | capacidad por camión (Tn) |
| `costo_por_viaje` | ≥ 0 | — | costo de un viaje |
| `camiones_disponibles` | ≥ 0 | 0 | flota disponible |
| `viajes_por_camion_semana` | ≥ 1 | 6 | viajes que hace 1 camión en la semana |

```
viajes       = ceil(tn_semana / cap_camion_tn)
camiones_req = ceil(viajes / viajes_por_camion_semana)
costo        = viajes · costo_por_viaje
deficit      = max(0, camiones_req − camiones_disponibles)
```
> **Supuesto:** el **costo se cobra por viaje** (no por camión). El `deficit` mide camiones de
> flota faltantes; no bloquea el despacho, genera alerta (F6).

### 9.6 Déficits → Alertas (F6, ✅ hecho)

Cada módulo expone `deficit` por semana y la bandera `tiene_deficit`. La **F6** los convierte
en registros `Alerta` **uno por semana con déficit** (`tipo`: `deficit_personal` /
`deficit_material` / `deficit_transporte`; `modulo_origen`: mano_obra / logistica / transporte;
`semana_id` ligado). Generación **bajo demanda** (`POST /campanas/<id>/alertas/generar`,
idempotente) y **severidad** por magnitud relativa del déficit: **baja ≤15 % · media ≤40 % · alta**.
El **dashboard** (`GET /campanas/<id>/dashboard`) consolida los KPIs de todos los módulos + el
badge de alertas activas por severidad.

### 9.7 Valores de referencia para La Joya (anclan los parámetros)

Valores reales del sitio de despliegue para configurar los módulos con cifras plausibles
(no inventadas). Detalle y fuentes en **`docs/REFERENCIA_LA_JOYA.md`**.

| Parámetro | Ref. La Joya | Origen |
|---|---|---|
| Plan: `semanas_total` | **16–20** (campaña feb–jul) | cosecha real dura 3–5 meses |
| Plan: `fecha_inicio` | **≈ febrero** | pico en mayo–junio |
| M6 `rendimiento_jornal` | **0.10 t/jornal·día** (0.05–0.15) | 100 kg/día (el parámetro más sensible) |
| M6 `tam_cuadrilla` | **6** (5–8) | 5 recolectores + 1 capataz |
| M7 jaba `consumo_por_tn` | **~45/t** (40–50) | canasta de 20–25 kg |
| M7 pallet `consumo_por_tn` | **~1/t** | pallet ~1000 kg |
| M8 `cap_camion_tn` | **3.5** (3–4) | camión ligero de fruta fresca |
| M8 `viajes_por_camion_semana` | **~12** (12–18) | 2–3 viajes/día × 6 días |

> ⚠️ Con `semanas_total` realista (~16) el pico de la curva campana se aplana y los
> requerimientos por semana son creíbles; con 8 semanas se disparan a cifras irreales.
> Verificado en `scripts/analisis/validar_flujo.py` (ya calibrado con estos valores).
