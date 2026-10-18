"""Matriz de decisión ponderada de la Fase 1.

Lee config/matriz.yaml, valida pesos y puntajes, calcula S = Σ (wᵢ · pᵢ) por agente
y hace el análisis de sensibilidad (peso de un criterio ± delta, el resto se reajusta
proporcionalmente para que Σ w = 1).

Salidas:
    results/matriz_decision.csv     matriz con pesos, puntajes, aportes y S
    results/sensibilidad.csv        S de cada agente con cada variación de peso
    results/matriz_decision.md      tablas en Markdown para el documento

Uso:
    python scripts/matriz_decision.py [--config config/matriz.yaml]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
AGENTES = ("A", "B")
TOL = 1e-9


def cargar(ruta: Path) -> dict:
    with ruta.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def validar(cfg: dict) -> None:
    criterios = cfg["criterios"]
    if len(criterios) < 6:
        raise ValueError(f"Se requieren al menos 6 criterios; hay {len(criterios)}.")
    suma = sum(c["peso"] for c in criterios)
    if abs(suma - 1.0) > 1e-6:
        raise ValueError(f"Los pesos deben sumar 1.0; suman {suma:.4f}.")
    for c in criterios:
        for ag in AGENTES:
            p = c[ag]["puntaje"]
            if not (isinstance(p, int) and 1 <= p <= 5):
                raise ValueError(f"Puntaje inválido ({p}) en '{c['nombre']}', agente {ag}.")
            if not str(c[ag].get("evidencia", "")).strip():
                raise ValueError(f"Puntaje sin evidencia en '{c['nombre']}', agente {ag}: no cuenta.")


def puntaje_ponderado(pesos: list[float], puntajes: list[int]) -> float:
    return sum(w * p for w, p in zip(pesos, puntajes))


def decidir(s: dict[str, float]) -> str:
    if abs(s["A"] - s["B"]) < TOL:
        return "empate"
    return max(s, key=s.get)


def reajustar(pesos: list[float], k: int, nuevo: float) -> list[float]:
    """Fija el peso k en `nuevo` y reparte el resto proporcionalmente entre los demás."""
    resto_original = 1.0 - pesos[k]
    factor = (1.0 - nuevo) / resto_original
    return [nuevo if i == k else w * factor for i, w in enumerate(pesos)]


def sensibilidad(cfg: dict) -> tuple[list[dict], int]:
    criterios = cfg["criterios"]
    pesos = [c["peso"] for c in criterios]
    pts = {ag: [c[ag]["puntaje"] for c in criterios] for ag in AGENTES}
    delta = cfg.get("sensibilidad_delta", 0.10)

    # Criterio más influyente: mayor |wᵢ · (p_Aᵢ − p_Bᵢ)|
    influencia = [abs(w * (a - b)) for w, a, b in zip(pesos, pts["A"], pts["B"])]
    k_max = max(range(len(criterios)), key=influencia.__getitem__)

    filas = []
    for k, c in enumerate(criterios):
        for signo in (-1, +1):
            nuevo = min(max(pesos[k] + signo * delta, 0.0), 1.0)
            w2 = reajustar(pesos, k, nuevo)
            s = {ag: puntaje_ponderado(w2, pts[ag]) for ag in AGENTES}
            filas.append({
                "criterio": c["nombre"],
                "mas_influyente": k == k_max,
                "influencia": influencia[k],
                "peso_original": pesos[k],
                "peso_nuevo": nuevo,
                "S_A": s["A"],
                "S_B": s["B"],
                "decision": decidir(s),
            })
    return filas, k_max


def punto_de_quiebre(cfg: dict) -> list[tuple[str, float | None]]:
    """Peso que debería tener cada criterio (resto reajustado) para que S(A) = S(B).

    Con d = p_A − p_B, la diferencia es D(w) = w·d_k + (1 − w)·R, donde R es la
    diferencia media ponderada de los demás criterios. D(w*) = 0 ⇒ w* = −R / (d_k − R).
    Devuelve None si no existe un peso en [0, 1) que produzca empate (un criterio con
    d_k = 0 solo "empata" si pesa 100 %, caso degenerado que no se reporta).
    """
    criterios = cfg["criterios"]
    pesos = [c["peso"] for c in criterios]
    d = [c["A"]["puntaje"] - c["B"]["puntaje"] for c in criterios]
    salida = []
    for k, c in enumerate(criterios):
        resto = 1.0 - pesos[k]
        r = sum(w * di for i, (w, di) in enumerate(zip(pesos, d)) if i != k) / resto
        den = d[k] - r
        w_star = -r / den if abs(den) > TOL else None
        valido = w_star is not None and d[k] != 0 and 0.0 <= w_star < 1.0
        salida.append((c["nombre"], w_star if valido else None))
    return salida


def pct(x: float) -> str:
    return f"{x * 100:.0f} %"


def num(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=RAIZ / "config" / "matriz.yaml")
    ap.add_argument("--salida", type=Path, default=RAIZ / "results")
    args = ap.parse_args()

    cfg = cargar(args.config)
    validar(cfg)
    criterios = cfg["criterios"]
    pesos = [c["peso"] for c in criterios]
    pts = {ag: [c[ag]["puntaje"] for c in criterios] for ag in AGENTES}
    s = {ag: puntaje_ponderado(pesos, pts[ag]) for ag in AGENTES}
    elegido = decidir(s)
    filas_sens, k_max = sensibilidad(cfg)
    base_se_mantiene = all(f["decision"] == elegido for f in filas_sens if f["mas_influyente"])

    args.salida.mkdir(parents=True, exist_ok=True)

    with (args.salida / "matriz_decision.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["criterio", "peso", "puntaje_A", "aporte_A", "evidencia_A",
                    "puntaje_B", "aporte_B", "evidencia_B"])
        for c in criterios:
            w.writerow([c["nombre"], c["peso"],
                        c["A"]["puntaje"], round(c["peso"] * c["A"]["puntaje"], 4), c["A"]["evidencia"],
                        c["B"]["puntaje"], round(c["peso"] * c["B"]["puntaje"], 4), c["B"]["evidencia"]])
        w.writerow(["Puntaje ponderado S", round(sum(pesos), 4),
                    "", round(s["A"], 4), "", "", round(s["B"], 4), ""])

    with (args.salida / "sensibilidad.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas_sens[0].keys()))
        w.writeheader()
        for fila in filas_sens:
            w.writerow({k: round(v, 4) if isinstance(v, float) else v for k, v in fila.items()})

    nombres = cfg["agentes"]
    md = ["### Matriz de decisión ponderada", "",
          "| Criterio | Peso (w) | Justificación del peso | A: puntaje | A: evidencia | B: puntaje | B: evidencia |",
          "|---|---|---|---|---|---|---|"]
    for c in criterios:
        md.append(f"| {c['nombre']} | {pct(c['peso'])} | {c['justificacion_peso']} | "
                  f"{c['A']['puntaje']} | {c['A']['evidencia']} | {c['B']['puntaje']} | {c['B']['evidencia']} |")
    md.append(f"| **Puntaje ponderado S** | **{pct(sum(pesos))}** | | **{num(s['A'])}** | | **{num(s['B'])}** | |")
    md += ["", f"A = {nombres['A']} · B = {nombres['B']}", "",
           "### Análisis de sensibilidad (± 10 puntos al peso, resto reajustado proporcionalmente)", "",
           "| Criterio | Influencia \\|w·(pA−pB)\\| | Peso original → nuevo | S A | S B | Decisión |",
           "|---|---|---|---|---|---|"]
    for f_ in filas_sens:
        marca = " **(más influyente)**" if f_["mas_influyente"] else ""
        md.append(f"| {f_['criterio']}{marca} | {num(f_['influencia'])} | "
                  f"{pct(f_['peso_original'])} → {pct(f_['peso_nuevo'])} | {num(f_['S_A'])} | "
                  f"{num(f_['S_B'])} | {f_['decision']} |")
    quiebres = punto_de_quiebre(cfg)
    md += ["", "### Punto de quiebre (peso que produciría empate S(A) = S(B))", "",
           "| Criterio | Peso actual | Peso de empate |", "|---|---|---|"]
    for (nombre, w_star), c in zip(quiebres, criterios):
        md.append(f"| {nombre} | {pct(c['peso'])} | {pct(w_star) if w_star is not None else 'no existe'} |")
    (args.salida / "matriz_decision.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # Resumen en consola
    print("Matriz de decisión")
    for c in criterios:
        print(f"  {c['nombre']:<36} w={c['peso']:.2f}  A={c['A']['puntaje']}  B={c['B']['puntaje']}")
    print(f"  S(A) = {s['A']:.4f}   S(B) = {s['B']:.4f}   ->  elegido: {elegido} ({nombres.get(elegido, '')})")
    print(f"\nSensibilidad (criterio más influyente: {criterios[k_max]['nombre']})")
    for f_ in filas_sens:
        marca = " *" if f_["mas_influyente"] else ""
        print(f"  {f_['criterio']:<36} {f_['peso_original']:.2f} -> {f_['peso_nuevo']:.2f}  "
              f"S(A)={f_['S_A']:.4f}  S(B)={f_['S_B']:.4f}  {f_['decision']}{marca}")
    print(f"\nLa decisión {'se mantiene' if base_se_mantiene else 'CAMBIA'} con ±10 puntos "
          f"en el criterio más influyente.")
    cambios = [f_ for f_ in filas_sens if f_["decision"] != elegido]
    print(f"Variaciones (de {len(filas_sens)}) en las que cambia la decisión: {len(cambios)}")
    print("\nPunto de quiebre (peso para empate):")
    for nombre, w_star in quiebres:
        print(f"  {nombre:<36} {f'{w_star:.4f}' if w_star is not None else 'no existe'}")


if __name__ == "__main__":
    main()
