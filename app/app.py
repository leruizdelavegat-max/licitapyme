"""LicitaPYME — oportunidades de contratación pública para MYPES.

Correr con:  streamlit run app/app.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun  # noqa: E402

st.set_page_config(page_title="LicitaPYME", page_icon="📋", layout="wide")

if not comun.DATA_CONV.exists():
    st.error("Faltan los datos. Corre primero `python scripts/preparar_convocatorias.py`.")
    st.stop()

P = Path(__file__).resolve().parent / "paginas"
paginas = {
    "": [
        st.Page(P / "inicio.py", title="Inicio", icon="🏠", default=True),
        st.Page(P / "mapa.py", title="Mapa de oportunidades", icon="🗺️"),
        st.Page(P / "buscar.py", title="Buscar convocatorias", icon="🔎"),
        st.Page(P / "mis_oportunidades.py", title="Mis oportunidades", icon="⭐"),
        st.Page(P / "mercado.py", title="Análisis del mercado", icon="📊"),
        st.Page(P / "perfil.py", title="Perfil de mi empresa", icon="🏢"),
    ]
}
nav = st.navigation(paginas, position="sidebar")

# ------------------------------------------------------------------ barra lateral común
with st.sidebar:
    p = comun.perfil()
    st.markdown("### 📋 LicitaPYME")
    st.caption(f"🏢 {p['nombre']}")
    corte = comun.fecha_corte()
    st.toggle(
        "Calcular plazos con la fecha de hoy",
        key="usar_hoy",
        help="Por defecto los plazos se calculan respecto al último corte de los datos abiertos, "
        "para que la demostración sea coherente con los datos disponibles.",
    )
    ref = comun.fecha_referencia()
    st.caption(
        f"📅 Datos abiertos del SEACE (OECE) con corte al **{corte:%d/%m/%Y}**. "
        f"Plazos calculados al **{ref:%d/%m/%Y}**."
    )
    n_ev, n_g = len(comun.evaluaciones()), len(comun.guardadas())
    st.caption(f"🤖 {n_ev} evaluadas con IA · ⭐ {n_g} guardadas")

nav.run()
