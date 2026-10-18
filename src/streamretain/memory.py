"""Memoria del agente en SQLite.

Guarda solo lo que el agente realmente percibió o hizo (nunca historial fabricado):
observaciones válidas, rechazos, predicciones (con sus features), intervenciones,
cola de reintentos y resultados observados a las 4 semanas.
"""

from __future__ import annotations

import json
import sqlite3

import pandas as pd

ESQUEMA = """
CREATE TABLE IF NOT EXISTS observaciones (
    user_id TEXT, semana INTEGER, horas_vistas REAL, dias_desde_ultimo_login REAL,
    tipo_plan TEXT, cambio_metodo_pago INTEGER, PRIMARY KEY (user_id, semana));
CREATE TABLE IF NOT EXISTS rechazos (user_id TEXT, semana INTEGER, motivo TEXT);
CREATE TABLE IF NOT EXISTS predicciones (
    user_id TEXT, semana INTEGER, probabilidad REAL, prediccion INTEGER, prioridad TEXT,
    confianza TEXT, modelo TEXT, features TEXT, PRIMARY KEY (user_id, semana));
CREATE TABLE IF NOT EXISTS intervenciones (
    user_id TEXT, semana INTEGER, estado TEXT, intentos INTEGER, detalle TEXT);
CREATE TABLE IF NOT EXISTS cola (user_id TEXT PRIMARY KEY, semana_origen INTEGER);
CREATE TABLE IF NOT EXISTS resultados (
    user_id TEXT, semana_prediccion INTEGER, cancelo INTEGER, intervenido INTEGER,
    PRIMARY KEY (user_id, semana_prediccion));
CREATE INDEX IF NOT EXISTS ix_obs_semana ON observaciones (semana);
"""


class Memoria:
    def __init__(self, ruta: str = ":memory:"):
        self.con = sqlite3.connect(ruta, check_same_thread=False)
        self.con.executescript(ESQUEMA)

    # ---------------------------------------------------------------- escritura
    def guardar_observaciones(self, df: pd.DataFrame) -> None:
        cols = ["user_id", "semana", "horas_vistas", "dias_desde_ultimo_login",
                "tipo_plan", "cambio_metodo_pago"]
        filas = list(df[cols].itertuples(index=False, name=None))
        self.con.executemany("INSERT OR REPLACE INTO observaciones VALUES (?,?,?,?,?,?)", filas)
        self.con.commit()

    def guardar_rechazos(self, df: pd.DataFrame) -> None:
        if len(df):
            filas = list(df[["user_id", "semana", "motivo"]].astype(object).itertuples(index=False, name=None))
            self.con.executemany("INSERT INTO rechazos VALUES (?,?,?)", filas)
            self.con.commit()

    def guardar_predicciones(self, df: pd.DataFrame, columnas_features: list[str]) -> None:
        feats = df[columnas_features].to_dict(orient="records")
        filas = [(r.user_id, int(r.semana), float(r.probabilidad), int(r.prediccion), r.prioridad,
                  r.confianza, r.modelo, json.dumps(f, allow_nan=True))
                 for r, f in zip(df.itertuples(index=False), feats)]
        self.con.executemany("INSERT OR REPLACE INTO predicciones VALUES (?,?,?,?,?,?,?,?)", filas)
        self.con.commit()

    def guardar_intervencion(self, user_id: str, semana: int, estado: str, intentos: int, detalle: str) -> None:
        self.con.execute("INSERT INTO intervenciones VALUES (?,?,?,?,?)",
                         (user_id, semana, estado, intentos, detalle))
        self.con.commit()

    def encolar(self, user_ids: list[str], semana: int) -> None:
        self.con.executemany("INSERT OR REPLACE INTO cola VALUES (?,?)", [(u, semana) for u in user_ids])
        self.con.commit()

    def desencolar(self, user_ids: list[str]) -> None:
        self.con.executemany("DELETE FROM cola WHERE user_id = ?", [(u,) for u in user_ids])
        self.con.commit()

    def guardar_resultados(self, df: pd.DataFrame) -> None:
        filas = list(df[["user_id", "semana_prediccion", "cancelo", "intervenido"]]
                     .itertuples(index=False, name=None))
        self.con.executemany("INSERT OR REPLACE INTO resultados VALUES (?,?,?,?)",
                             [(u, int(s), int(c), int(i)) for u, s, c, i in filas])
        self.con.commit()

    # ---------------------------------------------------------------- lectura
    def ventana(self, semana: int, semanas: int = 4) -> pd.DataFrame:
        """Observaciones válidas en [semana − semanas + 1, semana]."""
        return pd.read_sql_query(
            "SELECT * FROM observaciones WHERE semana BETWEEN ? AND ?",
            self.con, params=(semana - semanas + 1, semana))

    def semanas_historial(self, semana: int) -> pd.Series:
        """Número de semanas con observación válida por usuario hasta `semana` (incluida)."""
        df = pd.read_sql_query(
            "SELECT user_id, COUNT(*) AS n FROM observaciones WHERE semana <= ? GROUP BY user_id",
            self.con, params=(semana,))
        return df.set_index("user_id")["n"]

    def cola_pendiente(self) -> list[str]:
        return [r[0] for r in self.con.execute("SELECT user_id FROM cola ORDER BY semana_origen")]

    def ofertados_desde(self, semana: int) -> set[str]:
        filas = self.con.execute(
            "SELECT DISTINCT user_id FROM intervenciones WHERE estado = 'activada' AND semana >= ?", (semana,))
        return {r[0] for r in filas}

    def intervenidos_en(self, semana_desde: int, semana_hasta: int) -> set[str]:
        filas = self.con.execute(
            "SELECT DISTINCT user_id FROM intervenciones WHERE estado = 'activada' AND semana BETWEEN ? AND ?",
            (semana_desde, semana_hasta))
        return {r[0] for r in filas}

    def predicciones_semana(self, semana: int) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM predicciones WHERE semana = ?", self.con, params=(semana,))

    def datos_aprendizaje(self) -> pd.DataFrame:
        """Predicciones vinculadas con su resultado observado (para reentrenar)."""
        return pd.read_sql_query(
            """SELECT p.user_id, p.semana, p.features, r.cancelo, r.intervenido
               FROM predicciones p JOIN resultados r
               ON p.user_id = r.user_id AND p.semana = r.semana_prediccion""", self.con)

    def tabla(self, nombre: str) -> pd.DataFrame:
        return pd.read_sql_query(f"SELECT * FROM {nombre}", self.con)
