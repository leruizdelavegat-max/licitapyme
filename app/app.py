"""LicitaPYME — oportunidades de contratación pública para MYPES.

Correr con:  streamlit run app/app.py

Flujo según el estado del usuario:
- Sin sesión (solo en la nube con login): pantalla de acceso.
- Sin empresa o con perfil incompleto: configuración inicial (paso a paso).
- Con perfil confirmado: dashboard y todas las secciones.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun  # noqa: E402
import db  # noqa: E402
import sesion  # noqa: E402
import ui  # noqa: E402

st.set_page_config(page_title="LicitaPYME", page_icon=":material/account_balance:", layout="wide")
ui.estilos()
sesion.limpiar_cache()  # cada ejecución lee el estado fresco de la base

if not comun.DATA_CONV.exists():
    st.error("Faltan los datos. Corre primero `python scripts/preparar_convocatorias.py`.")
    st.stop()

P = Path(__file__).resolve().parent / "paginas"


def pantalla_acceso():
    ui.encabezado(
        "Oportunidades del Estado para tu empresa",
        "LicitaPYME lee las convocatorias públicas del SEACE, evalúa con IA cuáles son compatibles con tu MYPE "
        "y te dice cuánto se suele pagar y quién suele ganar.",
        sobre="LicitaPYME",
    )
    c1, c2, _ = st.columns([1.3, 1.6, 2])
    if c1.button("Ingresar con Google", type="primary", icon=":material/login:", width="stretch"):
        auth = st.secrets.get("auth", {})
        st.login("google") if "google" in auth else st.login()
    if c2.button("Explorar con una empresa de ejemplo", icon=":material/visibility:", width="stretch"):
        sesion.iniciar_demo(comun.PERFIL_DEMO)
        st.rerun()
    st.caption("Al ingresar, tus empresas, oportunidades guardadas e historial se conservan para tu próxima visita. "
               "El modo de ejemplo no requiere registro.")


uid = sesion.usuario_id()
if uid is None:
    st.navigation([st.Page(pantalla_acceso, title="Ingresar", icon=":material/login:")], position="hidden").run()
    st.stop()

emp = sesion.empresa_actual()
confirmada = emp is not None and emp["estado"] == "confirmado"

if confirmada:
    paginas = [
        st.Page(P / "inicio.py", title="Inicio", icon=":material/dashboard:", default=True),
        st.Page(P / "mapa.py", title="Mapa de oportunidades", icon=":material/map:"),
        st.Page(P / "buscar.py", title="Buscar convocatorias", icon=":material/search:"),
        st.Page(P / "mis_oportunidades.py", title="Mis oportunidades", icon=":material/bookmarks:"),
        st.Page(P / "mercado.py", title="Análisis del mercado", icon=":material/monitoring:"),
        st.Page(P / "perfil.py", title="Perfil de mi empresa", icon=":material/domain:"),
    ]
else:
    paginas = [st.Page(P / "configurar.py", title="Configurar mi empresa", icon=":material/domain_add:", default=True)]
nav = st.navigation(paginas, position="sidebar")

# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.markdown("### LicitaPYME")
    lista = sesion.empresas()
    if len(lista) > 1:
        ids = [e["id"] for e in lista]
        nombres = {e["id"]: e["nombre"] + ("" if e["estado"] == "confirmado" else " (sin terminar)") for e in lista}
        elegida = st.selectbox("Empresa", ids, index=ids.index(emp["id"]) if emp else 0,
                               format_func=nombres.get, key="selector_empresa")
        if emp and elegida != emp["id"]:
            sesion.cambiar_empresa(elegida)
            st.rerun()
    elif emp:
        st.caption(emp["nombre"])
    if confirmada and st.button("Registrar otra empresa", icon=":material/add_business:", width="stretch"):
        sesion.nueva_empresa(comun.PERFIL_VACIO)
        st.rerun()

    st.divider()
    if confirmada:
        st.toggle("Calcular plazos con la fecha de hoy", key="usar_hoy",
                  help="Por defecto los plazos se calculan respecto al último corte de los datos abiertos, "
                       "para que la demostración sea coherente con los datos disponibles.")
        st.caption(f"Datos abiertos del SEACE (OECE) con corte al **{comun.fecha_corte():%d/%m/%Y}**.")

    if sesion.es_demo():
        st.caption("Estás en el modo de ejemplo.")
        if st.button("Salir del ejemplo", icon=":material/logout:"):
            sesion.salir_demo()
            st.rerun()
    elif sesion.auth_configurado():
        st.caption(f"Sesión: {st.user.email}")
        if st.button("Cerrar sesión", icon=":material/logout:"):
            st.logout()
    else:
        st.caption("Modo local: los datos se guardan en este equipo"
                   + (" (base en la nube)." if db.es_nube() else "."))

nav.run()
