"""Sistema visual de LicitaPYME: paleta, estilos y componentes reutilizables.

La tipografía (Inter), los colores base y los radios están en .streamlit/config.toml.
Aquí van los componentes que Streamlit no trae: indicadores, pastillas de estado y
metadatos, todos con las mismas clases CSS.
"""

from __future__ import annotations

import html

import streamlit as st

MARINO = "#0B2545"
AZUL = "#1D63ED"
TEXTO = "#1B2A3A"
TEXTO_SUAVE = "#5B6B7F"
SUPERFICIE = "#F5F7FA"
BORDE = "#E3E8EF"
VERDE, AMBAR, ROJO, GRIS = "#1F9D55", "#D97706", "#DC2626", "#8A97A8"

ESTADOS = {
    "verde": {"color": VERDE, "fondo": "#E8F6EE", "texto": "#17703F", "etiqueta": "Alta compatibilidad"},
    "amarillo": {"color": AMBAR, "fondo": "#FEF3E2", "texto": "#94540A", "etiqueta": "Revisar condiciones"},
    "rojo": {"color": ROJO, "fondo": "#FDECEC", "texto": "#A61B1B", "etiqueta": "No cumple un requisito clave"},
    "gris": {"color": GRIS, "fondo": "#F1F3F6", "texto": "#4A5868", "etiqueta": "Sin evaluar"},
}

_CSS = f"""
<style>
/* Espaciado general más compacto y ordenado */
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px; }}
h1 {{ color: {MARINO}; letter-spacing: -0.02em; }}
h2, h3 {{ color: {MARINO}; letter-spacing: -0.01em; }}
[data-testid="stCaptionContainer"] p {{ color: {TEXTO_SUAVE}; }}

/* Encabezado de página */
.lp-enc {{ margin: 0 0 1.1rem 0; }}
.lp-enc .lp-sobre {{ font-size: 12px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: {AZUL}; margin-bottom: 4px; }}
.lp-enc h1 {{ font-size: 28px; font-weight: 700; margin: 0; padding: 0; color: {MARINO}; }}
.lp-enc .lp-sub {{ font-size: 15px; color: {TEXTO_SUAVE}; margin-top: 6px; max-width: 860px; line-height: 1.5; }}

/* Indicadores */
.lp-kpi {{ border: 1px solid {BORDE}; border-radius: 10px; padding: 14px 16px; background: #fff; height: 100%; }}
.lp-kpi .lp-et {{ font-size: 13px; color: {TEXTO_SUAVE}; font-weight: 500; }}
.lp-kpi .lp-val {{ font-size: 26px; font-weight: 600; color: {MARINO}; line-height: 1.25; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.lp-kpi .lp-nota {{ font-size: 12px; color: {TEXTO_SUAVE}; margin-top: 2px; }}
.lp-kpi.lp-acento {{ border-left: 3px solid {AZUL}; }}

/* Pastillas de estado */
.lp-pill {{ display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px; border-radius: 999px;
           font-size: 12.5px; font-weight: 600; white-space: nowrap; }}
.lp-pill .lp-punto {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}

/* Metadatos en línea */
.lp-meta {{ display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; color: {TEXTO_SUAVE}; margin-top: 6px; }}
.lp-meta span b {{ color: {TEXTO}; font-weight: 600; }}
.lp-titulo {{ font-size: 15px; font-weight: 600; color: {MARINO}; line-height: 1.35; }}
.lp-desc {{ font-size: 14px; color: {TEXTO}; margin-top: 4px; line-height: 1.45; }}
.lp-aviso {{ font-size: 12.5px; color: {AMBAR}; margin-top: 4px; }}

/* Panel de sección */
.lp-sec {{ display: flex; align-items: baseline; justify-content: space-between; margin: 1.6rem 0 .6rem 0; }}
.lp-sec h3 {{ font-size: 17px; font-weight: 600; margin: 0; color: {MARINO}; }}
.lp-sec .lp-sec-desc {{ font-size: 13px; color: {TEXTO_SUAVE}; }}

/* Pasos del asistente */
.lp-pasos {{ display: flex; gap: 8px; margin: .3rem 0 1.2rem 0; flex-wrap: wrap; }}
.lp-paso {{ flex: 1; min-width: 150px; border-top: 3px solid {BORDE}; padding-top: 8px; font-size: 13px; color: {TEXTO_SUAVE}; }}
.lp-paso.lp-activo {{ border-color: {AZUL}; color: {MARINO}; font-weight: 600; }}
.lp-paso.lp-hecho {{ border-color: {VERDE}; color: {TEXTO}; }}

/* Menú lateral: textos secundarios legibles sobre el azul marino */
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: #A9B8CE; }}
[data-testid="stSidebar"] h3 {{ color: #FFFFFF; letter-spacing: .01em; }}

/* Botones un poco más sobrios */
.stButton button, .stDownloadButton button, .stLinkButton a {{ font-weight: 500; }}

@media (max-width: 640px) {{
  .lp-enc h1 {{ font-size: 23px; }}
  .lp-kpi .lp-val {{ font-size: 22px; }}
}}
</style>
"""


def estilos():
    st.html(_CSS)


def e(texto) -> str:
    return html.escape(str(texto)) if texto is not None else ""


def encabezado(titulo: str, subtitulo: str | None = None, sobre: str | None = None):
    st.html(
        f'<div class="lp-enc">{f"<div class=lp-sobre>{e(sobre)}</div>" if sobre else ""}'
        f"<h1>{e(titulo)}</h1>{f'<div class=lp-sub>{e(subtitulo)}</div>' if subtitulo else ''}</div>"
    )


def seccion(titulo: str, descripcion: str | None = None):
    st.html(f'<div class="lp-sec"><h3>{e(titulo)}</h3><span class="lp-sec-desc">{e(descripcion or "")}</span></div>')


def kpi(contenedor, etiqueta: str, valor, nota: str | None = None, acento: bool = False):
    contenedor.html(
        f'<div class="lp-kpi{" lp-acento" if acento else ""}"><div class="lp-et">{e(etiqueta)}</div>'
        f'<div class="lp-val">{e(valor)}</div>{f"<div class=lp-nota>{e(nota)}</div>" if nota else ""}</div>'
    )


def pastilla(estado: str, texto: str | None = None) -> str:
    s = ESTADOS[estado]
    return (f'<span class="lp-pill" style="background:{s["fondo"]};color:{s["texto"]}">'
            f'<span class="lp-punto" style="background:{s["color"]}"></span>{e(texto or s["etiqueta"])}</span>')


def meta(items: list[tuple[str, str]]) -> str:
    """Lista de (etiqueta, valor) en una línea que se acomoda en pantallas pequeñas."""
    return '<div class="lp-meta">' + "".join(f"<span>{e(k)} <b>{e(v)}</b></span>" for k, v in items) + "</div>"


def pasos(nombres: list[str], actual: int):
    partes = []
    for i, n in enumerate(nombres, start=1):
        clase = "lp-activo" if i == actual else ("lp-hecho" if i < actual else "")
        partes.append(f'<div class="lp-paso {clase}">{i}. {e(n)}</div>')
    st.html('<div class="lp-pasos">' + "".join(partes) + "</div>")
