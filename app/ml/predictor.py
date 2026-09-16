"""
Wrapper del modelo de Machine Learning (Modulo 4: Inteligencia Agricola).

Carga el Random Forest UNA vez y lo reutiliza. Recibe las 15 variables de un
RegistroAgronomico (en el orden de FEATURES) y devuelve el rendimiento estimado,
la confianza y la bandera de extrapolacion (out-of-distribution).

OOD: el modelo se entreno con datos de Nepena. Si una variable de prediccion cae
fuera del rango visto en entrenamiento (tipico en La Joya: humedad/ETO), se marca
como extrapolacion -> la prediccion es indicativa, no precisa.

INTERVALO CONFORMAL (jul-2026):
  El intervalo p10-p90 entre arboles del bosque medido sobre validacion por campana
  cubria el 41% del valor real cuando prometia el 80%: los percentiles entre arboles
  miden la dispersion del ESTIMADOR de la media, no la distribucion del rendimiento,
  y omiten toda la varianza residual. Se sustituye por PREDICCION CONFORMAL: un
  margen +/-q estimado a partir de los residuos absolutos sobre datos que el modelo
  NO vio (una campana reservada en entrenamiento, o la cosecha real de F7). La
  cobertura pasa a ser la prometida por construccion.

  meta["conformal"] = {"q": Tn/Ha, "cobertura": 0.80, "n": int, "origen": str}
  Sin ese bloque el Predictor cae al intervalo entre arboles y lo marca
  `calibrado: False`, para que la API nunca presente como calibrado lo que no lo esta.
"""
import os
import json
import numpy as np
import pandas as pd
import joblib

from app.models import RegistroAgronomico


