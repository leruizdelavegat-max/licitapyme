"""Arma el paquete de borradores de postulación en Word (.docx)."""

from __future__ import annotations

import io
import re
from datetime import datetime

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import Pt, RGBColor

MARCA = re.compile(r"(\[COMPLETAR[^\]]*\])")
MARINO = RGBColor(0x0B, 0x25, 0x45)


def _parrafo(doc, texto: str, negrita: bool = False, tam: int = 11):
    """Párrafo donde cada [COMPLETAR: ...] queda resaltado en amarillo."""
    p = doc.add_paragraph()
    for trozo in MARCA.split(texto):
        if not trozo:
            continue
        r = p.add_run(trozo)
        r.bold = negrita
        r.font.size = Pt(tam)
        if MARCA.fullmatch(trozo):
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
            r.bold = True
    return p


def _titulo(doc, texto: str, nivel: int = 1):
    h = doc.add_heading(texto, level=nivel)
    for r in h.runs:
        r.font.color.rgb = MARINO
    return h


def _tabla(doc, encabezados: list[str], filas: list[list[str]]):
    t = doc.add_table(rows=1, cols=len(encabezados))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(encabezados):
        t.rows[0].cells[i].text = h
    for fila in filas:
        celdas = t.add_row().cells
        for i, v in enumerate(fila):
            celdas[i].text = ""
            par = celdas[i].paragraphs[0]
            for trozo in MARCA.split(str(v)):
                if not trozo:
                    continue
                r = par.add_run(trozo)
                r.font.size = Pt(9.5)
                if MARCA.fullmatch(trozo):
                    r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    return t


def generar(empresa: str, conv: dict, carta_texto: str, checklist: list[dict], cotizacion: list[dict],
            fuente_checklist: str) -> bytes:
    doc = Document()
    estilo = doc.styles["Normal"]
    estilo.font.name = "Calibri"
    estilo.font.size = Pt(11)

    aviso = doc.add_paragraph()
    r = aviso.add_run("BORRADOR GENERADO CON LICITAPYME — REVISAR Y COMPLETAR ANTES DE PRESENTAR. "
                      "No reemplaza los anexos ni las declaraciones juradas que exigen las bases.")
    r.bold = True
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0xA6, 0x1B, 0x1B)

    _titulo(doc, "Paquete de postulación", 0)
    _parrafo(doc, f"Empresa: {empresa}")
    _parrafo(doc, f"Entidad: {conv.get('entidad')}")
    _parrafo(doc, f"Procedimiento: {conv.get('metodo')} — {conv.get('nomenclatura')}")
    _parrafo(doc, f"Objeto: {conv.get('descripcion')}")
    if conv.get("url_bases"):
        _parrafo(doc, f"Bases oficiales: {conv['url_bases']}", tam=9)
    _parrafo(doc, f"Generado el {datetime.now():%d/%m/%Y %H:%M}", tam=9)

    # 1. Carta
    doc.add_page_break()
    _titulo(doc, "1. Carta de presentación (borrador)")
    for linea in carta_texto.split("\n"):
        _parrafo(doc, linea)

    # 2. Checklist
    doc.add_page_break()
    _titulo(doc, "2. Checklist de documentos y requisitos")
    _parrafo(doc, fuente_checklist, tam=9)
    _tabla(doc, ["", "Requisito", "Tipo", "Obligatorio", "Fuente"],
           [["☑" if c["listo"] else "☐", c["requisito"], c["categoria"], c["obligatorio"], c["fuente"]] for c in checklist])

    # 3. Cotización
    doc.add_page_break()
    _titulo(doc, "3. Borrador de cotización")
    _parrafo(doc, "Completa cantidades y precios según las bases. La referencia histórica es la mediana de "
                  "contrataciones adjudicadas similares (misma categoría CUBSO) en los datos abiertos del SEACE: "
                  "es una guía, no una garantía de precio.", tam=9)
    _tabla(doc, ["Ítem (categoría CUBSO)", "Cantidad", "Precio unitario (S/)", "Total (S/)", "Referencia histórica"],
           [[c["item"], "[COMPLETAR]", "[COMPLETAR]", "[COMPLETAR]", c["referencia"]] for c in cotizacion])
    _parrafo(doc, "")
    _parrafo(doc, "Validez de la oferta: [COMPLETAR: días]   ·   Plazo de entrega o ejecución: [COMPLETAR]   ·   "
                  "Condiciones de pago: según bases")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
