# Capítulo III — Secciones para completar + Rótulos de Tablas/Figuras

> Material listo para pegar en la tesis (Capítulo III, Elaboración de la propuesta).
> **Parte 1:** texto de las tres secciones vacías. **Parte 2:** numeración de Tablas y Figuras
> para llenar los índices. Cifras tomadas de `app/ml/modelo_meta.json` y
> `docs/DICCIONARIO_DATOS.md §9` (valores reales, no inventados).

---

# PARTE 1 — Textos de las secciones vacías

## A) Requerimientos Funcionales y No Funcionales

El sistema HassPlan se especificó a partir de las necesidades operativas de un productor de palta
Hass y del proveedor del servicio (superadministrador). Los requerimientos funcionales (RF)
describen **qué** debe hacer el sistema, organizados por módulo; los no funcionales (RNF) describen
**con qué cualidades** debe hacerlo. Ambos conjuntos guiaron el diseño de la arquitectura en capas y
del modelo de datos descritos en las secciones siguientes.

**Requerimientos funcionales**

| ID | Módulo | Requerimiento |
|----|--------|---------------|
| RF-01 | Acceso y seguridad | El sistema debe permitir el inicio de sesión con usuario y contraseña, y diferenciar los roles SUPERADMIN, CLIENTE_ADMIN y CLIENTE_CAMPO. |
| RF-02 | Administración | El superadministrador debe poder registrar y gestionar productores (clientes) y sus usuarios. |
| RF-03 | Georreferenciación | El productor debe poder dibujar cada lote sobre un mapa satelital (polígono o punto) y buscar ubicaciones por nombre. |
| RF-04 | Georreferenciación | El sistema debe derivar automáticamente el área (ha) y el centroide (lat/lon) de cada lote a partir de su geometría. |
| RF-05 | Registro | El sistema debe permitir el registro y edición de fincas, campañas y lotes, y asociar qué lotes participan en cada campaña. |
| RF-06 | Registro | El productor debe poder ingresar las variables manuales del lote (riego y las dos edades del cultivo). |
| RF-07 | Clima | El sistema debe sincronizar automáticamente las doce variables climáticas del lote desde una API meteorológica, usando el centroide del lote. |
| RF-08 | Clima | El sistema debe permitir corregir manualmente un valor climático (override) y evitar que la siguiente sincronización lo sobrescriba. |
| RF-09 | Predicción | El sistema debe estimar el rendimiento por hectárea de cada lote y su total, entregando además el nivel de confianza y una bandera de datos fuera de rango (OOD). |
| RF-10 | Cosecha | El sistema debe generar un plan de cosecha que reparta la producción estimada en semanas, y permitir reprogramar una semana. |
| RF-11 | Mano de obra | El sistema debe calcular los jornales y cuadrillas requeridos por semana y el déficit frente a la capacidad disponible. |
| RF-12 | Logística | El sistema debe calcular los materiales requeridos por semana (jabas, pallets, etc.) y el déficit frente al inventario. |
| RF-13 | Transporte | El sistema debe calcular los viajes, camiones y costo por semana y el déficit de flota. |
| RF-14 | Alertas | El sistema debe generar alertas automáticas por cada semana con déficit, clasificadas por severidad. |
| RF-15 | Cascada | Al reprogramar una semana, el sistema debe recalcular automáticamente mano de obra, logística y transporte. |
| RF-16 | Dashboard | El sistema debe mostrar un tablero con los indicadores de la campaña y las alertas activas. |
| RF-17 | Resultado | El sistema debe permitir registrar la cosecha real y compararla contra la predicción. |

**Requerimientos no funcionales**

