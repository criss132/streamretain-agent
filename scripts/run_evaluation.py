"""Evaluación de la Fase 3: corre el agente desde cero en escenarios × semillas de prueba y
genera la tabla de resultados contra los umbrales congelados (config/umbrales.yaml).

Salidas:
    results/resultados.csv / .md         tabla obligatoria (una fila por medida)
    results/detalle_por_caso.csv         todas las métricas de cada caso (escenario × semilla)
    results/detalle_por_escenario.csv    media y d.e. por escenario
    results/resumen_ciclos.csv           resumen de cada ciclo semanal de cada caso
    results/entorno_evaluacion.json      equipo, versiones, commit y tiempos
    results/figuras/*.png
    logs/eval_<fecha>_<commit>/          logs JSONL (gzip) por caso; detalle completo en la semilla 1001

Uso:
    python scripts/run_evaluation.py                      # evaluación completa (13 × 10 = 130 casos)
    python scripts/run_evaluation.py --escenarios N2 F3 --semillas 1001 1002 --jobs 1 --salida /tmp/x
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from streamretain.config import escenarios, rango_semillas, umbrales  # noqa: E402
from streamretain.logging_utils import RegistroEjecucion  # noqa: E402

COLUMNA_MEDIDA = {"M1": "M1_accuracy", "M1R": "M1R_balanced_accuracy", "M2": "M2_recall",
                  "M3": "M3_precision_top_k", "M4": "M4_auc", "M5": "M5_robustez", "M6": "M6_latencia_media_s"}
SEMILLA_DETALLE = 1001


def _commit() -> str:
    try:
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True,
                           text=True, check=True).stdout.strip()
        sucio = subprocess.run(["git", "status", "--porcelain", "--", "src", "config", "models"], cwd=RAIZ,
                               capture_output=True, text=True).stdout.strip()
        return h + ("-dirty" if sucio else "")
    except Exception:
        return "sin-git"


def correr_caso(id_esc: str, semilla: int, dir_logs: str) -> dict:
    """Se ejecuta en un proceso aparte (joblib)."""
    sys.path.insert(0, str(RAIZ / "src"))
    from streamretain.evaluacion import cargar_modelos, ejecutar_caso

    modelo, baseline = cargar_modelos(RAIZ)
    detalle = semilla == SEMILLA_DETALLE
    nombre = f"{'detalle' if detalle else 'eventos'}_{id_esc}_s{semilla}.jsonl.gz"
    ruta = Path(dir_logs) / nombre
    registro = RegistroEjecucion(ruta, run_id=f"{id_esc}-s{semilla}", detalle=detalle,
                                 contexto={"escenario": id_esc, "semilla": semilla})
    t0 = time.time()
    r = ejecutar_caso(id_esc, semilla, modelo, baseline, registro=registro)
    registro.cerrar()
    m = r["metricas"]
    m["log"] = str(ruta.relative_to(RAIZ)).replace("\\", "/")
    m["segundos"] = round(time.time() - t0, 2)
    ciclos = [{**c, "escenario": id_esc, "semilla": semilla} for c in r["ciclos"]]
    return {"metricas": m, "ciclos": ciclos, "errores": r["errores"]}


def cumple(valor: float, operador: str, umbral: float) -> bool:
    return bool(valor >= umbral) if operador == ">=" else bool(valor <= umbral)


def tabla_resultados(casos: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    filas = []
    for med in cfg["medidas"]:
        col = COLUMNA_MEDIDA[med["id"]]
        sub = casos[casos["escenario"].isin(med["aplica_a"])]
        v = sub[col].astype(float)
        media, de = float(v.mean()), float(v.std(ddof=1)) if len(v) > 1 else 0.0
        if med["id"] == "M6":
            fmt = lambda x: f"{x:.2f} s"  # noqa: E731
        elif med["id"] == "M4":
            fmt = lambda x: f"{x:.3f}"  # noqa: E731
        else:
            fmt = lambda x: f"{x * 100:.1f} %"  # noqa: E731
        alcanzan = float(np.mean([cumple(x, med["operador"], med["umbral"]) for x in v]))
        por_tipo = {t: sub.loc[sub["tipo"] == t, col].mean() for t in ("normal", "limite", "falla")}
        logs = sorted(sub.loc[sub["semilla"] == SEMILLA_DETALLE, "log"])
        filas.append({
            "Medida": f"{med['id']} — {med['nombre']}",
            "Fórmula": med["formula"],
            "Umbral": f"{med['operador']} {fmt(med['umbral'])}",
            "Casos ejecutados": f"{len(v)} ({sub['escenario'].nunique()} escenarios × {sub['semilla'].nunique()} semillas)",
            "Resultado obtenido": f"{fmt(media)} ± {fmt(de)}",
            "¿Cumple?": "Sí" if cumple(media, med["operador"], med["umbral"]) else "No",
            "Casos que alcanzan el umbral": f"{alcanzan * 100:.0f} %",
            "Normal / Límite / Falla": " / ".join(fmt(por_tipo[t]) if not np.isnan(por_tipo[t]) else "—"
                                                  for t in ("normal", "limite", "falla")),
            "Evidencia": f"results/detalle_por_caso.csv (columna {col}); logs con detalle: {len(logs)} archivos "
                         f"detalle_*_s{SEMILLA_DETALLE}.jsonl.gz",
            "media": media, "de": de,
        })
    return pd.DataFrame(filas)


def figuras(casos: pd.DataFrame, cfg: dict, destino: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    destino.mkdir(parents=True, exist_ok=True)
    orden = [e for e in escenarios() if e in set(casos["escenario"])]
    colores = {"normal": "#3b6ea5", "limite": "#d08c2c", "falla": "#b34a4a"}
    tipo_de = casos.groupby("escenario")["tipo"].first()
    salidas = []

    meds = cfg["medidas"]
    fig, ejes = plt.subplots(len(meds), 1, figsize=(9, 2.3 * len(meds)), sharex=True)
    for ax, med in zip(ejes, meds):
        col = COLUMNA_MEDIDA[med["id"]]
        g = casos.groupby("escenario")[col].agg(["mean", "std"]).reindex(orden)
        aplica = [e in med["aplica_a"] for e in orden]
        ax.bar(range(len(orden)), g["mean"], yerr=g["std"], capsize=2,
               color=[colores[tipo_de[e]] if a else "#c8c8c8" for e, a in zip(orden, aplica)])
        ax.axhline(med["umbral"], color="black", linestyle="--", linewidth=1)
        ax.set_ylabel(med["id"])
        ax.set_title(f"{med['id']} — {med['nombre']} (umbral {med['operador']} {med['umbral']})", fontsize=9, loc="left")
    ejes[-1].set_xticks(range(len(orden)), orden)
    fig.suptitle("Media ± d.e. por escenario (10 semillas). Gris = escenario fuera de la medida", fontsize=10)
    fig.tight_layout()
    ruta = destino / "medidas_por_escenario.png"
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    salidas.append(ruta.name)

    comp = pd.DataFrame({
        "Agente": [casos["M1R_balanced_accuracy"].mean(), casos["M2_recall"].mean(),
                   casos["M3_precision_top_k"].mean(), casos["M4_auc"].mean(), casos["M1_accuracy"].mean()],
        "LR sin tendencia": [casos["baseline_lr_balanced_accuracy"].mean(), casos["baseline_lr_recall"].mean(),
                             casos["baseline_lr_precision_top_k"].mean(), casos["baseline_lr_auc"].mean(),
                             casos["baseline_lr_accuracy"].mean()],
        "Nadie cancela": [0.5, 0.0, np.nan, 0.5, casos["baseline_nadie_accuracy"].mean()],
    }, index=["Precisión balanceada", "Recall", "Precisión top-K", "AUC", "Accuracy"])
    ax = comp.plot.bar(figsize=(9, 4), rot=0, color=["#3b6ea5", "#8fb3d9", "#c8c8c8"])
    ax.set_title("Agente vs. baselines (media sobre los 130 casos)", fontsize=10)
    ax.set_ylim(0, 1)
    plt.tight_layout()
    ruta = destino / "agente_vs_baselines.png"
    plt.savefig(ruta, dpi=150)
    plt.close()
    salidas.append(ruta.name)
    return salidas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--escenarios", nargs="*", default=None)
    ap.add_argument("--semillas", nargs="*", type=int, default=None)
    ap.add_argument("--jobs", type=int, default=5)
    ap.add_argument("--salida", type=Path, default=RAIZ / "results")
    args = ap.parse_args()

    cfg = umbrales()
    ids = args.escenarios or list(escenarios())
    semillas = args.semillas or rango_semillas("prueba")
    commit = _commit()
    marca = dt.datetime.now().strftime("%Y%m%d_%H%M")
    dir_logs = RAIZ / "logs" / f"eval_{marca}_{commit}"
    dir_logs.mkdir(parents=True, exist_ok=True)
    print(f"Evaluación: {len(ids)} escenarios × {len(semillas)} semillas = {len(ids) * len(semillas)} casos "
          f"| commit {commit} | logs en {dir_logs.relative_to(RAIZ)}")

    from joblib import Parallel, delayed
    t0 = time.time()
    res = Parallel(n_jobs=args.jobs, verbose=5)(
        delayed(correr_caso)(e, s, str(dir_logs)) for e in ids for s in semillas)
    duracion = time.time() - t0

    casos = pd.DataFrame([r["metricas"] for r in res])
    ciclos = pd.DataFrame([c for r in res for c in r["ciclos"]])
    errores = [{"escenario": r["metricas"]["escenario"], "semilla": r["metricas"]["semilla"], **e}
               for r in res for e in r["errores"]]
    args.salida.mkdir(parents=True, exist_ok=True)
    casos.to_csv(args.salida / "detalle_por_caso.csv", index=False)
    ciclos.to_csv(args.salida / "resumen_ciclos.csv", index=False)
    ciclos.to_csv(dir_logs / "resumen_ciclos.csv", index=False)
    num = casos.select_dtypes("number").columns.drop(["semilla"])
    por_esc = casos.groupby(["escenario", "tipo"])[list(num)].agg(["mean", "std"])
    por_esc.columns = [f"{a}_{b}" for a, b in por_esc.columns]
    por_esc.reset_index().to_csv(args.salida / "detalle_por_escenario.csv", index=False)

    tabla = tabla_resultados(casos, cfg)
    tabla.drop(columns=["media", "de"]).to_csv(args.salida / "resultados.csv", index=False)
    cols_md = ["Medida", "Fórmula", "Umbral", "Casos ejecutados", "Resultado obtenido", "¿Cumple?",
               "Casos que alcanzan el umbral", "Normal / Límite / Falla", "Evidencia"]
    md = ["| " + " | ".join(cols_md) + " |", "|" + "---|" * len(cols_md)]
    md += ["| " + " | ".join(str(f[c]) for c in cols_md) + " |" for _, f in tabla.iterrows()]
    (args.salida / "resultados.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    figs = figuras(casos, cfg, args.salida / "figuras")
    if errores:
        (args.salida / "errores_evaluacion.json").write_text(json.dumps(errores, indent=2, ensure_ascii=False),
                                                              encoding="utf-8")

    import sklearn
    entorno = {
        "fecha": dt.datetime.now().isoformat(timespec="seconds"), "commit": commit,
        "tag_umbrales": "umbrales-congelados", "casos": len(casos), "errores": len(errores),
        "duracion_s": round(duracion, 1), "procesos": args.jobs,
        "equipo": {"so": platform.platform(), "procesador": platform.processor(),
                   "python": platform.python_version()},
        "versiones": {"numpy": np.__version__, "pandas": pd.__version__, "scikit-learn": sklearn.__version__},
        "logs": str(dir_logs.relative_to(RAIZ)).replace("\\", "/"), "figuras": figs,
        "nota_latencia": "M6 medida con varios procesos en paralelo en el mismo equipo (cota conservadora).",
    }
    (args.salida / "entorno_evaluacion.json").write_text(json.dumps(entorno, indent=2, ensure_ascii=False),
                                                          encoding="utf-8")
    print(tabla[["Medida", "Umbral", "Resultado obtenido", "¿Cumple?", "Casos que alcanzan el umbral",
                 "Normal / Límite / Falla"]].to_string(index=False))
    print(f"\nErrores: {len(errores)} | Duración: {duracion / 60:.1f} min")


if __name__ == "__main__":
    main()
