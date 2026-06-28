"""
Modelo de datos del Sistema de Gestion y Planificacion del Cultivo de Palta Hass.

Jerarquia de entidades (lenguaje del agricultor: Finca -> Lote):

  Productor (cliente SaaS / tenant)   <-- NUEVO: raiz del aislamiento multi-tenant
    -> Finca   (chacra / propiedad entera del agricultor, normalmente UNA)
         -> Lote  (parcela dentro de la finca, ~4 por finca; unidad de prediccion)
              -> RegistroAgronomico  [por campana]  -> ENTRADA al modelo (15 features)
              -> Prediccion          [por campana]  -> SALIDA del modelo (Tn/Ha predicho)
              -> ResultadoCosecha    [por campana]  -> REAL (Tn/Ha real + datos de cosecha)

  El modelo ML predice a nivel LOTE: cada fila del dataset = un lote en una campana.

  COMPARACION CENTRAL:  Prediccion.tn_ha_predicho  <->  ResultadoCosecha.tn_ha_real

MULTI-TENANT (SaaS):
  Cada tabla operativa lleva productor_id (via TenantMixin), denormalizado para que
  las politicas RLS de PostgreSQL filtren sin JOINs. productor_id se autocompleta
  desde el contexto del request (app/tenant_ctx.py); en PostgreSQL, RLS ademas lo
  fuerza a nivel de motor. La integridad entre tenants la garantizan las FK
  compuestas (id, productor_id) definidas en sql/01_ddl_base.sql.

IMPORTANTE - Fuga de datos (data leakage):
  'frutos_arbol' y 'peso_fruto' tienen correlacion ~0.84-0.88 con el rendimiento
  porque el rendimiento se calcula a partir de ellos. Solo se conocen DESPUES de
  cosechar, por lo que NO entran al modelo: viven en ResultadoCosecha como dato real.
"""
from datetime import datetime, date, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import declared_attr

from app.tenant_ctx import get_current_tenant

db = SQLAlchemy()

# Politica de borrado en cascada reutilizada en las relaciones padre-hijo
CASCADE = "all, delete-orphan"