| ID | Categoría | Requerimiento |
|----|-----------|---------------|
| RNF-01 | Seguridad | El sistema debe aislar los datos de cada productor mediante Row Level Security (RLS) de PostgreSQL, de modo que un cliente nunca acceda a datos de otro. |
| RNF-02 | Seguridad | Las contraseñas deben almacenarse cifradas (hash) y las sesiones firmarse con una clave secreta. |
| RNF-03 | Integridad | La integridad entre clientes debe garantizarse con llaves foráneas compuestas (id, productor_id). |
| RNF-04 | Usabilidad | La interfaz debe estar en español y diseñada para un productor con una finca, sin requerir instalación (aplicación web). |
| RNF-05 | Rendimiento | Una predicción y su cascada de planificación deben resolverse en pocos segundos bajo demanda. |
| RNF-06 | Fiabilidad | Ante fallo de la fuente climática principal (Open-Meteo), el sistema debe recurrir automáticamente a una fuente de respaldo (NASA POWER). |
| RNF-07 | Mantenibilidad | El sistema debe seguir una arquitectura en capas estricta (api → services → models) con validaciones centralizadas, y contar con pruebas automatizadas. |
| RNF-08 | Portabilidad | El frontend debe ejecutarse en cualquier navegador moderno sin proceso de compilación. |
| RNF-09 | Escalabilidad | La base de datos debe ser multi-tenant compartida; el procesamiento asíncrono (broker) queda previsto como trabajo futuro. |
| RNF-10 | Económico | El sistema debe construirse exclusivamente con tecnologías de código abierto, sin licencias propietarias. |

## B) Diseño del componente de Machine Learning

El componente de Machine Learning es el módulo de soporte a la decisión del sistema: su función es
**estimar el rendimiento (Tn/Ha) de cada lote antes de la cosecha**, para que sobre esa estimación
operen los módulos de planificación. Es importante subrayar que el modelo es un **apoyo**, no el
centro del sistema; el foco es la gestión operativa.

**Algoritmo.** Se seleccionó un modelo de **Bosque Aleatorio (Random Forest Regressor)** por su
robustez frente a relaciones no lineales y su capacidad de estimar la incertidumbre a partir de la
dispersión entre árboles. El modelo se configuró de forma **regularizada** para evitar que las
variables climáticas, altamente correlacionadas entre sí, dominaran el ajuste: 300 árboles,
profundidad máxima de 4, `min_samples_leaf` = 1 y `max_features` = 1.0, hiperparámetros ajustados
contra validación cruzada por grupos (GroupKFold).

**Variables de entrada.** El modelo recibe **quince variables (features)**: tres de ellas manuales
—edad del campo, edad de producción y volumen de riego (M³/Ha)— y doce climáticas —horas frío en
distintos umbrales, horas de calor acumulado, humedad, evapotranspiración, temperaturas y lluvia—
derivadas automáticamente desde la API meteorológica. Se excluyeron deliberadamente las variables
`frutos_arbol` y `peso_fruto` (correlación de +0.88 con el rendimiento) para **evitar la fuga de
datos**, ya que solo se conocen después de cosechar; estas se almacenan como resultado real, no como
entrada del modelo.

**Consistencia del pipeline.** El entrenamiento y la inferencia comparten la misma función de
derivación de variables climáticas, de modo que las condiciones en que se entrenó el modelo son
idénticas a las de su uso en producción. El modelo se entrenó con datos del **Fundo Los Paltos
(Nepeña)** —215 registros, ventana julio–junio por campaña— y se serializa junto con sus metadatos
(`modelo.pkl` y `modelo_meta.json`).

**Evaluación.** Sobre una partición aleatoria (train/test) el modelo alcanzó un **R² de 0.612**,
un **MAE de 4.61 Tn/Ha** y un **RMSE de 5.8**, superando al modelo base. Sin embargo, bajo validación
cruzada por grupos (GroupKFold, que separa por campaña) el **R² resultó negativo (−0.597)**, lo que
evidencia con honestidad la dificultad de generalizar el componente climático entre campañas y sitios
distintos. Este resultado sustenta la decisión de tratar el modelo como soporte y de acompañar cada
predicción con una señal de confianza.

