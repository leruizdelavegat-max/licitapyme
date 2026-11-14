"""LicitaPYME — convocatorias del Estado para PYMES.

Correr con:  streamlit run app/app.py
"""

import os
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from ai.analizar import analizar  # noqa: E402

DATA = RAIZ / "data" / "convocatorias.parquet"

# La clave se lee de .env (local) o de los secrets de Streamlit Cloud (despliegue).
load_dotenv(RAIZ / ".env")
try:
    if "DEEPSEEK_API_KEY" in st.secrets:
        os.environ["DEEPSEEK_API_KEY"] = st.secrets["DEEPSEEK_API_KEY"]
except Exception:
    pass  # no hay secrets.toml en local: es normal
HAY_IA = bool(os.getenv("DEEPSEEK_API_KEY"))

st.set_page_config(page_title="LicitaPYME", page_icon="📋", layout="wide")


@st.cache_data(show_spinner=False)
def analizar_cache(ocid: str, conv: dict, perfil: str):
    """Guarda en caché cada análisis: la misma convocatoria con el mismo perfil no se paga dos veces."""
    r = analizar(conv, perfil)
    if r is None:
        # Lanzar error en vez de devolver None evita que un fallo quede guardado en caché.
        raise RuntimeError("respuesta inválida del modelo")
    return r.model_dump()


