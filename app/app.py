"""LicitaPYME — convocatorias del Estado para PYMES.

Correr con:  streamlit run app/app.py
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).resolve().parent.parent / "data" / "convocatorias.parquet"

st.set_page_config(page_title="LicitaPYME", page_icon="📋", layout="wide")


@st.cache_data
def cargar() -> pd.DataFrame:
    df = pd.read_parquet(DATA)
    df["texto"] = (
        df["descripcion"].fillna("") + " " + df["rubros_cubso"].fillna("") + " " + df["rubros_unspsc"].fillna("")
    ).str.upper()
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
    value="útiles de oficina, papel, tóner",
    help="Ej.: útiles de oficina, limpieza, uniformes, computadoras, alimentos",
)
departamentos = sorted(df["departamento"].dropna().unique())
regiones = st.sidebar.multiselect("Regiones donde puedes atender", departamentos, default=[])
categorias = st.sidebar.multiselect("Tipo", ["Bienes", "Servicios", "Obras"], default=["Bienes", "Servicios"])
monto_max = st.sidebar.number_input("Monto máximo que puedes atender (S/)", min_value=0, value=500_000, step=50_000)
solo_abiertas = st.sidebar.checkbox("Solo convocatorias en estado CONVOCADO", value=True)

# ---------------- Filtro ----------------
f = df[df["categoria"].isin(categorias)] if categorias else df
if regiones:
    f = f[f["departamento"].isin(regiones)]
if solo_abiertas:
    f = f[f["estado"] == "CONVOCADO"]
if monto_max:
    f = f[(f["monto_soles"].isna()) | (f["monto_soles"] <= monto_max)]

claves = [p.strip().upper() for p in palabras.split(",") if p.strip()]
if claves:
    coincide = pd.concat([f["texto"].str.contains(c, regex=False) for c in claves], axis=1)
    f = f.assign(coincidencias=coincide.sum(axis=1))
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
c3.metric("Monto total", soles(f["monto_soles"].sum()))
c4.metric("Entidades compradoras", f"{f['entidad'].nunique():,}")

if f.empty:
    st.info("No hay convocatorias con ese perfil. Prueba con otras palabras clave o más regiones.")
    st.stop()

# ---------------- Tabla ----------------
st.subheader("Tus oportunidades")
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
    use_container_width=True,
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
    use_container_width=True,
)
top_ent = f.groupby("entidad", as_index=False).agg(monto=("monto_soles", "sum")).nlargest(10, "monto")
g2.plotly_chart(
    px.bar(top_ent.sort_values("monto"), x="monto", y="entidad", orientation="h",
           labels={"monto": "Monto (S/)", "entidad": ""}, title="Entidades que más compran lo tuyo"),
    use_container_width=True,
)