**Salidas y control de extrapolación.** Para cada lote el componente entrega: el rendimiento por
hectárea, el rendimiento total (rendimiento × área), un **nivel de confianza** derivado de la
dispersión entre los árboles del bosque (confianza media de 84.4 %), un intervalo plausible (percentiles
10 y 90 del bosque) y una **bandera OOD (Out-Of-Distribution)** que se activa cuando alguna variable
del lote cae fuera del rango observado en el entrenamiento. Esta bandera es clave para el despliegue:
el sistema se entrena con Nepeña (costa húmeda) pero se aplica en **La Joya (desierto de altura)**,
un clima opuesto; por ello el modelo extrapola y marca OOD, aunque el rendimiento estimado (~20 Tn/Ha)
resulta plausible porque lo que transfiere entre sitios es la columna vertebral de edad y riego, no el
clima. La validación con la cosecha real de La Joya constituye la fase final del proyecto.

## C) Diseño del componente de gestión y planificación operativa

El componente de gestión y planificación es el **corazón operativo** del sistema. Toma la predicción
de rendimiento y la transforma, en cascada, en un plan de cosecha semanal y en los requerimientos de
mano de obra, logística y transporte, generando alertas cuando la capacidad disponible no alcanza. La
cadena de cálculo es la siguiente: la suma de las predicciones alimenta el **Plan de Cosecha (F4)**,
que produce la tonelada planificada por semana; cada semana alimenta en paralelo los módulos de
**mano de obra (M6)**, **logística (M7)** y **transporte (M8)**; y los déficits de estos convergen en
el módulo de **alertas (F6)**.

**Plan de cosecha (F4).** La producción total estimada se reparte entre las semanas mediante una
**curva tipo campana**, `wᵢ = sin(π·(i+0.5)/n)` normalizada, que concentra la cosecha hacia el centro
de la temporada. El reparto respeta dos invariantes: la suma de las toneladas planificadas iguala al
total estimado y la suma de los porcentajes es 100 %. Al reprogramar una semana, su valor se fija y el
resto se redistribuye de forma proporcional al peso actual, manteniendo el total.

**Mano de obra (M6).** A partir de la tonelada semanal y del rendimiento de un jornal se calculan los
jornales y cuadrillas requeridos:

```
jornales_req   = tn_semana / rendimiento_jornal
cuadrillas_req = ceil(jornales_req / (tam_cuadrilla · dias_cosecha_semana))
deficit        = max(0, cuadrillas_req − cuadrillas_disponibles)
```

**Logística (M7).** Por cada material se compara la demanda semanal contra el inventario disponible,
tratando el material como reutilizable (el riesgo es la semana de mayor demanda simultánea):

```
requerido_semana = tn_semana · consumo_por_tn
deficit          = max(0, requerido_semana − cantidad_disponible)
```

**Transporte (M8).** Desde la tonelada semanal y la capacidad del camión se calculan viajes, camiones
y costo:

```
viajes       = ceil(tn_semana / cap_camion_tn)
camiones_req = ceil(viajes / viajes_por_camion_semana)
costo        = viajes · costo_por_viaje
deficit      = max(0, camiones_req − camiones_disponibles)
```

**Alertas (F6) y cascada.** Cada módulo expone su déficit por semana; el sistema genera una alerta por
semana con déficit, clasificada por severidad según su magnitud relativa (baja ≤ 15 %, media ≤ 40 %,
alta > 40 %). Como los tres módulos consumen la misma semana de cosecha, **reprogramar una semana
dispara el recálculo automático** de mano de obra, logística y transporte, manteniendo la coherencia
de todo el plan.

Para que los requerimientos sean creíbles, los parámetros se anclan a valores reales del sitio de
despliegue (La Joya), resumidos en la Tabla de valores de referencia.

---

# PARTE 2 — Numeración de Tablas y Figuras (para los índices)

