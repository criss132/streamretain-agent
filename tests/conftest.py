import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from streamretain.config import parametros_escenario  # noqa: E402
from streamretain.datos import dataset  # noqa: E402
from streamretain.model import ModeloRiesgo  # noqa: E402


@pytest.fixture(scope="session")
def params_pequenos():
    p = parametros_escenario("N2")
    p.update({"n_usuarios": 300, "ciclos": 5})
    return p


@pytest.fixture(scope="session")
def modelo_pequeno(params_pequenos):
    """Modelo logístico entrenado con 2 semillas de entrenamiento pequeñas (rápido)."""
    datos = dataset("N2", [1, 2], params_pequenos)
    m = ModeloRiesgo.entrenar("logistica", datos, guardar_muestra=500)
    m.tau = 0.2
    return m
