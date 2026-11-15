"""Mapa de oportunidades: dónde están las convocatorias, con colores según la evaluación."""

from datetime import timedelta

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

import comun

st.title("🗺️ Mapa de oportunidades")
st.caption(
    "Cada punto es una convocatoria ubicada en el **distrito de la entidad compradora** (los datos abiertos no "
    "incluyen el lugar de ejecución). Si el distrito no se puede identificar sin ambigüedad, el punto va en la "
    "capital del departamento con borde punteado. No se inventan coordenadas."
)

p = comun.perfil()
df = comun.enriquecer(comun.cargar_convocatorias(), p)

# ------------------------------------------------------------------ filtros
with st.container(border=True):
    c1, c2, c3 = st.columns([2, 2, 2])
    solo_perfil = c1.toggle("Solo las que coinciden con mi perfil", value=True,
                            help="Usa las palabras clave de tu perfil.")
    solo_abiertas = c2.toggle("Solo en estado CONVOCADO", value=True)
    niveles = c3.multiselect(
        "Nivel de compatibilidad", list(comun.SEMAFORO),
        default=list(comun.SEMAFORO), format_func=lambda k: f"{comun.SEMAFORO[k]['icono']} {comun.SEMAFORO[k]['texto']}",
    )
    c1, c2, c3 = st.columns(3)
    deps = c1.multiselect("Departamento 🔍", comun.DEPARTAMENTOS, format_func=str.title, placeholder="Todo el Perú")
    base_prov = df[df["departamento"].isin(deps)] if deps else df
    provs = c2.multiselect("Provincia 🔍", sorted(base_prov["provincia"].dropna().unique()), format_func=str.title,
                           placeholder="Todas")
    base_dist = base_prov[base_prov["provincia"].isin(provs)] if provs else base_prov
    dists = c3.multiselect("Distrito 🔍", sorted(base_dist["distrito"].dropna().unique()), format_func=str.title,
                           placeholder="Todos")
    c1, c2, c3, c4 = st.columns(4)
    tipos = c1.multiselect("Tipo", comun.TIPOS, default=p["tipos"])
    rubro = c2.text_input("Categoría o rubro contiene", placeholder="Ej.: limpieza, computadoras")
    montos = c3.select_slider(
        "Valor referencial (S/)",
        options=[0, 50_000, 100_000, 400_000, 1_000_000, 5_000_000, 20_000_000, float("inf")],
        value=(0, float("inf")),
        format_func=lambda x: "Sin límite" if x == float("inf") else f"{x / 1e6:g} M" if x >= 1e6 else f"{x / 1e3:g} mil",
    )
    incluir_sin_monto = c4.checkbox("Incluir sin monto publicado", value=True)
    c1, c2 = st.columns(2)
    fmin, fmax = df["fecha_publicacion"].min().date(), df["fecha_publicacion"].max().date()
    rango_pub = c1.date_input("Fecha de publicación", (fmax - timedelta(days=45), fmax), min_value=fmin, max_value=fmax,
                              format="DD/MM/YYYY")
    rango_cons = c2.date_input("Fin de consultas (si está disponible)", (), format="DD/MM/YYYY",
                               help="Única fecha del cronograma que viene en los datos abiertos.")

f = df
if solo_perfil:
    f = f[f["coincidencia"] > 0]
if solo_abiertas:
    f = f[f["estado"] == "CONVOCADO"]
if niveles:
    f = f[f["semaforo"].isin(niveles)]
if deps:
    f = f[f["departamento"].isin(deps)]
if provs:
    f = f[f["provincia"].isin(provs)]
if dists:
    f = f[f["distrito"].isin(dists)]
if tipos:
    f = f[f["categoria"].isin(tipos)]
if rubro:
    clave = comun.normalizar(rubro)
    f = f[f["texto_rubro"].str.contains(clave, regex=False) | f["texto_desc"].str.contains(clave, regex=False)]
lo, hi = montos
en_rango = f["monto_soles"].between(lo, hi)
f = f[en_rango | (f["monto_soles"].isna() & incluir_sin_monto)]
if isinstance(rango_pub, tuple) and len(rango_pub) == 2:
    f = f[f["fecha_publicacion"].dt.date.between(*rango_pub)]
if isinstance(rango_cons, tuple) and len(rango_cons) == 2:
    f = f[f["consultas_fin"].dt.date.between(*rango_cons)]
f = f.dropna(subset=["lat", "lon"])

# ------------------------------------------------------------------ KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Oportunidades en el mapa", f"{len(f):,}")
c2.metric("Departamentos", f"{f['departamento'].nunique()}")
c3.metric("🟢 Alta compatibilidad", f"{int((f['semaforo'] == 'verde').sum())}")
c4.metric("⚪ Sin evaluar", f"{int((f['semaforo'] == 'gris').sum())}")

if f.empty:
    st.info("No hay oportunidades con esos filtros.")
    st.stop()

