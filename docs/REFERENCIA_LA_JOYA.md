# Referencia operativa — Palto Hass en La Joya (Arequipa)

Valores típicos del sitio de **despliegue** del sistema (La Joya, Arequipa). Sirven para
**anclar los parámetros** de los módulos de planificación (F4–F5) en cifras reales —no
inventadas— y como rangos de referencia/validación. Fuente: informe de investigación
(deep-research) sobre MINAGRI, AGROIDEAS, gremios y una tesis regional 2023.

> ⚠️ Son valores **orientativos** que el productor ajusta por finca. La calibración fina
> llega con la cosecha real de La Joya en **F7**.

---

## 1. Rendimiento (valida la predicción ML)

| Ámbito | Rendimiento |
|---|---|
| La Joya (típico) | **14–24 t/ha** |
| La Joya tecnificado (Agroideas) | hasta **22 t/ha** (subió desde 5 t/ha) |
| Arequipa (regional) | ~19–20 t/ha |
| Perú (promedio nacional) | ~9–13 t/ha |

> **Cierre importante:** en `validar_flujo.py` el modelo (entrenado en Nepeña) predice
> **~20 t/ha** para La Joya. Aunque el clima cae fuera de rango (bandera **OOD**), el
> rendimiento predicho **es plausible** para La Joya (14–24 t/ha). Es decir: el modelo
> extrapola pero **no delira** — coherente con que lo que transfiere es la columna
> vertebral edad/riego, no el clima. Buen argumento para la tesis.

## 2. Temporada de cosecha (informa F4)

- **Ventana:** **febrero a julio**, pico **mayo–junio** (La Joya aporta ~93 % del palto regional).
- **Duración por huerto:** **3–5 meses**, con **cortes parciales cada 7–15 días** (≈2 cortes/semana).
- **Implicación para el Plan de Cosecha:** una campaña realista en La Joya son **~16–20 semanas**
  empezando en **febrero**, no 8–10. Con más semanas el pico se aplana y los requerimientos
  semanales (jornales, camiones) se vuelven manejables. ➡️ ver §6 (replanteamiento de la curva).

## 3. M6 · Mano de obra

| Parámetro del modelo | Valor real La Joya | Notas |
|---|---|---|
| `rendimiento_jornal` | **0.10 t/jornal·día** (rango 0.05–0.15) | 100–150 kg/día óptimo; 50–80 en terreno difícil |
| `tam_cuadrilla` | **6** (rango 5–8) | 5 recolectores + 1 capataz |
| `dias_cosecha_semana` | **6** (lun–sáb) | jornadas diurnas de 8–10 h |
| (regla de campo) | 1 cuadrilla por **1–3 ha**; ~1 ha en 8–10 días | ~15–30 jornales/ha; ~150–200 jornales para 12 t/ha |
| (costo, futuro) | jornal **S/ 100–120/día** | aún no se costea en M6; útil para F6/costeo |

> Cosecha **manual** (tijeras/pértigas, corte cuidando el pedúnculo), intensiva en mano de obra.

## 4. M7 · Logística / inventario

| Material | `consumo_por_tn` real | Notas |
|---|---|---|
| Jaba / canasta | **~45 und/t** (rango 40–50) | canasta de 20–25 kg → 1 t ≈ 40–50 jabas |
| Pallet | **~1 und/t** | pallet ~1000–1200 kg neto |

> El supuesto del modelo (**pico semanal vs stock**, material reutilizable) es conservador:
> mide la semana de mayor demanda simultánea sin descontar cuántas veces rota la jaba en la semana.

## 5. M8 · Transporte

| Parámetro del modelo | Valor real La Joya | Notas |
|---|---|---|
| `cap_camion_tn` | **3.5 t** (camiones 3–4 t) | carga ligera de fruta fresca |
| `viajes_por_camion_semana` | **~12** (rango 12–18) | 2–3 viajes/día × 6 días |
| `costo_por_viaje` | estimado **S/ ~250** | sin cifra oficial; flete local ~50 km |
| (regla de campo) | ~3 camiones por ha (12 t) ≈ **0.3 camiones/t** | carga/descarga ~15–20 min/t |
| (distancia) | La Joya → packing Arequipa **~50 km, 1–1.5 h** | también Mollendo |

## 6. Defaults recomendados para La Joya (resumen accionable)

```
Plan de cosecha (F4):  fecha_inicio ≈ febrero  ·  semanas_total ≈ 16–20
M6 Mano de obra:       rendimiento_jornal 0.10  ·  tam_cuadrilla 6  ·  dias_cosecha_semana 6
M7 Inventario:         jaba consumo 45/t  ·  pallet consumo 1/t
M8 Transporte:         cap_camion_tn 3.5  ·  viajes_por_camion_semana 12  ·  costo_por_viaje ~250
```

## 7. Observaciones de replanteamiento (antes de F6)

1. **Nº de semanas del plan importa mucho.** Con 8 semanas la curva campana concentra el pico y dispara
   jornales/cuadrillas a cifras irreales; con ~16–20 (la realidad de La Joya) el pico se aplana.
   No requiere cambiar la fórmula, solo usar `semanas_total` realista. *Posible mejora futura:* permitir
   una curva más plana (meseta) además de la campana, ya que la cosecha real es por cortes parciales.
2. **`rendimiento_jornal` es el parámetro más sensible de M6.** Pasar de 0.5 (demo vieja) a 0.10 (real)
   multiplica por ~5 las cuadrillas requeridas. Es el valor que más hay que cuidar al configurar.
3. **`cap_camion_tn` realista es 3–4 t, no 10.** Camiones grandes subestiman viajes/flota.
4. **Costos abiertos:** jornal (S/100–120) y flete (~S/250) habilitan un **costeo** que hoy M6/M8 no hacen
   (M8 ya da `costo` de transporte; M6 no costea personal). Candidato a F6 o a una extensión de F5.

## 8. Riesgos que el sistema podría señalar (futuro)

Plagas (bicho del cesto, cochinillas, *Phytophthora*), heladas/sequía, ventana de madurez
(24–26 % materia seca para Hass), y logística (camiones, carreteras). Hoy fuera de alcance;
relevante para el módulo de alertas (F6) y para interpretar desvíos en F7.
