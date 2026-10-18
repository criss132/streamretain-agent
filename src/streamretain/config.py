"""Carga de configuración: escenarios, umbrales y parámetros del agente."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
DIR_CONFIG = RAIZ / "config"


def cargar_yaml(nombre: str) -> dict:
    with (DIR_CONFIG / nombre).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def escenarios() -> dict[str, dict]:
    """Devuelve {id: escenario} con la definición tal como está en escenarios.yaml."""
    cfg = cargar_yaml("escenarios.yaml")
    return {e["id"]: e for e in cfg["escenarios"]}


def parametros_escenario(id_escenario: str) -> dict:
    """Mezcla simulador_base + senal + parámetros propios del escenario.

    Las claves de `deriva` que coinciden con parámetros de señal (p. ej. caida_consumo_media)
    se aplican solo desde la semana de deriva; el simulador se encarga de eso.
    """
    cfg = cargar_yaml("escenarios.yaml")
    params = copy.deepcopy(cfg["simulador_base"])
    params.update(copy.deepcopy(cfg["senal"]))
    esc = {e["id"]: e for e in cfg["escenarios"]}[id_escenario]
    params.update(copy.deepcopy(esc.get("parametros") or {}))
    params["id_escenario"] = id_escenario
    params["tipo_escenario"] = esc["tipo"]
    return params


def umbrales() -> dict:
    return cargar_yaml("umbrales.yaml")


def rango_semillas(tipo: str) -> list[int]:
    a, b = umbrales()["protocolo"]["semillas"][tipo]
    return list(range(a, b + 1))