LIMITE = 2000
if len(f) > LIMITE:
    st.warning(f"Hay {len(f):,} oportunidades: se muestran las {LIMITE:,} más recientes. Usa los filtros para acotar.")
    f = f.sort_values("fecha_publicacion", ascending=False).head(LIMITE)


# ------------------------------------------------------------------ mapa
def icono(color: str, aproximado: bool) -> folium.DivIcon:
    borde = "2px dashed #fff" if aproximado else "2px solid #fff"
    html = (
        f'<div style="width:14px;height:14px;border-radius:50%;background:{color};border:{borde};'
        f'box-shadow:0 0 8px 4px {color}99, 0 0 2px 1px {color};"></div>'
    )
    return folium.DivIcon(html=html, icon_size=(14, 14), icon_anchor=(7, 7))


def ficha(c: dict) -> str:
    sem = comun.SEMAFORO[c["semaforo"]]
    compat = f"{int(c['compatibilidad'])} %" if pd.notna(c["compatibilidad"]) else "Sin evaluar"
    precision = "" if c["precision_geo"] == "distrito" else "<br><i>Ubicación aproximada: solo se conoce el departamento.</i>"
    bases = f'<br><a href="{c["url_bases"]}" target="_blank">📄 Ver bases en el SEACE</a>' if c.get("url_bases") else ""
    return (
        f'<div style="font-family:sans-serif;font-size:12px;width:280px">'
        f'<b>{c["entidad"]}</b><br>'
        f'<span style="color:{sem["color"]}">● {sem["texto"]} · {compat}</span><br><br>'
        f'<b>Objeto:</b> {c["categoria"]} · {c["metodo"]}<br>'
        f'<b>Descripción:</b> {str(c["descripcion"])[:220]}<br>'
        f'<b>Ubicación:</b> {comun.ubicacion_txt(c)}{precision}<br>'
        f'<b>Valor referencial:</b> {comun.soles(c["monto_soles"])}<br>'
        f'<b>Publicado:</b> {comun.fecha(c["fecha_publicacion"])}<br>'
        f'<b>Cronograma:</b> {comun.plazo_txt(c)}{bases}</div>'
    )


m = folium.Map(location=[-9.2, -75.0], zoom_start=5, tiles="OpenStreetMap", control_scale=True, min_zoom=4)
cluster = MarkerCluster(options={"spiderfyOnMaxZoom": True, "showCoverageOnHover": False}).add_to(m)
for c in f.to_dict("records"):
    folium.Marker(
        [c["lat"], c["lon"]],
        icon=icono(comun.SEMAFORO[c["semaforo"]]["color"], c["precision_geo"] != "distrito"),
        popup=folium.Popup(ficha(c), max_width=300),
        tooltip=f"{comun.SEMAFORO[c['semaforo']]['icono']} {c['entidad']}",
    ).add_to(cluster)

lat0, lon0, dom = comun.domicilio_coords(p)
if lat0 is not None:
    folium.Marker([lat0, lon0], tooltip=f"Tu domicilio: {dom.title()}",
                  icon=folium.Icon(color="blue", icon="home", prefix="fa")).add_to(m)

# Centro y zoom: todo el Perú, o el área de los lugares elegidos.
if deps or provs or dists:
    centro = [(f["lat"].min() + f["lat"].max()) / 2, (f["lon"].min() + f["lon"].max()) / 2]
    extension = max(f["lat"].max() - f["lat"].min(), f["lon"].max() - f["lon"].min(), 0.05)
    zoom = int(max(5, min(13, 9 - __import__("math").log2(extension))))
else:
    centro, zoom = [-9.4, -75.0], 5

col_mapa, col_lado = st.columns([3, 1])
with col_mapa:
    salida = st_folium(m, height=620, width=None, center=centro, zoom=zoom,
                       returned_objects=["last_object_clicked"], key="mapa")
with col_lado:
    st.markdown("**Oportunidades por departamento**")
    por_dep = f.groupby("departamento").size().sort_values(ascending=True).rename("Oportunidades").reset_index()
    fig = px.bar(por_dep.tail(15), x="Oportunidades", y="departamento", orientation="h", height=420,
                 labels={"departamento": ""})
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "🟢 alta compatibilidad · 🟡 revisar condiciones · 🔴 no cumple un requisito clave · ⚪ sin evaluar. "
        "Los colores salen de la evaluación con IA, no de la ubicación."
    )

# ------------------------------------------------------------------ detalle del punto elegido
clic = (salida or {}).get("last_object_clicked")
if clic:
    aqui = f[(f["lat"].sub(clic["lat"]).abs() < 1e-6) & (f["lon"].sub(clic["lng"]).abs() < 1e-6)]
    if not aqui.empty:
        st.subheader(f"📍 {len(aqui)} convocatoria(s) en este punto")
        for c in aqui.head(10).to_dict("records"):
            comun.tarjeta(c, clave="mapa")
else:
    st.info("Haz clic en un punto del mapa para ver su ficha y evaluarlo con IA aquí abajo.")