> **Convención sugerida:** numeración global secuencial (Tabla 1, Tabla 2…; Figura 1, Figura 2…),
> en el **orden en que aparecen** en el documento. Si tu norma exige numeración por capítulo, cambia
> a "Tabla 3.1", "Figura 3.1", etc. (el orden es el mismo).
>
> **Recomendación fuerte:** el diccionario de datos son **21 tablas** — considera moverlo a un
> **Anexo A. Diccionario de datos** y dejar en el cuerpo solo el listado de entidades, la cardinalidad
> y el diagrama lógico. Así el cuerpo queda legible y el ÍNDICE DE TABLAS no se infla con 21 entradas.

## ÍNDICE DE TABLAS (Capítulo III, en orden)

| Rótulo | Ubicación (sección) |
|--------|---------------------|
| **Tabla 1.** Matriz del stack tecnológico | Infraestructura tecnológica |
| **Tabla 2.** Requerimientos funcionales del sistema | Requerimientos F. y NF. |
| **Tabla 3.** Requerimientos no funcionales del sistema | Requerimientos F. y NF. |
| **Tabla 4.** Listado de entidades del modelo de datos | Infraestructura de información |
| **Tabla 5.** Cardinalidad de las relaciones | Infraestructura de información |
| **Tabla 6.** Métricas de evaluación del modelo de Machine Learning | Diseño del componente ML |
| **Tabla 7.** Rangos de entrenamiento para la detección OOD | Diseño del componente ML |
| **Tabla 8.** Parámetros y valores de referencia de La Joya | Diseño del componente de gestión |
| **Tabla 9.** Diccionario de datos por entidad *(o Anexo A)* | Infraestructura de información |

> Si mantienes el diccionario tabla por tabla en el cuerpo, serían las Tablas 9 a 29 (una por entidad,
> en el orden: Productor, Usuario, Finca, Campana, Lote, Lote_campana, Registro_agronomico,
> Variable_override, Prediccion, Resultado_cosecha, Plan_cosecha, Semana_cosecha, Plan_mano_obra,
> Mano_obra_semanal, Inventario, Logistica_semanal, Plan_transporte, Despacho_semanal, Alerta,
> Fuente_datos, Clima_sync). **Por eso conviene el Anexo.**

## ÍNDICE DE FIGURAS (Capítulo III, en orden)

| Rótulo | Ubicación (sección) |
|--------|---------------------|
| **Figura 1.** Esquema general de la propuesta | Esquema general de la propuesta |
| **Figura 2.** Matriz del stack tecnológico | Infraestructura tecnológica |
| **Figura 3.** Modelo lógico de datos (entidades y cardinalidad) | Infraestructura de información |
| **Figura 4.** Arquitectura de paquetes y componentes | Arquitectura del sistema |
| **Figura 5.** Esquema funcional del sistema (flujo de procesos) | Arquitectura del sistema |
| **Figura 6.** Flujo de comunicación entre componentes (predecir lote) | Arquitectura del sistema |
| **Figura 7.** Cascada de planificación operativa | Diseño del componente de gestión |

> **Nota:** la "Matriz del stack" puede ir como **Figura 2** (versión visual) **o** como **Tabla 1**
> (versión detallada), no ambas con el mismo contenido. Elige una y ajusta la referencia en el texto
> (hoy dice "Diagrama 3" → cámbialo a "Figura 2" o "Tabla 1" según decidas).

## Correcciones de referencias en el texto ya redactado

En la sección **Arquitectura del sistema** reemplaza los marcadores por el número final:
- "…se resume de forma visual en el Diagrama 3…" → **Figura 2**
- "Diagrama X - Arquitectura de Plataforma de HassPlan" → **Figura 4. Arquitectura de paquetes y componentes**
- "Diagrama 2 del esquema funcional" / "Diagrama X - Esquema Funcional" → **Figura 5. Esquema funcional del sistema**
