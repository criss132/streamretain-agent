"""Entorno simulado de una plataforma de streaming por suscripción (datos SINTÉTICOS).

Respeta las propiedades de ambiente de la sección 3 del diseño:
- Parcialmente observable: la intención de cancelar es latente; el agente solo ve consumo,
  recencia, plan y cambios de pago.
- Estocástico: decisiones de cancelación, consumo, logins, fallas y efecto de las ofertas son
  aleatorios (con semilla, para reproducibilidad).
- Secuencial y dinámico: el estado evoluciona semana a semana; las ofertas cambian el futuro.

Mecánica principal
- Cada suscriptor tiene un riesgo latente semanal de "decidir cancelar". Al decidir, cancela
  `semanas_decaimiento_previo` semanas después. Mientras tanto su consumo cae y aumentan
  sus días sin login (señal débil y con ruido). Una fracción cancela sin señal previa.
- Un cambio reciente de método de pago multiplica el riesgo.
- Una oferta de retención exitosa (probabilidad `efecto_oferta`) evita la cancelación si llega
  dentro de las 4 semanas anteriores a la fecha de cancelación.
- Etiqueta natural (evaluación): ¿el usuario tenía una cancelación programada en (t, t+4],
  haya sido rescatado o no? Etiqueta real (aprendizaje): ¿canceló de verdad en (t, t+4]?

Toda la aleatoriedad que no depende del agente se pre-sortea por usuario y semana, de modo
que la trayectoria del entorno es idéntica para cualquier agente con la misma semilla
(comparación justa con los baselines).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import poisson

PLANES = ("basico", "estandar", "premium")
HORAS_MAX_SEMANA = 168.0

# Constantes estructurales del simulador (no se calibran; se documentan en el README).
CONSTANTES = {
    "horas_media_plan": {"basico": 6.0, "estandar": 9.0, "premium": 12.0},
    "riesgo_plan": {"basico": 1.3, "estandar": 1.0, "premium": 0.7},
    "sigma_riesgo": 0.8,             # heterogeneidad del riesgo latente entre usuarios
    "carga_riesgo_en_horas": 0.25,   # usuarios de mayor riesgo latente consumen algo menos
    "sigma_horas_base": 0.35,        # dispersión del consumo base entre usuarios
    "prob_cambio_pago_semanal": 0.03,
    "semanas_cambio_reciente": 4,
    "dias_login_base": 1.5,
}

TIPOS_CORRUPCION = ("horas_nan", "horas_negativas", "horas_fuera_rango",
                    "dias_nan", "dias_negativos", "plan_desconocido")


@dataclass
class EventoCancelacion:
    user_id: str
    semana: int
    rescatado: bool


class StreamingEnv:
    """Entorno semanal. Uso: `observar()` → (agente decide/actúa) → `avanzar()`."""

    def __init__(self, params: dict, seed: int):
        self.p = params
        self.seed = int(seed)
        self.semana = 0
        self.inicio_ciclos = int(params["historial_previo_semanas"])
        self.horizonte = self.inicio_ciclos + int(params["ciclos"]) + 4
        self.semana_deriva = None
        if params.get("deriva"):
            self.semana_deriva = self.inicio_ciclos + int(params["deriva"]["semana"])

        self._rng_usuarios = np.random.default_rng([self.seed, 2])
        self._rng_altas = np.random.default_rng([self.seed, 1])
        self._rng_ofertas = np.random.default_rng([self.seed, 4])

        self._n_inicial = int(params["n_usuarios"])
        self._escala: float | None = None   # se resuelve con la población inicial
        self._u: dict[str, np.ndarray] = {}
        self._crear_usuarios(self._n_inicial, semana_alta=0)
        self.eventos: list[EventoCancelacion] = []
        self.corrupciones: list[dict] = []      # verdad de terreno de registros inválidos inyectados
        self._observados: dict[int, np.ndarray] = {}  # semana -> índices activos observados
        self._con_senal: dict[int, set[str]] = {}     # semana -> usuarios cuya señal ya es visible

    # ------------------------------------------------------------------ creación
    def _factor_pago(self) -> float:
        p_rec = 1.0 - (1.0 - CONSTANTES["prob_cambio_pago_semanal"]) ** CONSTANTES["semanas_cambio_reciente"]
        return 1.0 + p_rec * (float(self.p["multiplicador_cambio_pago"]) - 1.0)

    def _resolver_escala(self, x: np.ndarray) -> float:
        """Escala c del riesgo semanal para que la tasa de cancelación a 4 semanas observada en
        los ciclos de decisión coincida con la declarada en el escenario.

        Se resuelve por bisección con una mini simulación vectorizada de la dinámica de
        decisión/cancelación/altas (con un generador propio), porque la heterogeneidad del
        riesgo hace que los usuarios más riesgosos salgan primero (supervivencia).
        """
        tasa = float(self.p["tasa_cancelacion_4s"])
        fp = self._factor_pago()
        L = int(self.p["semanas_decaimiento_previo"])
        nuevos_por_semana = float(self.p["tasa_usuarios_nuevos"]) * len(x)
        ciclos = range(self.inicio_ciclos, self.horizonte - 4)

        def tasa_observada(c: float) -> float:
            rng = np.random.default_rng([self.seed, 99])
            riesgo = x.copy()
            cancel = np.full(len(x), -1)
            activo = np.ones(len(x), dtype=bool)
            fotos = {}
            for w in range(self.horizonte):
                decide = activo & (cancel < 0) & (rng.random(len(riesgo)) < np.clip(c * riesgo * fp, 0, 1))
                cancel[decide] = w + L
                if w in ciclos:
                    fotos[w] = activo.copy()
                activo &= ~(cancel == w + 1)
                n_new = rng.poisson(nuevos_por_semana)
                riesgo = np.concatenate([riesgo, rng.choice(x, n_new)])
                cancel = np.concatenate([cancel, np.full(n_new, -1)])
                activo = np.concatenate([activo, np.ones(n_new, dtype=bool)])
            # la etiqueta usa las fechas de cancelación finales (incluye decisiones posteriores a w)
            tasas = [np.mean((cancel[:len(a)][a] > w) & (cancel[:len(a)][a] <= w + 4)) for w, a in fotos.items()]
            return float(np.mean(tasas))

        lo, hi = 0.0, 0.05
        while tasa_observada(hi) < tasa and hi < 50:
            hi *= 2.0
        for _ in range(30):
            mid = (lo + hi) / 2.0
            lo, hi = (mid, hi) if tasa_observada(mid) < tasa else (lo, mid)
        return (lo + hi) / 2.0

    def _crear_usuarios(self, n: int, semana_alta: int) -> None:
        if n <= 0:
            return
        rng, T = self._rng_usuarios, self.horizonte
        mezcla = self.p["mezcla_planes"]
        plan = rng.choice(len(PLANES), size=n, p=[mezcla[k] for k in PLANES])
        z = rng.standard_normal(n)
        s = CONSTANTES["sigma_riesgo"]
        r = np.exp(s * z - s * s / 2.0)
        riesgo_plan = np.array([CONSTANTES["riesgo_plan"][PLANES[i]] for i in plan])
        media_h = np.array([CONSTANTES["horas_media_plan"][PLANES[i]] for i in plan])
        sh = CONSTANTES["sigma_horas_base"]
        horas_base = media_h * np.exp(-CONSTANTES["carga_riesgo_en_horas"] * z
                                      + sh * rng.standard_normal(n) - sh * sh / 2.0)
        if self._escala is None:
            self._escala = self._resolver_escala(r * riesgo_plan)
        nuevos = {
            "plan": plan,
            "h_semanal": self._escala * r * riesgo_plan,
            "horas_base": horas_base,
            "alta": np.full(n, semana_alta),
            "activo": np.ones(n, dtype=bool),
            "decidido": np.zeros(n, dtype=bool),
            "subito": np.zeros(n, dtype=bool),
            "sem_decision": np.full(n, -1),
            "sem_cancel": np.full(n, -1),
            "ult_cambio_pago": np.full(n, -100),
            "ult_oferta": np.full(n, -100),
            "oferta_efectiva": np.zeros(n, dtype=bool),
            # sorteos pre-asignados por usuario y semana
            "u_riesgo": rng.random((n, T)),
            "u_pago": rng.random((n, T)),
            "u_subito": rng.random((n, T)),
            "eps_horas": rng.standard_normal((n, T)),
            "u_login": rng.random((n, T)),
            "u_corrupcion": rng.random((n, T)),
            "tipo_corrupcion": rng.integers(0, len(TIPOS_CORRUPCION), (n, T)),
        }
        if not self._u:
            self._u = nuevos
        else:
            self._u = {k: np.concatenate([self._u[k], v]) for k, v in nuevos.items()}

    @property
    def n_total(self) -> int:
        return len(self._u["plan"])

    @staticmethod
    def user_id(i: int) -> str:
        return f"U{i:05d}"

    def _indice(self, user_id: str) -> int:
        return int(user_id[1:])

    # ------------------------------------------------------------------ dinámica
    def _param_senal(self, nombre: str) -> float:
        if self.semana_deriva is not None and self.semana >= self.semana_deriva:
            deriva = self.p["deriva"]
            if nombre in deriva:
                return float(deriva[nombre])
        return float(self.p[nombre])

    def _factor_global(self) -> float:
        if self.semana_deriva is not None and self.semana >= self.semana_deriva:
            return 1.0 + float(self.p["deriva"].get("consumo_global_rel", 0.0))
        return 1.0

    def _actualizar_estado_semana(self) -> None:
        """Cambios de pago y nuevas decisiones de cancelar al inicio de la semana."""
        u, w = self._u, self.semana
        act = u["activo"]
        cambio = act & (u["u_pago"][:, w] < CONSTANTES["prob_cambio_pago_semanal"])
        u["ult_cambio_pago"][cambio] = w
        reciente = (w - u["ult_cambio_pago"]) < CONSTANTES["semanas_cambio_reciente"]
        h = u["h_semanal"] * np.where(reciente, float(self.p["multiplicador_cambio_pago"]), 1.0)
        decide = act & ~u["decidido"] & (u["u_riesgo"][:, w] < h)
        u["decidido"][decide] = True
        u["sem_decision"][decide] = w
        # el consumo empieza a caer `semanas_decaimiento_previo` semanas antes de cancelar
        u["sem_cancel"][decide] = w + int(self.p["semanas_decaimiento_previo"])
        u["subito"][decide] = u["u_subito"][decide, w] < float(self.p["fraccion_cancelacion_sin_senal"])

    def observar(self) -> pd.DataFrame:
        """Lote crudo de percepciones de la semana actual (incluye registros corruptos)."""
        if self.semana not in self._observados:
            self._actualizar_estado_semana()
        u, w = self._u, self.semana
        idx = np.flatnonzero(u["activo"])
        self._observados[w] = idx
        L = float(self.p["semanas_decaimiento_previo"])
        en_senal = u["decidido"][idx] & ~u["subito"][idx]
        self._con_senal[w] = {self.user_id(i) for i in idx[en_senal]}
        k = np.clip((w - u["sem_decision"][idx] + 1) / L, 0.0, 1.0) * en_senal
        caida = self._param_senal("caida_consumo_media")
        ruido = self._param_senal("ruido_consumo_rel")
        horas = (u["horas_base"][idx] * self._factor_global() * (1.0 - caida * k)
                 * np.exp(ruido * u["eps_horas"][idx, w] - ruido * ruido / 2.0))
        lam = (CONSTANTES["dias_login_base"] + 4.0 * np.exp(-u["horas_base"][idx] / 4.0)
               + self._param_senal("aumento_dias_sin_login") * k)
        dias = poisson.ppf(u["u_login"][idx, w], lam).astype(float)
        cambio = ((w - u["ult_cambio_pago"][idx]) < CONSTANTES["semanas_cambio_reciente"]).astype(int)
        df = pd.DataFrame({
            "user_id": [self.user_id(i) for i in idx],
            "semana": w,
            "horas_vistas": np.round(horas, 2),
            "dias_desde_ultimo_login": dias,
            "tipo_plan": [PLANES[j] for j in u["plan"][idx]],
            "cambio_metodo_pago": cambio,
        })
        df["tipo_plan"] = df["tipo_plan"].astype(object)
        corr = u["u_corrupcion"][idx, w] < float(self.p["tasa_registros_invalidos"])
        for pos in np.flatnonzero(corr):
            tipo = TIPOS_CORRUPCION[u["tipo_corrupcion"][idx[pos], w]]
            self._corromper(df, pos, tipo)
            self.corrupciones.append({"user_id": df.at[pos, "user_id"], "semana": w, "tipo": tipo})
        return df

    @staticmethod
    def _corromper(df: pd.DataFrame, pos: int, tipo: str) -> None:
        if tipo == "horas_nan":
            df.at[pos, "horas_vistas"] = np.nan
        elif tipo == "horas_negativas":
            df.at[pos, "horas_vistas"] = -abs(df.at[pos, "horas_vistas"]) - 1.0
        elif tipo == "horas_fuera_rango":
            df.at[pos, "horas_vistas"] = HORAS_MAX_SEMANA + 50.0
        elif tipo == "dias_nan":
            df.at[pos, "dias_desde_ultimo_login"] = np.nan
        elif tipo == "dias_negativos":
            df.at[pos, "dias_desde_ultimo_login"] = -3.0
        elif tipo == "plan_desconocido":
            df.at[pos, "tipo_plan"] = "desconocido"

    def registrar_oferta(self, user_id: str, semana: int) -> bool:
        """Lo invoca la API de marketing al activar una oferta. Devuelve si fue efectiva."""
        i = self._indice(user_id)
        efectiva = bool(self._rng_ofertas.random() < float(self.p["efecto_oferta"]))
        self._u["ult_oferta"][i] = semana
        self._u["oferta_efectiva"][i] = efectiva
        return efectiva

    def avanzar(self) -> list[EventoCancelacion]:
        """Cierra la semana: procesa cancelaciones (o rescates) y altas de usuarios nuevos."""
        if self.semana not in self._observados:
            self._actualizar_estado_semana()
        u = self._u
        siguiente = self.semana + 1
        vence = u["activo"] & u["decidido"] & (u["sem_cancel"] == siguiente)
        eventos = []
        for i in np.flatnonzero(vence):
            rescatado = bool(u["oferta_efectiva"][i] and (siguiente - 4) <= u["ult_oferta"][i] < siguiente)
            if rescatado:
                u["decidido"][i] = False
                u["sem_decision"][i] = -1
                u["oferta_efectiva"][i] = False
            else:
                u["activo"][i] = False
            eventos.append(EventoCancelacion(self.user_id(i), int(siguiente), rescatado))
        self.eventos.extend(eventos)
        self.semana = siguiente
        if self.semana < self.horizonte:
            n_nuevos = int(self._rng_altas.poisson(float(self.p["tasa_usuarios_nuevos"]) * self._n_inicial))
            self._crear_usuarios(n_nuevos, semana_alta=self.semana)
        return eventos

    # ------------------------------------------------------------------ etiquetas
    def _etiqueta(self, semana_t: int, incluir_rescatados: bool) -> pd.Series:
        if self.semana < semana_t + 4:
            raise RuntimeError(f"La ventana de la semana {semana_t} aún no ha vencido.")
        idx = self._observados.get(semana_t, np.array([], dtype=int))
        positivos = {e.user_id for e in self.eventos
                     if semana_t < e.semana <= semana_t + 4 and (incluir_rescatados or not e.rescatado)}
        ids = [self.user_id(i) for i in idx]
        return pd.Series([int(x in positivos) for x in ids], index=pd.Index(ids, name="user_id"), dtype=int)

    def etiquetas_naturales(self, semana_t: int) -> pd.Series:
        """SOLO para evaluación: cancelación programada en (t, t+4] sin intervención."""
        return self._etiqueta(semana_t, incluir_rescatados=True)

    def resultados_reales(self, semana_t: int) -> pd.Series:
        """Estado posterior observable (sección 5 del diseño): ¿canceló de verdad en (t, t+4]?"""
        return self._etiqueta(semana_t, incluir_rescatados=False)

    def usuarios_con_senal(self, semana_t: int) -> set[str]:
        """SOLO para análisis: usuarios que en t ya decidieron cancelar y muestran caída de consumo."""
        return self._con_senal.get(semana_t, set())

    def usuarios_sin_historial(self, semana_t: int, minimo: int = 2) -> set[str]:
        """Verdad de terreno: usuarios activos en t con menos de `minimo` semanas de existencia."""
        idx = self._observados.get(semana_t, np.array([], dtype=int))
        return {self.user_id(i) for i in idx if semana_t - self._u["alta"][i] + 1 < minimo}


class MarketingAPIError(Exception):
    """Error devuelto por el sistema de marketing (p. ej., HTTP 503)."""


class MarketingTimeout(TimeoutError):
    """La llamada al sistema de marketing excedió el tiempo de espera."""


class MarketingAPI:
    """Mock del sistema de marketing con fallas y timeouts configurables (sin esperas reales)."""

    def __init__(self, env: StreamingEnv, tasa_fallo: float, tasa_timeout: float, seed: int):
        self.env = env
        self.tasa_fallo = float(tasa_fallo)
        self.tasa_timeout = float(tasa_timeout)
        self._rng = np.random.default_rng([int(seed), 3])
        self._n = 0

    def activate_offer(self, user_id: str, semana: int) -> dict:
        self._n += 1
        u = self._rng.random()
        if u < self.tasa_timeout:
            raise MarketingTimeout(f"timeout activando oferta para {user_id}")
        if u < self.tasa_timeout + self.tasa_fallo:
            raise MarketingAPIError(f"503 servicio no disponible para {user_id}")
        self.env.registrar_oferta(user_id, semana)
        return {"user_id": user_id, "estado": "activada", "oferta_id": f"OF-{semana:02d}-{self._n:06d}"}