class Predictor:
    def __init__(self, model_path):
        self.model_path = model_path
        self.meta_path = os.path.join(os.path.dirname(model_path), "modelo_meta.json")
        self._model = None
        self._meta = None
        self._meta_mtime = None

    @property
    def model(self):
        """Carga perezosa del modelo serializado (modelo.pkl)."""
        if self._model is None:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(
                    f"No se encontro el modelo entrenado en {self.model_path}. "
                    "Genera modelo.pkl con scripts/ml/entrenar.py."
                )
            self._model = joblib.load(self.model_path)
        return self._model

    @property
    def meta(self):
        """Metadata del modelo (features, rangos OOD, margen conformal).

        Se recarga si el archivo cambió en disco: `scripts/ml/calibrar.py` reescribe
        el margen conformal con la cosecha real, y sin esto el proceso servidor
        seguiria usando el margen viejo hasta reiniciarlo. El modelo (.pkl) SI queda
        cacheado: cambiarlo en caliente es otra cosa y exige reinicio.
        """
        try:
            mtime = os.path.getmtime(self.meta_path)
        except OSError:
            return self._meta or {}
        if self._meta is None or mtime != self._meta_mtime:
            with open(self.meta_path, encoding="utf-8") as f:
                self._meta = json.load(f)
            self._meta_mtime = mtime
        return self._meta or {}

    def _detectar_ood(self, valores):
        """
        Lista de variables cuyo valor cae fuera del rango de entrenamiento.
        Cada item: {variable, valor, rango:[min,max], posicion: 'debajo'|'encima'}.
        """
        rangos = self.meta.get("rangos_entrenamiento", {})
        fuera = []
        for feat, val in zip(RegistroAgronomico.FEATURES, valores):
            rango = rangos.get(feat)
            if rango is None or val is None:
                continue
            lo, hi = rango
            if val < lo:
                fuera.append({"variable": feat, "valor": val, "rango": rango, "posicion": "debajo"})
            elif val > hi:
                fuera.append({"variable": feat, "valor": val, "rango": rango, "posicion": "encima"})
        return fuera

    def _dispersion_arboles(self, X):
        """Coeficiente de variacion entre arboles del bosque, en % (0-100).

        Es la metrica de 'confianza' historica del sistema. Se conserva porque mide
        algo real -el desacuerdo interno del bosque- y sirve de comparacion en la
        tesis, pero NO es una probabilidad de acierto: sobre validacion por campana
        su correlacion con el error real es de solo -0.24 (Spearman). La
        incertidumbre que se muestra al usuario sale del intervalo conformal.
        """
        if not hasattr(self.model, "estimators_"):
            return None, None
        Xv = X.to_numpy()
        arboles = np.array([t.predict(Xv)[0] for t in self.model.estimators_])
        media = arboles.mean()
        cv = arboles.std() / media if media else 0.0
        # float() de Python: evita numpy.float64, que psycopg2 no sabe adaptar
        # (rompia el guardado en PostgreSQL) ni jsonify serializar.
        return float(max(0.0, min(100.0, 100 * (1 - cv)))), arboles

    def _intervalo(self, tn_ha, arboles):
        """Intervalo de prediccion. Conformal si hay margen calibrado; si no, el
        rango entre arboles marcado explicitamente como NO calibrado."""
        conf = self.meta.get("conformal") or {}
        q = conf.get("q")
        if q:
            q = float(q)
            return {
                "p10": float(max(0.0, tn_ha - q)),
                "p90": float(tn_ha + q),
                "calibrado": True,
                "cobertura": conf.get("cobertura", 0.80),
                "origen": conf.get("origen", "entrenamiento"),
                "n_calibracion": conf.get("n"),
            }
        if arboles is None:
            return None
        p10, p90 = np.percentile(arboles, [10, 90])
        return {
            "p10": float(p10), "p90": float(p90),
            "calibrado": False,
            "cobertura": None,          # desconocida: NO es el 80% que sugieren p10-p90
            "origen": "dispersion_arboles",
            "n_calibracion": None,
        }

    def predecir(self, registro: RegistroAgronomico, area_ha: float):
        """
        Devuelve un dict:
          tn_ha, tn_total, confianza, intervalo, out_of_distribution[], es_extrapolacion.

        `intervalo` lleva `calibrado`: True solo si sale de la calibracion conformal.

        Lanza ValueError si faltan variables (el RF no acepta nulos).
        """
        valores = registro.to_features()
        faltantes = [f for f, v in zip(RegistroAgronomico.FEATURES, valores) if v is None]
        if faltantes:
            raise ValueError(
                "Faltan variables para predecir: " + ", ".join(faltantes) +
                ". Completa las manuales y sincroniza el clima."
            )

        # DataFrame con los nombres de las features (mismos que en entrenamiento):
        # evita el warning de sklearn y garantiza el orden correcto.
        X = pd.DataFrame([valores], columns=RegistroAgronomico.FEATURES, dtype=float)
        tn_ha = float(self.model.predict(X)[0])
        tn_total = tn_ha * area_ha if area_ha else None

        # Los árboles internos se entrenaron sin nombres de columnas -> pasar numpy.
        dispersion, arboles = self._dispersion_arboles(X)
        intervalo = self._intervalo(tn_ha, arboles)

        # `confianza`: precision del intervalo calibrado relativa a la predicción.
        # Con q=10.8 Tn/Ha sobre una predicción de 20 Tn/Ha da 46%, que es lo que el
        # modelo realmente sabe. Sin calibración se cae a la dispersión entre árboles
        # (la métrica histórica), y el intervalo queda marcado `calibrado: False`.
        if intervalo and intervalo["calibrado"] and tn_ha > 0:
            semiancho = (intervalo["p90"] - intervalo["p10"]) / 2
            confianza = float(max(0.0, min(100.0, 100 * (1 - semiancho / tn_ha))))
        else:
            confianza = dispersion

        ood = self._detectar_ood(valores)
        return {
            "tn_ha": tn_ha,
            "tn_total": float(tn_total) if tn_total is not None else None,
            "confianza": confianza,
            "dispersion_arboles": dispersion,   # métrica histórica, para comparar
            "intervalo": intervalo,
            "out_of_distribution": ood,
            "es_extrapolacion": bool(ood),
        }