def analizar_seguro(conv: dict, perfil: str):
    try:
        return analizar_cache(conv["ocid"], conv, perfil)
    except Exception as e:
        print(f"[IA] fallo en {conv['ocid']}: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def normalizar(s: str) -> str:
    """Mayúsculas y sin tildes, para que 'útiles' encuentre 'UTILES'."""
    s = unicodedata.normalize("NFKD", s.upper())
    return "".join(c for c in s if not unicodedata.combining(c))


@st.cache_data
def cargar() -> pd.DataFrame:
    df = pd.read_parquet(DATA)
    df["texto_desc"] = df["descripcion"].fillna("").map(normalizar)
    df["texto_rubro"] = (df["rubros_cubso"].fillna("") + " " + df["rubros_unspsc"].fillna("")).map(normalizar)
    return df


def soles(x) -> str:
    return "—" if pd.isna(x) or x == 0 else f"S/ {x:,.0f}"


if not DATA.exists():
    st.error("Faltan los datos. Corre primero `python scripts/preparar_convocatorias.py`.")
    st.stop()

df = cargar()

# ---------------- Perfil de la PYME ----------------
st.sidebar.header("Perfil de tu empresa")
palabras = st.sidebar.text_input(
    "¿Qué vendes? (palabras clave, separadas por coma)",
    value="servicio de limpieza, limpieza de oficinas",
    help="Ej.: útiles de oficina, servicio de limpieza, uniformes, computadoras, alimentos",
)
departamentos = sorted(df["departamento"].dropna().unique())
regiones = st.sidebar.multiselect("Regiones donde puedes atender", departamentos, default=[])
categorias = st.sidebar.multiselect("Tipo", ["Bienes", "Servicios", "Obras"], default=["Bienes", "Servicios"])
monto_max = st.sidebar.number_input("Monto máximo que puedes atender (S/)", min_value=0, value=500_000, step=50_000)
solo_abiertas = st.sidebar.checkbox("Solo convocatorias en estado CONVOCADO", value=True)
descripcion_pyme = st.sidebar.text_area(
    "Describe tu empresa (lo lee la IA)",
    value="Somos una empresa de servicios de limpieza de oficinas y locales en Lima Metropolitana, "
    "con 30 trabajadores en planilla y 4 años de experiencia con clientes privados. "
    "Facturamos unos S/ 1.2 millones al año. Aún no hemos ganado contratos con el Estado.",
    height=120,
)

# ---------------- Filtro ----------------
f = df[df["categoria"].isin(categorias)] if categorias else df
if regiones:
    f = f[f["departamento"].isin(regiones)]
if solo_abiertas:
    f = f[f["estado"] == "CONVOCADO"]
if monto_max:
    f = f[(f["monto_soles"].isna()) | (f["monto_soles"] <= monto_max)]

claves = [normalizar(p.strip()) for p in palabras.split(",") if p.strip()]
if claves:
    # Coincidir en el rubro oficial (CUBSO/UNSPSC) pesa el doble que en la descripción:
    # "limpieza pública" en una obra no es lo mismo que el rubro "artículos de limpieza".
    puntaje = sum(
        2 * f["texto_rubro"].str.contains(c, regex=False) + f["texto_desc"].str.contains(c, regex=False)
        for c in claves
    )
    f = f.assign(coincidencias=puntaje)
    f = f[f["coincidencias"] > 0].sort_values(["coincidencias", "fecha_publicacion"], ascending=[False, False])

# ---------------- Encabezado y KPIs ----------------
st.title("📋 LicitaPYME")
st.caption(
    "Convocatorias reales del SEACE (datos abiertos OCDS del OECE). "
    f"Datos publicados hasta {df['fecha_publicacion'].max():%d/%m/%Y}."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Procesos en la base", f"{len(df):,}")
c2.metric("Oportunidades para ti", f"{len(f):,}")
c3.metric("Monto total", f"S/ {f['monto_soles'].sum() / 1e6:,.1f} M")
c4.metric("Entidades compradoras", f"{f['entidad'].nunique():,}")

if f.empty:
    st.info("No hay convocatorias con ese perfil. Prueba con otras palabras clave o más regiones.")
    st.stop()

# ---------------- Análisis con IA ----------------
st.subheader("🤖 La IA revisa tus oportunidades")
st.caption(
    "La búsqueda por palabras encuentra muchas convocatorias que no te sirven. "
    "La IA lee cada una, la compara con tu empresa y te dice cuáles valen la pena."
)
if not HAY_IA:
    st.warning("Falta la clave DEEPSEEK_API_KEY: el análisis con IA está desactivado.")
else:
    n_max = min(10, len(f))
    n = st.slider("¿Cuántas convocatorias analizar?", 1, max(n_max, 1), min(5, n_max)) if n_max > 1 else 1
    if st.button(f"Analizar las {n} primeras con IA", type="primary"):
        filas = f.head(n).to_dict("records")
        with st.spinner("La IA está leyendo las convocatorias…"):
            with ThreadPoolExecutor(max_workers=5) as ex:
                resultados = list(ex.map(lambda c: analizar_seguro(c, descripcion_pyme), filas))
        st.session_state["analisis"] = [(c, r) for c, r in zip(filas, resultados)]

    for conv, r in sorted(
        st.session_state.get("analisis", []), key=lambda x: -(x[1]["encaje"] if x[1] else -1)
    ):
        if r is None:
            st.error(f"No se pudo analizar: {conv['descripcion'][:80]}…")
            continue
        icono = "🟢" if r["encaje"] >= 70 else ("🟡" if r["encaje"] >= 40 else "🔴")
        with st.expander(f"{icono} {r['encaje']}/100 · {conv['entidad']} · {soles(conv['monto_soles'])}", expanded=r["encaje"] >= 70):
            st.markdown(f"**Qué compran:** {r['resumen']}")
            st.markdown(f"**¿Te conviene?** {r['razon_encaje']}")
            if r["alerta"]:
                st.warning(r["alerta"])
            st.markdown("**Revisa en las bases:**\n" + "\n".join(f"- {x}" for x in r["que_revisar"]))
            if conv.get("url_bases"):
                st.link_button("Ver bases (PDF)", conv["url_bases"])

# ---------------- Tabla ----------------
st.subheader("Todas tus coincidencias")
tabla = f[
    ["fecha_publicacion", "entidad", "departamento", "descripcion", "categoria", "monto_soles", "metodo", "estado", "url_bases"]
].rename(
    columns={
        "fecha_publicacion": "Publicado",
        "entidad": "Entidad",
        "departamento": "Región",
        "descripcion": "Descripción",
        "categoria": "Tipo",
        "monto_soles": "Monto (S/)",
        "metodo": "Procedimiento",
        "estado": "Estado",
        "url_bases": "Bases",
    }
)
st.dataframe(
    tabla,
    hide_index=True,
    width="stretch",
    column_config={
        "Publicado": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Monto (S/)": st.column_config.NumberColumn(format="%,.0f"),
        "Bases": st.column_config.LinkColumn(display_text="PDF"),
        "Descripción": st.column_config.TextColumn(width="large"),
    },
)

# ---------------- Dashboard ----------------
st.subheader("¿Dónde están tus oportunidades?")
g1, g2 = st.columns(2)
por_region = f.groupby("departamento", as_index=False).agg(procesos=("ocid", "count"), monto=("monto_soles", "sum"))
g1.plotly_chart(
    px.bar(por_region.sort_values("procesos"), x="procesos", y="departamento", orientation="h",
           labels={"procesos": "Convocatorias", "departamento": ""}, title="Convocatorias por región"),
    width="stretch",
)
top_ent = f.groupby("entidad", as_index=False).agg(monto=("monto_soles", "sum")).nlargest(10, "monto")
g2.plotly_chart(
    px.bar(top_ent.sort_values("monto"), x="monto", y="entidad", orientation="h",
           labels={"monto": "Monto (S/)", "entidad": ""}, title="Entidades que más compran lo tuyo"),
    width="stretch",
)
