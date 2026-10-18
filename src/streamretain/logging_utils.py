"""Registro (log) de ejecución en JSON Lines: cada evento lleva marca de tiempo ISO 8601,
identificador de ejecución, tipo de evento y semana simulada."""

from __future__ import annotations

import datetime as dt
import gzip
import json
from pathlib import Path

import numpy as np


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


class RegistroEjecucion:
    """`detalle=True` guarda percepciones y decisiones por usuario; si es False solo guarda
    resúmenes y todos los eventos de falla (rechazos, errores de API, reintentos, cola)."""

    def __init__(self, ruta: Path | None = None, run_id: str = "local", detalle: bool = True,
                 en_memoria: bool = True, contexto: dict | None = None):
        self.run_id = run_id
        self.detalle = detalle
        self.en_memoria = en_memoria
        self.contexto = contexto or {}
        self.eventos: list[dict] = []
        self._f = None
        if ruta is not None:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            self._f = gzip.open(ruta, "at", encoding="utf-8") if str(ruta).endswith(".gz") \
                else open(ruta, "a", encoding="utf-8")

    def evento(self, tipo: str, semana: int | None = None, **datos) -> dict:
        e = {"ts": dt.datetime.now().isoformat(timespec="milliseconds"), "run_id": self.run_id,
             **self.contexto, "tipo": tipo, "semana": semana, **datos}
        if self.en_memoria:
            self.eventos.append(e)
        if self._f is not None:
            self._f.write(json.dumps(e, ensure_ascii=False, default=_json_default) + "\n")
        return e

    def cerrar(self) -> None:
        if self._f is not None:
            self._f.close()
            self._f = None

    def jsonl(self) -> str:
        return "\n".join(json.dumps(e, ensure_ascii=False, default=_json_default) for e in self.eventos)
