"""
Wrapper del modelo de Machine Learning (Modulo 4: Inteligencia Agricola).

Carga el Random Forest UNA vez y lo reutiliza. Recibe las 15 variables de un
RegistroAgronomico (en el orden de FEATURES) y devuelve el rendimiento estimado,
la confianza y la bandera de extrapolacion (out-of-distribution).

OOD: el modelo se entreno con datos de Nepena. Si una variable de prediccion cae
fuera del rango visto en entrenamiento (tipico en La Joya: humedad/ETO), se marca
como extrapolacion -> la prediccion es indicativa, no precisa.
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
        """Metadata del modelo (orden de features + rangos de entrenamiento)."""
        if self._meta is None and os.path.exists(self.meta_path):
            with open(self.meta_path, encoding="utf-8") as f:
                self._meta = json.load(f)
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

    def predecir(self, registro: RegistroAgronomico, area_ha: float):
        """
        Devuelve un dict:
          tn_ha, tn_total, confianza, out_of_distribution[], es_extrapolacion.

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

        # Confianza e intervalo a partir de la dispersion entre arboles del bosque.
        confianza = None
        intervalo = None
        if hasattr(self.model, "estimators_"):
            # Los árboles internos se entrenaron sin nombres de columnas -> pasar numpy.
            Xv = X.to_numpy()
            arboles = np.array([t.predict(Xv)[0] for t in self.model.estimators_])
            cv = arboles.std() / arboles.mean() if arboles.mean() else 0
            # float() de Python: evita numpy.float64, que psycopg2 no sabe adaptar
            # (rompía el guardado en PostgreSQL) ni jsonify serializar.
            confianza = float(max(0.0, min(100.0, 100 * (1 - cv))))
            # Intervalo p10-p90: rango plausible del rendimiento segun el bosque.
            # Mas honesto que un solo numero de "confianza" (no asume nada de la forma).
            p10, p90 = np.percentile(arboles, [10, 90])
            intervalo = {"p10": float(p10), "p90": float(p90)}

        ood = self._detectar_ood(valores)
        return {
            "tn_ha": tn_ha,
            "tn_total": float(tn_total) if tn_total is not None else None,
            "confianza": confianza,
            "intervalo": intervalo,
            "out_of_distribution": ood,
            "es_extrapolacion": bool(ood),
        }