def utcnow():
    """UTC actual como datetime naive (reemplaza datetime.utcnow(), deprecado en 3.12).

    Devuelve el MISMO valor que utcnow() (UTC sin tzinfo) para no cambiar el formato
    que SQLite guarda ni mezclar datetimes aware/naive con los registros existentes.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ===========================================================================
#  MULTI-TENANT: tenant (Productor), usuarios y mixin de aislamiento
# ===========================================================================

class TenantMixin:
    """
    Anade productor_id NOT NULL a una tabla operativa.

    El valor se autocompleta desde el contexto del request (get_current_tenant),
    de modo que el codigo existente que crea registros sin pasar productor_id
    sigue funcionando. En PostgreSQL, RLS valida ademas que coincida con el
    tenant de la sesion.
    """
    @declared_attr
    def productor_id(cls):
        return db.Column(
            db.Integer,
            db.ForeignKey("productor.id", ondelete="CASCADE"),
            nullable=False,
            default=get_current_tenant,
            index=True,
        )


class Productor(db.Model):
    """Cliente del SaaS (el 'Productor'). Raiz del aislamiento de datos."""
    __tablename__ = "productor"

    id = db.Column(db.Integer, primary_key=True)
    nombre_comercial = db.Column(db.String(100), nullable=False)
    ruc_dni = db.Column(db.String(20), unique=True)
    correo_contacto = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    fecha_registro = db.Column(db.DateTime, default=utcnow)
    activo = db.Column(db.Boolean, default=True)

    usuarios = db.relationship("Usuario", backref="productor", cascade=CASCADE)
    fincas = db.relationship("Finca", backref="productor", cascade=CASCADE)
    # Las campañas cuelgan de la FINCA (Finca.campanas), no directamente del productor.

    def __repr__(self):
        return f"<Productor {self.nombre_comercial}>"


class Usuario(db.Model):
    """
    Usuario del sistema. productor_id NULL => Superadmin/Proveedor (yo);
    en otro caso pertenece a un productor (CLIENTE_ADMIN / CLIENTE_CAMPO).
    """
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    # NULL = SUPERADMIN. No usa TenantMixin (nullable y semantica distinta).
    productor_id = db.Column(
        db.Integer, db.ForeignKey("productor.id", ondelete="CASCADE")
    )
    nombre_usuario = db.Column(db.String(50), nullable=False, unique=True)
    correo = db.Column(db.String(100), nullable=False, unique=True)
    contrasena_hash = db.Column(db.String(255), nullable=False)
    tipo_usuario = db.Column(db.String(30), nullable=False)  # SUPERADMIN | CLIENTE_ADMIN | CLIENTE_CAMPO
    activo = db.Column(db.Boolean, default=True)

    def es_superadmin(self):
        return self.tipo_usuario == "SUPERADMIN"

    def __repr__(self):
        return f"<Usuario {self.nombre_usuario} ({self.tipo_usuario})>"


# ===========================================================================
#  REGISTRO  (Modulos 2 y 3: Campanas, Fincas y Lotes)
# ===========================================================================

class Campana(db.Model, TenantMixin):
    """Campana agricola (equivale a la columna 'Campana' del dataset, ej. 18-19)."""
    __tablename__ = "campana"

    id = db.Column(db.Integer, primary_key=True)
    # La campaña pertenece a UNA finca; cada finca maneja sus campañas por separado.
    finca_id = db.Column(db.Integer, db.ForeignKey("finca.id"), nullable=False)
    nombre = db.Column(db.String(50), nullable=False)          # ej. "2024-2025"
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(20), default="borrador")      # borrador | activa | cerrada

    # Relaciones
    registros = db.relationship("RegistroAgronomico", backref="campana", cascade=CASCADE)
    predicciones = db.relationship("Prediccion", backref="campana", cascade=CASCADE)
    cosechas = db.relationship("ResultadoCosecha", backref="campana", cascade=CASCADE)
    inventario = db.relationship("Inventario", backref="campana", cascade=CASCADE)
    alertas = db.relationship("Alerta", backref="campana", cascade=CASCADE)
    plan_cosecha = db.relationship("PlanCosecha", backref="campana", uselist=False, cascade=CASCADE)
    # Qué lotes PARTICIPAN en esta campaña (los lotes son físicos/permanentes; su
    # participación es por campaña). Ver LoteCampana.
    lotes_campana = db.relationship("LoteCampana", backref="campana", cascade=CASCADE)

    def __repr__(self):
        return f"<Campana {self.nombre} ({self.estado})>"


class Finca(db.Model, TenantMixin):
    """
    Chacra / propiedad entera del agricultor. Agrupa sus lotes.
    Normalmente hay UNA por agricultor, pero el sistema soporta varias.
    """
    __tablename__ = "finca"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)          # ej. "Chacra La Joya"
    distrito = db.Column(db.String(120))                       # ubicacion textual, ej. "La Joya, Arequipa"
    area_total_ha = db.Column(db.Float)                        # superficie total (suma de lotes)
    # Geometria del contorno de la finca (GeoJSON, opcional) + centroide para centrar el mapa
    geometria = db.Column(db.Text)                             # GeoJSON Polygon del contorno
    centro_lat = db.Column(db.Float)
    centro_lon = db.Column(db.Float)

    lotes = db.relationship("Lote", backref="finca", cascade=CASCADE)
    # Cada finca tiene SUS propias campañas (separadas de las de otras fincas).
    campanas = db.relationship("Campana", backref="finca", cascade=CASCADE)

    def __repr__(self):
        return f"<Finca {self.nombre}>"


class Lote(db.Model, TenantMixin):
    """
    Parcela dentro de una finca. Es la unidad sobre la que el modelo ML predice.
    El agricultor lo dibuja en el mapa (poligono) o lo marca con un punto; de ahi
    se derivan su centroide (para la API de clima) y su area.
    """
    __tablename__ = "lote"

    id = db.Column(db.Integer, primary_key=True)
    finca_id = db.Column(db.Integer, db.ForeignKey("finca.id"), nullable=False)
    nombre = db.Column(db.String(50), nullable=False)          # ej. "Lote 1"
    area_ha = db.Column(db.Float, nullable=False)              # derivada del poligono o manual (si es punto)
    variedad = db.Column(db.String(50), default="Hass")
    ano_plantacion = db.Column(db.Integer)                     # para derivar la edad del cultivo
    densidad_plantas_ha = db.Column(db.Float)                  # marco de plantacion (plantas/Ha); si es NULL la UI usa un default
    en_produccion = db.Column(db.Boolean, default=True)        # produccion vs inactivo
    # Geometria del lote (GeoJSON Polygon dibujado, o Point/centroide).
    geometria = db.Column(db.Text)
    # Centroide (lat/lon): derivado del poligono o el punto. Alimenta la API meteorologica.
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    # Fuente meteorologica preferida para sincronizar las variables climaticas (M10)
    fuente_preferida_id = db.Column(db.Integer, db.ForeignKey("fuente_datos.id"))

    registros = db.relationship("RegistroAgronomico", backref="lote", cascade=CASCADE)
    predicciones = db.relationship("Prediccion", backref="lote", cascade=CASCADE)
    cosechas = db.relationship("ResultadoCosecha", backref="lote", cascade=CASCADE)
    # Campañas en las que participa este lote (asociación por campaña, no físico).
    participaciones = db.relationship("LoteCampana", backref="lote", cascade=CASCADE)

    def __repr__(self):
        return f"<Lote {self.nombre} ({self.area_ha} ha)>"


class LoteCampana(db.Model, TenantMixin):
    """
    Participación de un lote en una campaña (tabla puente Lote<->Campaña).

    El Lote es FÍSICO y permanente (cuelga de la finca); lo que cambia por campaña es
    QUÉ lotes se trabajan. Agregar un lote a la campaña 24-25 crea una fila aquí solo
    para esa campaña: no aparece en 25-26 hasta que se asocie explícitamente. Conserva
    la identidad del lote entre campañas (la comparación histórica Predicción<->Cosecha
    por lote sigue intacta).
    """
    __tablename__ = "lote_campana"
    __table_args__ = (db.UniqueConstraint("lote_id", "campana_id", name="uq_lote_campana"),)

    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lote.id"), nullable=False)
    campana_id = db.Column(db.Integer, db.ForeignKey("campana.id"), nullable=False)
    # Estado productivo del lote EN ESTA campaña (un lote puede estar en producción una
    # campaña e inactivo otra). Default = el del lote físico al asociarlo.
    en_produccion = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<LoteCampana lote={self.lote_id} campana={self.campana_id}>"


# ===========================================================================
#  ENTRADA AL MODELO ML  (Modulo 3: datos productivos/climaticos del lote)
#  -> Estas son las 15 VARIABLES PREDICTORAS que el productor ingresa
#     ANTES de la cosecha. Son la entrada del modelo de Inteligencia Agricola.
# ===========================================================================

class RegistroAgronomico(db.Model, TenantMixin):
    """
    Variables de ENTRADA al modelo ML para un lote en una campana.
    Ordenadas por importancia segun el Random Forest entrenado.
    """
    __tablename__ = "registro_agronomico"

    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lote.id"), nullable=False)
    campana_id = db.Column(db.Integer, db.ForeignKey("campana.id"), nullable=False)

    overrides = db.relationship("VariableOverride", backref="registro", cascade=CASCADE)

    # --- Edad del cultivo (las 2 mas importantes: imp. 0.217 y 0.209) ---
    edad_campo = db.Column(db.Integer)     # Edad Campo  - anos desde plantacion
    edad_prod = db.Column(db.Integer)      # Edad Prod.  - anos en produccion

    # --- Riego (imp. 0.163) ---
    riego_m3ha = db.Column(db.Float)       # M3/Ha Riego - volumen de agua aplicado

    # --- Horas frio (acumulacion de frio, clave en floracion) ---
    hfrio_19 = db.Column(db.Float)         # H.Frio <19 C   (imp. 0.113)
    hfrio_14_19 = db.Column(db.Float)      # H.Frio 14-19 C
    hfrio_14 = db.Column(db.Float)         # H.Frio <14 C
    hfrio_15 = db.Column(db.Float)         # H.Frio <15 C

    # --- Horas de calor acumulado ---
    hac_20_25 = db.Column(db.Float)        # H.Ac. 20-25 C  (imp. 0.063)
    hac_25 = db.Column(db.Float)           # H.Ac. >25 C

    # --- Clima general ---
    humedad = db.Column(db.Float)          # Humedad Prom (%)
    eto = db.Column(db.Float)              # ETO (mm) - evapotranspiracion
    t_min = db.Column(db.Float)            # T_Min (C)
    t_max = db.Column(db.Float)            # T_Max (C)
    t_prom = db.Column(db.Float)           # T_Prom (C)
    lluvia = db.Column(db.Float)           # Lluvia (mm)

    # Orden exacto de features que espera el modelo entrenado (modelo.pkl)
    FEATURES = [
        "edad_campo", "edad_prod", "riego_m3ha",
        "hfrio_19", "hfrio_14_19", "hfrio_14", "hfrio_15",
        "hac_20_25", "hac_25",
        "humedad", "eto", "t_min", "t_max", "t_prom", "lluvia",
    ]

    # Origen de cada feature: manual (la ingresa el productor) vs api (la calcula
    # el motor climatico desde una fuente meteorologica). Suma = las 15 features.
    MANUAL_FEATURES = ["edad_campo", "edad_prod", "riego_m3ha"]
    CLIMATE_FEATURES = [
        "hfrio_19", "hfrio_15", "hfrio_14", "hfrio_14_19",
        "hac_20_25", "hac_25",
        "t_prom", "t_min", "t_max", "humedad", "lluvia", "eto",
    ]

    def to_features(self):
        """Devuelve las 15 variables en el orden que espera el modelo ML."""
        return [getattr(self, f) for f in self.FEATURES]

    def __repr__(self):
        return f"<RegistroAgronomico lote={self.lote_id} campana={self.campana_id}>"


# ===========================================================================
#  SALIDA DEL MODELO ML  (Modulo 4: Inteligencia Agricola)
# ===========================================================================

class Prediccion(db.Model, TenantMixin):
    """Resultado que genera el modelo ML a partir de un RegistroAgronomico."""
    __tablename__ = "prediccion"

    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lote.id"), nullable=False)
    campana_id = db.Column(db.Integer, db.ForeignKey("campana.id"), nullable=False)

    tn_ha_predicho = db.Column(db.Float, nullable=False)   # rendimiento estimado por hectarea
    tn_total_predicho = db.Column(db.Float)                # tn_ha_predicho * area_ha del lote
    nivel_confianza = db.Column(db.Float)                  # dispersion entre arboles del RF (%)
    intervalo_p10 = db.Column(db.Float)                    # rendimiento plausible bajo (Tn/Ha, percentil 10 del bosque)
    intervalo_p90 = db.Column(db.Float)                    # rendimiento plausible alto (Tn/Ha, percentil 90 del bosque)
    fecha = db.Column(db.DateTime, default=utcnow)

    def __repr__(self):
        return f"<Prediccion lote={self.lote_id} {self.tn_ha_predicho:.2f} Tn/Ha>"


# ===========================================================================
#  RESULTADO REAL  (dato de cosecha -> lo que se COMPARA con la prediccion)
#  -> Aqui viven 'frutos_arbol' y 'peso_fruto': son RESULTADO, no entrada.
# ===========================================================================

class ResultadoCosecha(db.Model, TenantMixin):
    """
    Rendimiento real obtenido tras la cosecha. Se compara contra Prediccion
    y sirve de historico para reentrenar el modelo.
    """
    __tablename__ = "resultado_cosecha"

    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lote.id"), nullable=False)
    campana_id = db.Column(db.Integer, db.ForeignKey("campana.id"), nullable=False)

    tn_ha_real = db.Column(db.Float, nullable=False)   # Tn/Ha REAL (target del dataset)
    # Datos de cosecha (NO entran al modelo - se conocen recien al cosechar):
    frutos_arbol = db.Column(db.Float)                 # Frutos/Arbol
    peso_fruto = db.Column(db.Float)                   # Peso Fruto (g)
    fecha_cierre = db.Column(db.Date)

    def error_vs(self, prediccion):
        """Error absoluto en Tn/Ha entre el valor real y una prediccion dada."""
        if prediccion is None:
            return None
        return abs(self.tn_ha_real - prediccion.tn_ha_predicho)

    def __repr__(self):
        return f"<ResultadoCosecha lote={self.lote_id} {self.tn_ha_real:.2f} Tn/Ha>"


# ===========================================================================
#  PLANIFICACION  (Modulos 5-8: derivan de la prediccion confirmada)
# ===========================================================================

class PlanCosecha(db.Model, TenantMixin):
    """Modulo 5: distribuye la produccion estimada en semanas de cosecha."""
    __tablename__ = "plan_cosecha"

    id = db.Column(db.Integer, primary_key=True)
    campana_id = db.Column(db.Integer, db.ForeignKey("campana.id"), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    semanas_total = db.Column(db.Integer, nullable=False)
    tn_total = db.Column(db.Float)                         # suma de produccion estimada
    curva = db.Column(db.String(20), nullable=False, default="campana")   # forma del reparto semanal

    semanas = db.relationship("SemanaCosecha", backref="plan", cascade=CASCADE)
    plan_mano_obra = db.relationship("PlanManoObra", backref="plan_cosecha", uselist=False, cascade=CASCADE)
    plan_transporte = db.relationship("PlanTransporte", backref="plan_cosecha", uselist=False, cascade=CASCADE)


class SemanaCosecha(db.Model, TenantMixin):
    """Una semana dentro del plan de cosecha. Es la unidad que consumen M6, M7 y M8."""
    __tablename__ = "semana_cosecha"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plan_cosecha.id"), nullable=False)
    numero_semana = db.Column(db.Integer, nullable=False)
    fecha_inicio = db.Column(db.Date)
    fecha_fin = db.Column(db.Date)
    tn_planificada = db.Column(db.Float, nullable=False)
    porcentaje = db.Column(db.Float)                       # % del total de la campana
    tn_real = db.Column(db.Float)                          # cosecha real registrada (F7); None = aun sin registrar

    mano_obra = db.relationship("ManoObraSemanal", backref="semana", cascade=CASCADE)
    despachos = db.relationship("DespachoSemanal", backref="semana", cascade=CASCADE)


class PlanManoObra(db.Model, TenantMixin):
    """Modulo 6: parametros para calcular personal requerido."""
    __tablename__ = "plan_mano_obra"

    id = db.Column(db.Integer, primary_key=True)
    plan_cosecha_id = db.Column(db.Integer, db.ForeignKey("plan_cosecha.id"), nullable=False)
    rendimiento_jornal = db.Column(db.Float, nullable=False)   # Tn que cosecha 1 jornal/dia
    tam_cuadrilla = db.Column(db.Integer, nullable=False)      # trabajadores por cuadrilla
    cuadrillas_disponibles = db.Column(db.Integer, default=0)
    dias_cosecha_semana = db.Column(db.Integer, default=6)     # dias laborables por semana (lun-sab)

    requerimientos = db.relationship("ManoObraSemanal", backref="plan", cascade=CASCADE)


class ManoObraSemanal(db.Model, TenantMixin):
    """Personal requerido por semana (calculado desde tn_planificada)."""
    __tablename__ = "mano_obra_semanal"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plan_mano_obra.id"), nullable=False)
    semana_id = db.Column(db.Integer, db.ForeignKey("semana_cosecha.id"), nullable=False)
    jornales_req = db.Column(db.Float)
    cuadrillas_req = db.Column(db.Integer)
    deficit = db.Column(db.Integer, default=0)             # cuadrillas faltantes (>0 = alerta)


class Inventario(db.Model, TenantMixin):
    """Modulo 7: stock disponible de materiales (jabas, pallets, herramientas, EPP)."""
    __tablename__ = "inventario"

    id = db.Column(db.Integer, primary_key=True)
    campana_id = db.Column(db.Integer, db.ForeignKey("campana.id"), nullable=False)
    material = db.Column(db.String(50), nullable=False)    # jaba | pallet | herramienta | epp
    cantidad_disponible = db.Column(db.Float, default=0)
    unidad = db.Column(db.String(20))
    consumo_por_tn = db.Column(db.Float)                  # cuantas unidades se gastan por Tn


class LogisticaSemanal(db.Model, TenantMixin):
    """Requerimiento de materiales por semana (calculado desde la cosecha planificada)."""
    __tablename__ = "logistica_semanal"

    id = db.Column(db.Integer, primary_key=True)
    semana_id = db.Column(db.Integer, db.ForeignKey("semana_cosecha.id"), nullable=False)
    material = db.Column(db.String(50), nullable=False)
    cantidad_requerida = db.Column(db.Float)
    deficit = db.Column(db.Float, default=0)              # requerido - disponible (>0 = alerta)


class PlanTransporte(db.Model, TenantMixin):
    """Modulo 8: parametros para calcular camiones, viajes y costos."""
    __tablename__ = "plan_transporte"

    id = db.Column(db.Integer, primary_key=True)
    plan_cosecha_id = db.Column(db.Integer, db.ForeignKey("plan_cosecha.id"), nullable=False)
    cap_camion_tn = db.Column(db.Float, nullable=False)   # capacidad por camion en Tn
    # En PostgreSQL la columna es NUMERIC(12,2) (ver sql/01_ddl_base.sql); se mapea
    # como Float para que la API/JSON la traten como número (no Decimal->string).
    costo_por_viaje = db.Column(db.Float, nullable=False)
    camiones_disponibles = db.Column(db.Integer, default=0)        # flota disponible
    viajes_por_camion_semana = db.Column(db.Integer, default=6)    # viajes que hace 1 camion/semana

    despachos = db.relationship("DespachoSemanal", backref="plan", cascade=CASCADE)


class DespachoSemanal(db.Model, TenantMixin):
    """Despacho de produccion por semana (camiones/viajes/costo)."""
    __tablename__ = "despacho_semanal"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plan_transporte.id"), nullable=False)
    semana_id = db.Column(db.Integer, db.ForeignKey("semana_cosecha.id"), nullable=False)
    tn_despachadas = db.Column(db.Float)
    camiones = db.Column(db.Integer)               # camiones requeridos esa semana
    viajes = db.Column(db.Integer)
    costo = db.Column(db.Float)            # NUMERIC(12,2) en PostgreSQL (ver DDL); Float en el ORM
    deficit = db.Column(db.Integer, default=0)     # camiones faltantes (>0 = alerta)


# ===========================================================================
#  MONITOREO  (Modulo 9: Sistema de Alertas)
# ===========================================================================

class Alerta(db.Model, TenantMixin):
    """Notificacion generada automaticamente por los modulos de planificacion."""
    __tablename__ = "alerta"

    id = db.Column(db.Integer, primary_key=True)
    campana_id = db.Column(db.Integer, db.ForeignKey("campana.id"), nullable=False)
    # Semana del plan a la que apunta el déficit (nullable: algunas alertas no son semanales).
    semana_id = db.Column(db.Integer, db.ForeignKey("semana_cosecha.id"))
    tipo = db.Column(db.String(50))            # deficit_personal | deficit_material | deficit_transporte
    mensaje = db.Column(db.String(255), nullable=False)
    modulo_origen = db.Column(db.String(50))   # cosecha | mano_obra | logistica | transporte
    severidad = db.Column(db.String(20), default="media")   # baja | media | alta
    fecha_creacion = db.Column(db.DateTime, default=utcnow)
    estado = db.Column(db.String(20), default="activa")     # activa | resuelta

    def __repr__(self):
        return f"<Alerta {self.tipo} ({self.severidad})>"


# ===========================================================================
#  FUENTES DE DATOS Y SINCRONIZACION CLIMATICA  (Modulo 10)
#  -> Soporta las variables climaticas AUTOMATICAS (por API) del modelo.
#  -> fuente_datos es CATALOGO COMPARTIDO: NO lleva productor_id (sin RLS).
# ===========================================================================

class FuenteDatos(db.Model):
    """Proveedor meteorologico que alimenta las variables climaticas (M10)."""
    __tablename__ = "fuente_datos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(60), nullable=False)       # ej. "NASA POWER"
    tipo = db.Column(db.String(30), nullable=False)         # open_meteo | nasa_power | agera5 | davis | manual
    endpoint = db.Column(db.String(200))                    # URL base de la API
    resolucion = db.Column(db.String(60))                   # ej. "horario · 0.1°"
    activa = db.Column(db.Boolean, default=True)

    lotes = db.relationship("Lote", backref="fuente_preferida")
    sincronizaciones = db.relationship("ClimaSync", backref="fuente", cascade=CASCADE)

    def __repr__(self):
        return f"<FuenteDatos {self.nombre} ({self.tipo})>"


class ClimaSync(db.Model, TenantMixin):
    """
    Registro de una sincronizacion climatica para un lote en una campana.
    Sirve tambien como 'Log de sincronizacion' del M10. Un fetch llena las 12
    variables climaticas del RegistroAgronomico -> un timestamp por sync.
    """
    __tablename__ = "clima_sync"

    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lote.id"), nullable=False)
    campana_id = db.Column(db.Integer, db.ForeignKey("campana.id"), nullable=False)
    fuente_id = db.Column(db.Integer, db.ForeignKey("fuente_datos.id"))

    ventana_inicio = db.Column(db.Date)                     # inicio de la ventana consultada
    ventana_fin = db.Column(db.Date)                        # fin de la ventana consultada
    fetched_at = db.Column(db.DateTime, default=utcnow)
    status = db.Column(db.String(20), default="ok")         # ok | error | stale
    mensaje = db.Column(db.Text)                            # detalle (errores, fallback, etc.) - texto libre, puede ser largo

    def __repr__(self):
        return f"<ClimaSync lote={self.lote_id} {self.status} @ {self.fetched_at}>"


class VariableOverride(db.Model, TenantMixin):
    """
    Override manual de una celda climatica: el usuario corrige un valor que vino
    de la API. Queda marcada para que el siguiente sync no la sobrescriba.
    """
    __tablename__ = "variable_override"

    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey("registro_agronomico.id"), nullable=False)
    var_key = db.Column(db.String(30), nullable=False)      # ej. "hfrio_19"
    valor = db.Column(db.Float)
    motivo = db.Column(db.String(255))
    fecha = db.Column(db.DateTime, default=utcnow)

    def __repr__(self):
        return f"<VariableOverride {self.var_key}={self.valor}>"
