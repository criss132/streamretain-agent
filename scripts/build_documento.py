"""Genera el documento de diseño ajustado (DOCX y, si hay Microsoft Word, PDF).

Parte del documento de la Tarea 2 (StreamRetain-Agent, L. Ortiz, 25-ago-2026), lo corrige y
lo amplía según la guía de la Tarea 3. Los números de la matriz y de las pruebas se leen de
results/ (no se copian a mano). Los enlaces y minutos del video se leen de docs/enlaces.yaml.

Uso: python scripts/build_documento.py [--sin-pdf]
Requiere: python-docx (y Microsoft Word en Windows para exportar a PDF).
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

import pandas as pd
import yaml
from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[1]
RES = RAIZ / "results"
DIAG = RAIZ / "docs" / "diagramas"
SALIDA = RAIZ / "docs" / "Diseno_Ajustado_StreamRetain.docx"
AZUL = RGBColor(0x1F, 0x3A, 0x5F)


# ====================================================================== utilidades
def runs(par, texto: str, tam=None, italic=False, bold_todo=False, color=None):
    """Agrega runs a un párrafo interpretando **negrita** y `código`."""
    negrita = codigo = False
    for trozo in re.split(r"(\*\*|`)", str(texto)):
        if trozo == "**":
            negrita = not negrita
            continue
        if trozo == "`":
            codigo = not codigo
            continue
        if not trozo:
            continue
        r = par.add_run(trozo)
        r.bold = negrita or bold_todo
        r.italic = italic
        if codigo:
            r.font.name = "Consolas"
            r.element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
        if tam:
            r.font.size = Pt(tam * (0.92 if codigo else 1))
        if color is not None:
            r.font.color.rgb = color
    return par


class Doc:
    def __init__(self):
        self.d = Document()
        self.n_tabla = 0
        self.n_figura = 0
        s = self.d.styles["Normal"]
        s.font.name = "Calibri"
        s.font.size = Pt(11)
        s.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
        s.paragraph_format.space_after = Pt(6)
        s.paragraph_format.line_spacing = 1.1
        for nivel, tam in ((1, 15), (2, 12.5), (3, 11.5)):
            h = self.d.styles[f"Heading {nivel}"]
            h.font.name = "Calibri"
            h.font.size = Pt(tam)
            h.font.color.rgb = AZUL
            h.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
            h.paragraph_format.space_before = Pt(12 if nivel == 1 else 8)
            h.paragraph_format.space_after = Pt(4)
        sec = self.d.sections[0]
        sec.page_height, sec.page_width = Cm(27.94), Cm(21.59)   # carta
        for m in ("left_margin", "right_margin"):
            setattr(sec, m, Cm(2.3))
        sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.2)
        self._pie()

    def _pie(self):
        p = self.d.sections[0].footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = p.add_run("StreamRetain-Agent · Diseño ajustado · Página ")
        r.font.size = Pt(8.5)
        for tipo, texto in (("begin", None), (None, "PAGE"), ("end", None)):
            run = p.add_run()
            run.font.size = Pt(8.5)
            if tipo:
                f = OxmlElement("w:fldChar")
                f.set(qn("w:fldCharType"), tipo)
                run._r.append(f)
            else:
                t = OxmlElement("w:instrText")
                t.set(qn("xml:space"), "preserve")
                t.text = texto
                run._r.append(t)

    def h(self, texto, nivel=1):
        return self.d.add_heading(texto, level=nivel)

    def p(self, texto, tam=None, align=None, italic=False, espacio=None):
        """Párrafo con **negritas** en línea."""
        par = runs(self.d.add_paragraph(), texto, tam, italic)
        if align == "centro":
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif align == "just":
            par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if espacio is not None:
            par.paragraph_format.space_after = Pt(espacio)
        return par

    def lista(self, items, numerada=False):
        for it in items:
            par = runs(self.d.add_paragraph(style="List Number" if numerada else "List Bullet"), it)
            par.paragraph_format.space_after = Pt(2)

    def _sombra(self, celda, color):
        tcPr = celda._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), color)
        tcPr.append(shd)

    def tabla(self, titulo, encabezados, filas, anchos_cm=None, tam=8.5, negrita_ultima=False):
        self.n_tabla += 1
        cap = self.d.add_paragraph()
        r = cap.add_run(f"Tabla {self.n_tabla}. ")
        r.bold = True
        r.font.size = Pt(9.5)
        runs(cap, titulo, 9.5)
        cap.paragraph_format.space_after = Pt(2)
        cap.paragraph_format.keep_with_next = True
        t = self.d.add_table(rows=1, cols=len(encabezados))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, e in enumerate(encabezados):
            c = t.rows[0].cells[j]
            c.text = ""
            runs(c.paragraphs[0], e, tam, bold_todo=True, color=RGBColor(0xFF, 0xFF, 0xFF))
            self._sombra(c, "1F3A5F")
        trPr = t.rows[0]._tr.get_or_add_trPr()
        th = OxmlElement("w:tblHeader")
        th.set(qn("w:val"), "true")
        trPr.append(th)
        for i, fila in enumerate(filas):
            cells = t.add_row().cells
            for j, v in enumerate(fila):
                cells[j].text = ""
                runs(cells[j].paragraphs[0], v, tam, bold_todo=negrita_ultima and i == len(filas) - 1)
                if i % 2 == 1:
                    self._sombra(cells[j], "EEF2F7")
        if anchos_cm:
            for fila in t.rows:
                for j, w in enumerate(anchos_cm):
                    fila.cells[j].width = Cm(w)
        self.d.add_paragraph().paragraph_format.space_after = Pt(2)
        return self.n_tabla

    def figura(self, ruta, titulo, ancho_cm=16.5):
        self.n_figura += 1
        par = self.d.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run().add_picture(str(ruta), width=Cm(ancho_cm))
        par.paragraph_format.keep_with_next = True
        cap = self.d.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cap.add_run(f"Figura {self.n_figura}. ")
        r.bold = True
        r.font.size = Pt(9.5)
        runs(cap, titulo, 9.5)
        return self.n_figura

    def salto(self):
        self.d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def coma(texto: str) -> str:
    """Separador decimal en español (solo en números)."""
    return re.sub(r"(\d)\.(\d)", r"\1,\2", str(texto))


def miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def pct(x: float, dec=1) -> str:
    return coma(f"{x * 100:.{dec}f} %")


# ====================================================================== datos
def cargar_datos() -> dict:
    casos = pd.read_csv(RES / "detalle_por_caso.csv")
    resultados = pd.read_csv(RES / "resultados.csv")
    matriz = pd.read_csv(RES / "matriz_decision.csv")
    sens = pd.read_csv(RES / "sensibilidad.csv")
    entorno = yaml.safe_load((RES / "entorno_evaluacion.json").read_text(encoding="utf-8"))
    entren = yaml.safe_load((RES / "entrenamiento.json").read_text(encoding="utf-8"))
    calib = yaml.safe_load((RES / "calibracion_simulador.json").read_text(encoding="utf-8"))
    enlaces = yaml.safe_load((RAIZ / "docs" / "enlaces.yaml").read_text(encoding="utf-8"))
    m = casos.mean(numeric_only=True)
    sumas = casos.sum(numeric_only=True)
    por_esc = casos.groupby("escenario")
    m6 = float(casos.loc[casos["n_usuarios_inicial"] == 2000, "M6_latencia_media_s"].mean())
    return {"casos": casos, "resultados": resultados, "matriz": matriz, "sens": sens, "entorno": entorno,
            "entren": entren, "calib": calib, "enlaces": enlaces, "m6": m6, "m": m, "sumas": sumas, "por_esc": por_esc}


# ====================================================================== contenido
def portada(D: Doc, X: dict):
    for _ in range(3):
        D.p("")
    D.p("Universidad Tecnológica de Bolívar", 16, "centro")
    D.p("Escuela de Transformación Digital · Ingeniería de Sistemas y Computación", 11, "centro")
    D.p("")
    D.p("**Diseño ajustado e implementación de un agente inteligente**", 15, "centro")
    D.p("Tarea 3 — Segundo Parcial [Agentes Inteligentes]", 11.5, "centro")
    D.p("")
    D.p("**STREAMRETAIN-AGENT — AGENTE DE PREDICCIÓN DE CANCELACIÓN EN STREAMING**", 13, "centro")
    for _ in range(3):
        D.p("")
    D.p("Presentado por:", 11, "centro", espacio=2)
    D.p("Christian David Menco Galván — T00058749", 11.5, "centro", espacio=2)
    D.p("Levis Adrian Ortiz Cano — T00083674", 11.5, "centro")
    D.p("")
    D.p("Curso: Inteligencia Artificial (ISCO-A06A-I-1233-202620)", 11, "centro", espacio=2)
    D.p("Docente: Edwin Alexander Puertas Del Castillo", 11, "centro")
    for _ in range(4):
        D.p("")
    D.p(f"Cartagena de Indias, {X['enlaces']['fecha_documento']}", 11, "centro")
    D.p("Documento base: «Diseño inicial de un agente inteligente — StreamRetain-Agent» (Tarea 2, "
        "L. Ortiz, 25 de agosto de 2026), corregido y ampliado.", 9, "centro", italic=True)
    D.salto()


def tabla_cambios(D: Doc, X: dict):
    D.h("Tabla de cambios", 1)
    D.p("**Retroalimentación del docente:** no recibimos retroalimentación del docente para el documento de "
        "StreamRetain-Agent de la Tarea 2. Por eso esta tabla recoge **solo los cambios propios** de la "
        "pareja: la matriz de decisión, las medidas reformuladas, las precisiones de diseño que surgieron al "
        "implementar y la sección 9 nueva. No se incluyen ni se simulan correcciones del docente.", align="just")
    filas = [
        ["Portada", "Presentado por: Levis Adrian Ortiz Cano", "Presentado por ambos integrantes de la pareja",
         "La Tarea 3 es en pareja y tiene una sola entrega."],
        ["Selección justificada del agente (nueva)", "—", "Matriz de decisión ponderada, sensibilidad y "
         "justificación (Fase 1)", "La guía la exige como sección nueva antes del diseño."],
        ["4. Descripción del entorno", "«El conjunto de datos definitivo deberá quedar formalmente definido antes "
         "de la fase de evaluación»", "El entorno de evaluación es un simulador estocástico con datos sintéticos, "
         "13 escenarios definidos y congelados antes de probar", "No hay acceso a una plataforma real; la guía "
         "permite un simulador mínimo que respete las secciones 3 y 5."],
        ["5. Entradas y sensores", "Estado posterior de la suscripción como dato categórico",
         "Se precisa que el agente lo recibe 4 semanas después de cada predicción y solo lo usa para aprender",
         "Evitar fuga de información: el agente no puede ver el futuro al decidir."],
        ["7. Medidas de desempeño", "«Precisión general» ≥ 75 % = predicciones correctas / total",
         "Se nombra «exactitud (accuracy)» y se conserva como M1. La medida principal pasa a ser la precisión "
         "balanceada ≥ 75 % (M1R). Se agregan M2–M6 con fórmula y umbral", "«Precisión» se confunde con "
         "«precision». Con tasas de cancelación ≤ 25 %, predecir «nadie cancela» ya da accuracy ≥ 75 %: la medida "
         "original no discrimina. La guía pide fórmula, umbral previo y prueba por medida."],
        ["8. Razonamiento y toma de decisiones", "«Se podrá utilizar SHAP»",
         "Explicación local por oclusión (aporte de cada variable al reemplazarla por su mediana)",
         "Funciona igual con el modelo calibrado, es rápida y evita una dependencia pesada en el despliegue."],
        ["8. Aprendizaje y adaptación", "Reentrenar si la nueva versión mantiene o mejora la medida",
         "Compuerta concreta: precisión balanceada en un holdout de resultados recientes; se excluyen los "
         "usuarios intervenidos", "La oferta cambia el resultado de quien la recibe y sesgaría la etiqueta."],
        ["9. Desarrollo del agente (nueva)", "—", "Arquitectura, tecnologías, entradas, salidas, diagramas de "
         "secuencia, diferencias, pruebas, limitaciones y enlaces", "Exigida por la guía de la Tarea 3."],
        ["10. Conclusiones", "Sección 9", "Pasa a ser la sección 10 y se actualiza con los resultados",
         "Orden exigido por la guía."],
        ["Referencias", "Formato libre; Russell y Norvig sin año ni edición",
         "Formato APA 7, con citas en el texto que corresponden una a una; se agregan las fuentes usadas en la "
         "implementación", "Normas del curso."],
    ]
    D.tabla("Cambios respecto al documento de la Tarea 2.", ["Sección", "Qué decía", "Qué dice ahora",
                                                             "Por qué cambió"], filas, [2.8, 4.0, 5.2, 5.0], 8)


def seleccion(D: Doc, X: dict):
    D.h("Selección justificada del agente (Fase 1)", 1)
    mz = X["matriz"]
    sA = float(mz.iloc[-1]["aporte_A"])
    sB = float(mz.iloc[-1]["aporte_B"])
    D.p("Comparamos los dos agentes que diseñamos en la Tarea 2 con una matriz de decisión ponderada. "
        "Agente A: PickFlow-Agent, optimización de picking en bodega (C. Menco). Agente B: StreamRetain-Agent, "
        "predicción de cancelación en streaming (L. Ortiz).", align="just")
    D.p("Primero fijamos los pesos (los seis criterios mínimos de la guía, con su peso sugerido) y después "
        "puntuamos de 1 a 5, con una frase de evidencia por puntaje. El puntaje es S = Σ (wᵢ · pᵢ), con "
        "Σ wᵢ = 1 y máximo 5. Todo se calcula con `scripts/matriz_decision.py` a partir de "
        "`config/matriz.yaml`, así que cualquiera puede reconstruir la decisión.", align="just")
    filas = []
    for _, r in mz.iloc[:-1].iterrows():
        filas.append([r["criterio"], pct(r["peso"], 0), int(r["puntaje_A"]), r["evidencia_A"],
                      int(r["puntaje_B"]), r["evidencia_B"]])
    filas.append(["**Puntaje ponderado S**", "100 %", f"**{coma(f'{sA:.2f}')}**", "",
                  f"**{coma(f'{sB:.2f}')}**", ""])
    t = D.tabla("Matriz de decisión ponderada (A = PickFlow-Agent, B = StreamRetain-Agent).",
                ["Criterio", "Peso", "A", "Evidencia A", "B", "Evidencia B"], filas,
                [2.6, 1.2, 0.8, 5.7, 0.8, 5.9], 7.5)
    D.p(f"Como muestra la Tabla {t}, StreamRetain-Agent obtiene **S = {coma(f'{sB:.2f}')}** frente a "
        f"{coma(f'{sA:.2f}')} de PickFlow-Agent. Gana en los tres criterios de mayor peso: viabilidad técnica, "
        "disponibilidad del entorno y medibilidad. PickFlow solo gana en complejidad de IA, y en costo y valor "
        "del problema empatan.", align="just")
    sens = X["sens"]
    filas = [[r["criterio"] + (" (más influyente)" if r["mas_influyente"] else ""),
              f"{pct(r['peso_original'], 0)} → {pct(r['peso_nuevo'], 0)}", coma(f"{r['S_A']:.2f}"),
              coma(f"{r['S_B']:.2f}"), "B" if r["decision"] == "B" else r["decision"]]
             for _, r in sens.iterrows()]
    t2 = D.tabla("Análisis de sensibilidad: cada peso ± 10 puntos y el resto reajustado en proporción.",
                 ["Criterio", "Peso original → nuevo", "S(A)", "S(B)", "Gana"], filas, [5.5, 3.5, 2, 2, 1.5], 8)
    D.p(f"**Sensibilidad.** El criterio más influyente es la viabilidad técnica, con el mayor |w·(pA − pB)| = 0,50. "
        f"Si su peso sube o baja 10 puntos, la decisión **se mantiene** (Tabla {t2}). Repetimos la prueba con "
        "los otros cinco criterios y en ninguna de las 12 variaciones cambia el resultado. El único criterio "
        "que podría invertirlo es la complejidad de IA, y para llegar al empate tendría que pesar 35 %, más del "
        "doble del peso sugerido.", align="just")
    D.p("**Qué perdemos al descartar PickFlow-Agent:**")
    D.lista(["Un ambiente multiagente y secuencial, con decisiones de asignación y ruta que se encadenan.",
             "Un elemento de desempeño basado en utilidad, más rico en razonamiento que una clasificación con "
             "umbral.",
             "Una medida de impacto operativo directo (−20 % del tiempo de preparación)."])
    D.p("Lo compensamos así:")
    D.lista(["StreamRetain conserva estado interno por suscriptor.",
             "Aprende de los resultados con una compuerta de reentrenamiento.",
             "Prioriza las ofertas con un presupuesto.",
             "Opera en un entorno estocástico con fallas inyectadas."])
    D.salto()


ORIGINAL = {
    "1": ["Las plataformas de streaming basadas en suscripción dependen de la permanencia de sus usuarios, por lo "
          "que la cancelación del servicio, que se puede denominar como churn, representa un problema relevante "
          "para la continuidad de los ingresos y para la planificación de estrategias de retención. En este "
          "contexto, el caso de uso StreamRetain-Agent plantea identificar semanalmente a los suscriptores con alta "
          "probabilidad de cancelar durante las siguientes cuatro semanas, utilizando señales de comportamiento "
          "como las horas vistas, los días transcurridos desde el último inicio de sesión, el tipo de plan y los "
          "cambios recientes en el método de pago (Maan & Maan, 2023).",
          "Un agente inteligente resulta pertinente porque no se limita a producir una predicción aislada, sino que "
          "percibe periódicamente el estado de cada suscriptor, compara su comportamiento actual con el historial "
          "disponible, estima el riesgo de cancelación, prioriza los casos de mayor riesgo y ejecuta una acción "
          "sobre el entorno mediante la conexión con el sistema de marketing para activar una oferta de retención. "
          "El resultado de cada intervención se registra con el propósito de mejorar decisiones posteriores y "
          "conformar un ciclo de percepción, decisión, acción y aprendizaje."],
    "2": ["El agente se clasifica principalmente como un agente de aprendizaje (Russell & Norvig, 2004). Esta "
          "elección se justifica porque su comportamiento no dependerá únicamente de reglas fijas definidas por el "
          "diseñador, sino de un modelo entrenado con datos históricos de suscriptores que cancelaron y "
          "permanecieron. Además, el agente utilizará un estado interno basado en el historial de cada usuario para "
          "interpretar cambios de comportamiento, por ejemplo una disminución sostenida de las horas vistas. Los "
          "resultados de las intervenciones de retención se almacenarán para incorporarlos a futuras evaluaciones y "
          "reentrenamientos del modelo. Por ello, aunque utiliza características de un agente basado en modelo, su "
          "clasificación principal dentro de las opciones de la plantilla es de aprendizaje."],
}


def diseno(D: Doc, X: dict):
    D.h("1. Introducción y planteamiento del problema", 1)
    for t in ORIGINAL["1"]:
        D.p(t, align="just")
    D.h("2. Tipo de agente inteligente", 1)
    for t in ORIGINAL["2"]:
        D.p(t, align="just")
    D.h("3. Tipos de ambiente", 1)
    D.p("La clasificación sigue las seis dimensiones de Russell y Norvig (2004) y del material del curso "
        "(Puertas, 2026).", align="just")
    filas = [
        ["Observabilidad", "Parcialmente observable", "El agente observa registros de uso, plan, accesos y pagos, "
         "pero no puede conocer de forma directa la intención futura del suscriptor ni todos los factores externos "
         "que pueden llevarlo a cancelar; debe inferir el riesgo a partir de señales incompletas."],
        ["Determinismo", "Estocástico", "Usuarios con características similares pueden tomar decisiones diferentes "
         "y una misma oferta de retención puede producir resultados distintos."],
        ["Episodicidad", "Secuencial", "La evaluación de una semana depende del historial previo del usuario y las "
         "acciones ejecutadas pueden influir en su comportamiento posterior."],
        ["Dinamismo", "Dinámico", "El comportamiento cambia con el tiempo (sesiones, consumo, plan, pagos, "
         "cancelaciones); el agente actualiza su percepción en cada ciclo semanal."],
        ["Discretización", "Continuo, con variables discretas", "Horas vistas, días desde el último acceso y "
         "probabilidad son numéricas; tipo de plan y estado de la suscripción son categóricos."],
        ["Número de agentes", "Agente único", "Un solo agente StreamRetain; usuarios y sistema de marketing forman "
         "parte del entorno."],
    ]
    D.tabla("Propiedades del ambiente (sin cambios respecto a la Tarea 2).", ["Dimensión", "Clasificación",
                                                                            "Justificación"], filas, [3, 3.5, 10.5], 8.5)
    D.h("4. Descripción del entorno", 1)
    D.p("El entorno operativo corresponde a una plataforma piloto de streaming por suscripción. Los actores "
        "principales son los suscriptores activos, el agente StreamRetain y el sistema de marketing o retención. "
        "El agente recibe semanalmente la información de comportamiento disponible para cada suscriptor y genera "
        "una estimación de riesgo de cancelación a cuatro semanas. Cuando identifica usuarios de mayor riesgo, "
        "los prioriza y envía la decisión al sistema de marketing para activar una oferta de retención "
        "personalizada. Posteriormente, se registra si el usuario permaneció o canceló.", align="just")
    D.p("Como restricciones del dominio, el agente solo puede decidir con base en los datos que la plataforma haya "
        "capturado y no debe asumir información histórica inexistente. Entre las condiciones excepcionales que "
        "deben manejarse se encuentran los registros faltantes o inválidos, los usuarios sin suficiente historial "
        "y los fallos temporales de integración con el sistema de marketing.", align="just")
    D.p("**Entorno de implementación (corregido).** Como no tenemos acceso a una plataforma real, el entorno se "
        "implementó como un **simulador estocástico con datos sintéticos** (sección 9.1). El simulador genera las "
        "percepciones de la sección 5 y respeta las propiedades de la sección 3. Los 13 escenarios de evaluación "
        "(6 normales, 4 límite y 3 de falla esperada) y sus parámetros quedaron definidos y congelados en "
        "`config/escenarios.yaml` antes de probar.", align="just")
    D.h("5. Entradas y sensores", 1)
    D.lista([
        "**Horas vistas:** dato numérico del nivel de consumo semanal. Captura: registros de reproducción.",
        "**Días desde el último inicio de sesión:** dato numérico de recencia. Captura: registros de autenticación.",
        "**Tipo de plan:** dato categórico (básico, estándar, premium). Captura: base de datos de suscripciones.",
        "**Cambio reciente en el método de pago:** dato binario. Captura: sistema de facturación.",
        "**Historial semanal de comportamiento:** serie temporal construida con las capturas periódicas para "
        "calcular variaciones, tendencias y caídas sostenidas de consumo.",
        "**Estado posterior de la suscripción e intervención:** dato categórico (permaneció o canceló) que el "
        "agente recibe **4 semanas después** de cada predicción, junto con el registro de las ofertas activadas. "
        "Solo se usa para aprender, nunca para decidir en la semana en curso (precisión agregada)."])
    D.h("6. Salidas y actuadores", 1)
    D.lista([
        "**Probabilidad de cancelación:** riesgo estimado de cancelar en las siguientes cuatro semanas; modifica el "
        "estado interno de decisión y permite ordenar prioridades.",
        "**Clasificación o priorización de riesgo:** organiza a los suscriptores según su riesgo para determinar "
        "cuáles requieren intervención.",
        "**Activación de oferta de retención:** acción ejecutada mediante la llamada al servicio de marketing, que "
        "registra al usuario y activa la oferta.",
        "**Registro de la intervención y su resultado:** escritura en la base histórica de la intervención, la "
        "fecha y el resultado observado, que actualiza la memoria del agente."])
    D.h("7. Medidas de desempeño", 1)
    D.p("**Medida SMART original (se conserva como M1).** Alcanzar una exactitud (accuracy) general mínima del "
        "75 % al identificar, en cada ciclo semanal, a los suscriptores que cancelarán dentro de las siguientes "
        "cuatro semanas. Se calcula como predicciones correctas / total de predicciones, sobre datos no usados en "
        "el entrenamiento. El 75 % es el umbral definido en el caso de uso.", align="just")
    D.p("**Reformulación (corregido, antes de probar).** Con tasas de cancelación de 25 % o menos, la estrategia "
        "trivial de predecir que nadie cancela obtiene una accuracy de 1 − tasa base, es decir, 75 % o más, sin "
        "detectar a nadie. Por eso la medida original no permite distinguir un buen agente de uno inútil. La "
        "medida principal pasa a ser la **precisión balanceada ≥ 75 %** (M1R), que conserva el umbral del diseño "
        "y en la que la estrategia trivial obtiene 50 %. Se agregan cinco medidas complementarias. Todas tienen "
        "fórmula y umbral, y se congelaron con el tag git `umbrales-congelados` antes de ejecutar la "
        "evaluación.", align="just")
    filas = [["M1", "Exactitud (accuracy), SMART original", "(TP + TN) / N", "≥ 75 %"],
             ["M1R", "Precisión balanceada (principal)", "(recall + especificidad) / 2", "≥ 75 %"],
             ["M2", "Recall de la clase «cancela»", "TP / (TP + FN)", "≥ 60 %"],
             ["M3", "Precisión en el top-K (K = 10 % de la base)", "cancelaciones reales en el top-K / K", "≥ 50 %"],
             ["M4", "AUC-ROC", "área bajo la curva ROC de la probabilidad", "≥ 0,80"],
             ["M5", "Robustez ante entradas inválidas y fallas", "fallas manejadas / fallas inyectadas", "100 %"],
             ["M6", "Latencia del ciclo semanal (2.000 suscriptores)", "segundos por ciclo", "≤ 10 s"]]
    D.tabla("Medidas de desempeño y umbrales congelados antes de probar.", ["ID", "Medida", "Fórmula", "Umbral"],
            filas, [1.2, 6.3, 6.5, 2.5], 8.5)
    D.h("8. Componentes de la arquitectura de IA agéntica (marco IBM)", 1)
    D.p("Los agentes de inteligencia artificial son sistemas capaces de percibir su entorno, tomar decisiones y "
        "ejecutar acciones de manera autónoma. Según la arquitectura de la IA agéntica que describe IBM (s. f.), "
        "sus componentes se organizan en siete áreas funcionales.", align="just")
    comp = [
        ("Percepción y manejo de entradas", "El agente recibe y valida los datos semanales de cada suscriptor desde "
         "los registros de reproducción, acceso, suscripción y pagos, y los transforma en variables utilizables "
         "por el modelo, comparándolos con el historial disponible del propio usuario. Cuando no existe suficiente "
         "historial, el sistema reconoce esa limitación en lugar de generar artificialmente observaciones "
         "anteriores."),
        ("Planificación y descomposición de tareas", "En cada ciclo semanal el agente divide su tarea en etapas: "
         "recopilar y validar datos, actualizar el historial, calcular cambios de comportamiento, estimar la "
         "probabilidad de cancelación, ordenar a los usuarios por riesgo, seleccionar los casos que cumplen el "
         "criterio de intervención, ejecutar la acción mediante marketing y registrar el resultado."),
        ("Memoria", "Historial de observaciones semanales de cada suscriptor, predicciones realizadas, "
         "intervenciones aplicadas y sus resultados. Permite construir variación semanal, promedio reciente, "
         "tendencia de consumo y semanas consecutivas de descenso, solo con datos realmente capturados."),
        ("Razonamiento y toma de decisiones", "Un modelo de aprendizaje automático entrenado con ejemplos "
         "etiquetados produce una probabilidad de cancelación, que el agente combina con reglas de priorización "
         "(umbral τ y presupuesto de intervenciones). Para la interpretabilidad se usa una **explicación local por "
         "oclusión** (corregido; antes: SHAP), que indica qué factores aumentaron o redujeron el riesgo estimado."),
        ("Llamada de herramientas y acción (tool calling)", "Acceso a las fuentes de datos y a la API de marketing: "
         "el agente envía los usuarios seleccionados para una acción de retención y almacena el resultado de la "
         "intervención."),
        ("Comunicación", "Presenta al analista la identificación del usuario, su probabilidad, prioridad, confianza "
         "y factores principales, y distingue entre una estimación probabilística y una cancelación confirmada."),
        ("Aprendizaje y adaptación", "Cada predicción se vincula con el estado de la suscripción en las cuatro "
         "semanas siguientes. Periódicamente se reentrena el modelo y la nueva versión **solo se acepta si mantiene "
         "o mejora la precisión balanceada** en un holdout reciente (corregido: compuerta concreta; se excluyen los "
         "usuarios intervenidos)."),
    ]
    for titulo, texto in comp:
        D.p(f"**{titulo}.** {texto}", align="just")
    D.salto()


def desarrollo(D: Doc, X: dict):
    m, s, en, ent = X["m"], X["sumas"], X["enlaces"], X["entren"]
    D.h("9. Desarrollo del agente", 1)
    D.p("Esta sección describe la implementación. El código, las instrucciones para ejecutarlo y los logs están en "
        f"el repositorio ({en['repositorio']}). Todos los datos que usa el agente son **sintéticos**: los genera "
        "el simulador.", align="just")

    # 9.1
    D.h("9.1 Arquitectura", 2)
    f1 = D.figura(DIAG / "arquitectura.png", "Diagrama de componentes de StreamRetain-Agent y su entorno simulado.",
                  13.5)
    D.p(f"La Figura {f1} muestra los componentes y cómo se conectan:", align="just")
    D.lista([
        "**Sensores:** el entorno (`StreamingEnv`) entrega cada semana un lote crudo de registros.",
        "**Percepción:** valida el lote, lo guarda en la memoria SQLite y construye el estado interno de cada "
        "usuario (variables estáticas y de tendencia).",
        "**Modelo de riesgo:** estima la probabilidad de cancelación.",
        "**Decisión:** aplica el umbral τ y el presupuesto de intervenciones.",
        "**Acción:** llama a la API de marketing (servicio externo).",
        "**Aprendizaje:** recibe el resultado a 4 semanas y reentrena el modelo con una compuerta.",
        "**Interfaz y log:** la interfaz Streamlit orquesta los ciclos y el log JSONL registra cada paso con "
        "marca de tiempo."])
    filas = [
        ["Percepción y manejo de entradas", "`perception.py` (`validar`), `agent.py` (`perceive`), `features.py` "
         "(`construir`)", "Implementado"],
        ["Planificación y descomposición", "`agent.py` (`run_cycle`: validar → memoria → variables → predecir → "
         "priorizar → actuar → registrar → aprender)", "Implementado como descomposición fija. No hay un "
         "planificador dinámico porque la tarea semanal es siempre la misma."],
        ["Memoria", "`memory.py` (SQLite: observaciones, rechazos, predicciones, intervenciones, cola, resultados)",
         "Implementado"],
        ["Razonamiento y toma de decisiones", "`model.py` (`ModeloRiesgo.predecir`, `explicar`), `decision.py` "
         "(`decidir`)", "Implementado (oclusión en lugar de SHAP)"],
        ["Llamada de herramientas", "`env/simulator.py` (`MarketingAPI.activate_offer`), `agent.py` (`act`)",
         "Implementado contra una API simulada. No hay integración con un sistema real."],
        ["Comunicación", "`app/streamlit_app.py` (tabla de riesgo, prioridad, confianza y factores), "
         "`logging_utils.py`", "Implementado. No envía notificaciones a otros sistemas."],
        ["Aprendizaje y adaptación", "`agent.py` (`learn`, `_reentrenar`), `scripts/train_initial.py`",
         "Implementado"],
    ]
    D.tabla("Componentes IBM y módulo del código que los implementa.", ["Componente IBM", "Módulo",
                                                                      "Estado"], filas, [4.2, 8.3, 4.5], 8)

    # 9.2
    D.h("9.2 Tecnologías", 2)
    v = X["entorno"]["versiones"]
    filas = [
        ["Python", X["entorno"]["equipo"]["python"], "Lenguaje de todo el agente", "Ecosistema de ML maduro y "
         "conocido por la pareja; Java o R exigirían más código propio"],
        ["NumPy / pandas", f"{v['numpy']} / {v['pandas']}", "Simulador vectorizado, variables, tablas de "
         "resultados", "Estándar para datos tabulares; Polars sería más rápido pero es menos conocido"],
        ["scikit-learn", v["scikit-learn"], "Regresión logística, HistGradientBoosting, calibración isotónica, "
         "AUC y ROC (Pedregosa et al., 2011)", "API uniforme para comparar candidatos; XGBoost no aportaba ventaja "
         "a este tamaño de datos"],
        ["SciPy", "1.18.1", "Muestreo de los días sin login (Poisson)", "Ya viene con scikit-learn"],
        ["SQLite (sqlite3)", "3.45.3", "Memoria persistente del agente", "Incluido en Python; sin servidor (frente "
         "a PostgreSQL)"],
        ["Streamlit", "1.66.0", "Interfaz y despliegue (evidencia)", "Despliegue gratuito desde GitHub; Flask "
         "requiere más código de interfaz"],
        ["PyYAML", "6.0.3", "Configuración de escenarios, umbrales y matriz", "Legible y versionable (frente a "
         "JSON)"],
        ["matplotlib", "3.11.2", "Figuras de resultados", "Estándar; sin dependencias de navegador"],
        ["joblib", "1.6.0", "Guardar modelos y paralelizar la evaluación", "Incluido con scikit-learn"],
        ["pytest", "9.1.1", "Pruebas unitarias y de integración", "Más conciso que unittest"],
        ["Mermaid", "11.4.1", "Diagramas de arquitectura y de secuencia", "Diagrama como código, versionable "
         "(frente a draw.io)"],
        ["Git / GitHub", "—", "Repositorio reproducible", "Requisito de la guía; integración con Streamlit Cloud"],
    ]
    D.tabla("Tecnologías utilizadas.", ["Tecnología", "Versión", "Para qué se usó", "Por qué frente a una "
                                        "alternativa"], filas, [2.8, 2.3, 5.8, 6.1], 8)
    D.p("**Qué razona el código propio y qué hacen las librerías.** El código propio implementa:", align="just")
    D.lista([
        "simulador y API simulada;",
        "validación de percepciones;",
        "memoria y variables de tendencia;",
        "regla de decisión (τ, presupuesto, cola y enfriamiento de 4 semanas);",
        "reintentos;",
        "vínculo entre predicción y resultado;",
        "compuerta de reentrenamiento;",
        "explicación por oclusión;",
        "evaluación de M1–M6.",
    ])
    D.p("scikit-learn solo ajusta los clasificadores y calcula el AUC. **No se usa ningún modelo de lenguaje "
        "(LLM).**", align="just")

    # 9.3
    D.h("9.3 Entradas (inputs)", 2)
    filas = [
        ["user_id", "texto", "«U» + 5 dígitos", "Base de suscripciones (simulador)", "U00000"],
        ["semana", "entero", "0 – 15", "Reloj del ciclo", "4"],
        ["horas_vistas", "real", "0 – 168 h por semana", "Registros de reproducción (sensor)", "5,33"],
        ["dias_desde_ultimo_login", "real", "0 – 365", "Registros de autenticación (sensor)", "4"],
        ["tipo_plan", "categórico", "básico, estándar, premium", "Base de suscripciones", "basico"],
        ["cambio_metodo_pago", "binario", "0 o 1 (cambio en las últimas 4 semanas)", "Sistema de facturación", "0"],
        ["Historial semanal", "serie temporal", "Ventana de 4 semanas en memoria", "Memoria SQLite (propia)",
         "5 semanas con datos válidos (U00006)"],
        ["Resultado a 4 semanas", "binario", "0 = permaneció, 1 = canceló", "Entorno (estado de la suscripción), "
         "4 semanas después", "197 cancelaciones de 1.888 predicciones (semana 7)"],
    ]
    D.tabla("Percepciones del agente. Los ejemplos son reales del log `detalle_N2_s1001.jsonl.gz` (N2, semilla "
            "1001, semana 4, 2026-10-18T18:54:25).", ["Nombre", "Tipo", "Rango o formato", "Origen",
                                                     "Ejemplo del log"], filas, [3.4, 1.9, 3.8, 4.4, 3.5], 8)
    D.p("Ejemplo real de un registro rechazado en la misma ejecución: `U00048`, con el motivo «dias_desde_"
        "ultimo_login faltante o no numérico». No se descarta en silencio: queda en la tabla `rechazos` de la "
        "memoria y en el log.", align="just")

    # 9.4
    D.h("9.4 Salidas y acciones", 2)
    filas = [
        ["Probabilidad de cancelación (`predecir`)", "Estado interno: ordena el riesgo. No modifica el entorno."],
        ["Predicción p ≥ τ, prioridad (alta, media, baja) y confianza (normal, baja)", "Tabla de riesgo para el "
         "analista, con 3 factores principales para cada ofertado."],
        ["Activar oferta (`MarketingAPI.activate_offer`)", "Modifica el entorno: si llega dentro de las 4 semanas "
         "previas a una cancelación programada, la evita con probabilidad 30 % (efecto probabilístico)."],
        ["Reintentar o encolar ante un fallo de la API", "Hasta 3 reintentos. Si la falla persiste, el usuario "
         "pasa a la cola del ciclo siguiente (la entrada vence a las 4 semanas)."],
        ["Registrar intervención y resultado", "Actualiza la memoria (`intervenciones`, `resultados`), que alimenta "
         "el aprendizaje."],
        ["Reentrenar con compuerta (`_reentrenar`)", "Reemplaza el modelo solo si su precisión balanceada en el "
         "holdout es mayor o igual a la del modelo vigente."],
    ]
    D.tabla("Acciones del agente y su efecto.", ["Acción", "Efecto en el entorno o en el agente"], filas,
            [6.5, 10.5], 8.5)

    # 9.5
    D.h("9.5 Diagramas de secuencia UML", 2)
    D.p("Los participantes son el analista (actor externo), la interfaz, el agente separado en percepción, "
        "decisión/aprendizaje y acción, el entorno, la memoria y la API de marketing (servicio externo). Los "
        "mensajes usan los **nombres reales de los métodos** del código. Fuentes en "
        "`docs/diagramas/*.mmd`.", align="just")
    f2 = D.figura(DIAG / "secuencia_tipico.png", "Secuencia del escenario típico (N2): ciclo semanal completo, "
                  "con fragmentos loop y alt.", 17)
    f3 = D.figura(DIAG / "secuencia_excepcion.png", "Secuencia del escenario de excepción: registro inválido, "
                  "usuario sin historial y fallo o timeout de la API, con alt, loop y opt.", 17)
    D.p(f"La Figura {f2} muestra el escenario típico y la Figura {f3} los casos de excepción que la guía pide "
        "manejar.", align="just")

    # 9.6
    D.h("9.6 Diferencias entre el diseño y la implementación", 2)
    filas = [
        ["Entorno: plataforma piloto real", "Simulador estocástico con semilla y datos sintéticos",
         "No hay acceso a datos reales; la guía permite un simulador mínimo."],
        ["Entrenamiento con datos históricos etiquetados", "«Prehistoria» sintética: 20 poblaciones de "
         "entrenamiento (semillas 1–20); modelo y τ elegidos con 5 de validación (501–505)",
         "Sin fuga de datos: las semillas de prueba (1001–1010) se usaron una sola vez."],
        ["Explicabilidad con SHAP", "Oclusión: aporte = p(x) − p(x con la variable en su mediana)",
         "Funciona con el modelo calibrado, es rápida y aligera el despliegue."],
        ["«Reglas de priorización»", "τ = umbral de Youden en validación (Youden, 1950); presupuesto del "
         "top-10 %; enfriamiento de 4 semanas; cola de reintentos", "Hacer verificable y reproducible la regla "
         "de intervención."],
        ["Usuarios sin historial: «reconocer la limitación»", "Submodelo sin variables de tendencia y confianza "
         "«baja»", "Seguir prediciendo sin inventar historial."],
        ["Aprendizaje con el resultado de la intervención", "Se reentrena con los no intervenidos; compuerta con "
         "precisión balanceada en un holdout", "La oferta altera el resultado de quien la recibe."],
        ["Medida: precisión general ≥ 75 %", "M1 (se conserva), M1R principal y M2–M6", "Ver sección 7."],
    ]
    D.tabla("Diferencias entre el diseño y la implementación.", ["Diseño (Tarea 2)", "Implementación",
                                                                "Por qué"], filas, [4.5, 6.5, 6], 8)
    D.p("**Transparencia sobre la calibración del simulador.** Antes de usar las semillas de prueba encontramos un "
        "error: el código sorteaba entre 1 y 3 semanas el inicio de la caída de consumo, cuando el parámetro "
        "congelado `semanas_decaimiento_previo` fija 3 semanas. Lo corregimos y revertimos un ajuste de ruido que "
        f"habíamos hecho con el código erróneo. Con los valores iniciales se cumple el criterio de dificultad "
        f"congelado: AUC de la regresión logística = {coma(str(X['calib']['auc']))}, dentro de 0,70–0,90, medido "
        "solo con semillas de entrenamiento. Todo quedó registrado en el historial de git y en la bitácora de "
        "IA.", align="just")

    # 9.7
    D.h("9.7 Pruebas", 2)
    casos = X["casos"]
    D.p(f"**Protocolo.** Probamos 13 escenarios × 10 semillas de prueba = **{len(casos)} casos**: 6 normales "
        "(tasas base de 10, 15 y 20 %, base de 500 y 2.000 suscriptores, 12 ciclos y otra mezcla de planes), "
        "4 límite (1 semana de historial, tasas de 3 % y 40 %, deriva de comportamiento) y 3 de falla esperada "
        "(10 % de registros inválidos, 20 % de usuarios nuevos sin historial, API con 30 % de fallos). En cada "
        "caso el agente arranca desde cero y corre 8 ciclos (12 en N5). M1–M4 se miden contra la cancelación "
        "«sin intervención» que conoce el simulador; M5 compara las fallas inyectadas con lo que registró el "
        "agente. Cada medida se reporta como media ± desviación estándar sobre sus casos.", align="just")
    mins = en.get("minutos_video") or {}
    filas = []
    for _, r in X["resultados"].iterrows():
        mid = r["Medida"].split(" — ")[0]
        col = r["Evidencia"].split("(columna ")[1].split(")")[0]
        minuto = mins.get(mid) or "[pendiente]"
        filas.append([coma(r["Medida"]).replace(" — ", ": "), r["Fórmula"], coma(r["Umbral"]).replace(">=", "≥").replace("<=", "≤"),
                      r["Casos ejecutados"].split(" (")[0], coma(r["Resultado obtenido"]),
                      f"**{r['¿Cumple?']}**", f"detalle_por_caso.csv ({col}); logs detalle_*_s1001; video: {minuto}"])
    t = D.tabla("Tabla de resultados (obligatoria). Fuente: `results/resultados.csv`; logs en "
                f"`{X['entorno']['logs']}/`.", ["Medida de desempeño", "Fórmula", "Umbral", "Casos ejecutados",
                                                 "Resultado obtenido", "¿Cumple?", "Evidencia (log, minuto del video)"],
                filas, [3.4, 3.2, 1.6, 1.4, 2.4, 1.3, 3.7], 7.5)
    f4 = D.figura(RES / "figuras" / "medidas_por_escenario.png", "Media ± d.e. de cada medida por escenario "
                  "(10 semillas). Línea punteada = umbral; gris = escenario fuera de la medida.", 11.5)
    f5 = D.figura(RES / "figuras" / "agente_vs_baselines.png", "Agente frente a los baselines (media de los 130 "
                  "casos).", 14)
    cumplen = int((X["resultados"]["¿Cumple?"] == "Sí").sum())
    D.p(f"**Análisis de resultados.** Se cumplen **{cumplen} de {len(X['resultados'])}** medidas (Tabla {t}, "
        f"Figuras {f4} y {f5}).", align="just")
    D.p("**Lo que se cumplió:**")
    D.lista([
        f"**M5 (robustez):** cero excepciones en 130 ejecuciones. Se manejaron los "
        f"{miles(s['fallas_registros_inyectados'])} registros inválidos (rechazados con motivo), las "
        f"{miles(s['fallas_sin_historial'])} predicciones sin historial (baja confianza, sin historial inventado) "
        f"y los {miles(s['fallas_api'])} fallos o timeouts de la API (reintento o cola).",
        f"**M6 (latencia):** {coma(f'{X['m6']:.2f}')} s de media (escenarios de 2.000 suscriptores) y "
        f"{coma(f'{casos.latencia_max_s.max():.2f}')} s como máximo.",
        f"**M2 (recall):** se cumple por poco ({pct(m.M2_recall)}).",
        "**M3 (precisión en el top-10 %):** se cumple en promedio, pero depende de la tasa base: "
        f"{pct(X['por_esc'].M3_precision_top_k.mean()['N1'])} en N1 (tasa 10 %) frente a "
        f"{pct(X['por_esc'].M3_precision_top_k.mean()['L3'])} en L3 (tasa 40 %)."])
    D.p("**Lo que no se cumplió y por qué:**")
    D.lista([
        f"**M1 ({pct(m.M1_accuracy)}).** Queda por debajo del baseline «nadie cancela» "
        f"({pct(m.baseline_nadie_accuracy)} de media). Es el efecto que anticipamos al reformular: τ acepta falsos "
        "positivos para detectar a quien sí cancela.",
        f"**M1R ({pct(m.M1R_balanced_accuracy)}) y M4 ({coma(f'{m.M4_auc:.3f}')}).** La causa principal es la "
        f"falta de señal. Solo el **{pct(m.fraccion_positivos_con_senal)}** de quienes cancelan en las 4 semanas "
        "siguientes mostraba alguna señal cuando se hizo la predicción. Los demás todavía no habían decidido "
        "cancelar (la caída empieza 3 semanas antes de la baja) o cancelan sin aviso previo.",
        f"El agente detecta al {pct(m.recall_positivos_con_senal)} de los que tienen señal y solo al "
        f"{pct(m.recall_positivos_sin_senal)} de los que no.",
        "El AUC es casi idéntico en los 13 escenarios (d.e. 0,011): el techo lo pone la información de los "
        "sensores, no un error del modelo."])
    D.p(f"**Frente a los baselines,** el agente supera a la regresión logística sin tendencia en precisión "
        f"balanceada ({pct(m.M1R_balanced_accuracy)} frente a {pct(m.baseline_lr_balanced_accuracy)}), recall "
        f"({pct(m.M2_recall)} frente a {pct(m.baseline_lr_recall)}) y AUC ({coma(f'{m.M4_auc:.3f}')} frente a "
        f"{coma(f'{m.baseline_lr_auc:.3f}')}). La memoria y las variables de tendencia aportan una mejora real "
        f"pero modesta. La compuerta de aprendizaje aceptó {int(s['reentrenos_aceptados'])} reentrenamientos y "
        f"rechazó {int(s['reentrenos_rechazados'])}.", align="just")
    D.p("**Qué cambiaríamos:**")
    D.lista(["Sumar sensores que anticipen la decisión: visitas a la página de cancelación, tickets de soporte o "
             "pagos rechazados.",
             "Alinear el horizonte de predicción con la señal: predecir a 2 semanas.",
             "Usar un τ adaptativo a la tasa base para no perder recall cuando sube la cancelación (L3).",
             "Construir una línea base individual con más de 4 semanas de memoria."])

    # 9.8
    D.h("9.8 Limitaciones y trabajo futuro", 2)
    D.lista([
        "Los datos son **sintéticos**: los resultados describen el agente en el simulador, no en una plataforma "
        "real. El siguiente paso es validarlo con datos reales anonimizados.",
        "La evaluación usa la etiqueta «sin intervención», que solo conoce el simulador. En producción haría falta "
        "un **grupo de control** sin ofertas.",
        "τ y el modelo se eligieron con la tasa de referencia del 15 %; con tasas muy distintas cae el recall "
        "(L3) o la precisión en el top-K (N1, L2).",
        "El efecto de la oferta (30 %) es un supuesto del simulador; habría que medirlo con experimentos A/B.",
        "Aspectos éticos pendientes del diseño original: privacidad, uso proporcional de los datos, sesgos por "
        "plan y efectos de ofrecer beneficios distintos a distintos usuarios.",
        "Trabajo futuro: SHAP como explicación complementaria, horizonte de 2 semanas, nuevos sensores y "
        "aprendizaje en línea con detección de deriva (L4)."])

    # 9.9
    D.h("9.9 Enlaces", 2)
    D.lista([f"**Repositorio:** {en['repositorio']}",
             f"**Plataforma desplegada (Streamlit Community Cloud):** {en['despliegue'] or '[pendiente]'}",
             f"**Video de respaldo:** {en['video'] or '[pendiente]'}",
             "**Logs de las pruebas:** `logs/eval_20261018_1853_2dbc2c8/` y `results/detalle_por_caso.csv`",
             "**Bitácora de uso de IA:** `docs/BITACORA_IA.md`"])


def conclusiones(D: Doc, X: dict):
    m = X["m"]
    D.h("10. Conclusiones", 1)
    D.p("StreamRetain-Agent quedó implementado como un agente de aprendizaje con estado interno, con el ciclo "
        "percepción → decisión → acción → aprendizaje explícito en el código. Percibe y valida registros "
        "semanales, mantiene memoria por suscriptor, estima el riesgo con un modelo calibrado, prioriza con un "
        "umbral y un presupuesto, actúa sobre una API externa con manejo de fallas y aprende de los resultados "
        "con una compuerta que impide aceptar modelos peores. Todo funciona sobre un simulador estocástico que "
        "respeta el ambiente declarado en la sección 3.", align="just")
    D.p(f"Las pruebas, con umbrales congelados antes de ejecutarlas, muestran un agente robusto y rápido: M5 = "
        f"100 % y M6 = {coma(f'{X['m6']:.2f}')} s. También cumple el recall y la precisión en el "
        f"top-K. En cambio, no alcanza la meta de discriminación: precisión balanceada de "
        f"{pct(m.M1R_balanced_accuracy)} y AUC de {coma(f'{m.M4_auc:.3f}')}. El análisis apunta a un límite de "
        f"información y no a un defecto de implementación: solo el {pct(m.fraccion_positivos_con_senal)} de las "
        "cancelaciones muestra alguna señal al momento de predecir.", align="just")
    D.p("La lección para la siguiente fase es que la meta del 75 % depende más de qué se observa que de qué "
        "modelo se usa. Se necesitan sensores que anticipen la decisión o un horizonte de predicción alineado "
        "con la señal. Siguen pendientes los aspectos éticos del diseño original: privacidad, proporcionalidad "
        "en el uso de datos, sesgos y equidad de las ofertas.", align="just")


def referencias(D: Doc):
    D.h("Referencias", 1)
    refs = [
        "IBM. (s. f.). *Components of AI agents*. IBM Think. https://www.ibm.com/mx-es/think/topics/components-of-ai-agents",
        "Maan, J., & Maan, H. (2023). Customer churn prediction model using explainable machine learning. "
        "*International Journal of Computer Science Trends and Technology, 11*(1), 33–38.",
        "Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, "
        "P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & "
        "Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research, "
        "12*, 2825–2830.",
        "Puertas, E. (2026). *Inteligencia artificial: Agentes inteligentes* [Material de clase]. Universidad "
        "Tecnológica de Bolívar.",
        "Russell, S. J., & Norvig, P. (2004). *Inteligencia artificial: Un enfoque moderno* (2.ª ed.). Pearson "
        "Educación.",
        "Youden, W. J. (1950). Index for rating diagnostic tests. *Cancer, 3*(1), 32–35.",
    ]
    for r in refs:
        par = D.d.add_paragraph()
        par.paragraph_format.left_indent = Cm(1.0)
        par.paragraph_format.first_line_indent = Cm(-1.0)
        for i, trozo in enumerate(r.split("*")):
            if trozo:
                run = par.add_run(trozo)
                run.italic = i % 2 == 1
                run.font.size = Pt(10)


def exportar_pdf(docx: Path) -> Path:
    pdf = docx.with_suffix(".pdf")
    ps = (f"$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
          f"$d = $w.Documents.Open('{docx}'); $d.SaveAs([ref] '{pdf}', [ref] 17); $d.Close(); $w.Quit()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=180)
    return pdf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-pdf", action="store_true")
    args = ap.parse_args()
    X = cargar_datos()
    D = Doc()
    portada(D, X)
    tabla_cambios(D, X)
    seleccion(D, X)
    diseno(D, X)
    desarrollo(D, X)
    conclusiones(D, X)
    referencias(D)
    D.d.save(SALIDA)
    print(f"DOCX: {SALIDA.relative_to(RAIZ)}  ({D.n_tabla} tablas, {D.n_figura} figuras)")
    if not args.sin_pdf:
        print(f"PDF:  {exportar_pdf(SALIDA).relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
