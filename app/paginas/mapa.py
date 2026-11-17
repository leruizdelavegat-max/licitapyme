"""Mapa de oportunidades: dónde están las convocatorias, con colores según la evaluación."""

import math
from datetime import timedelta

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

import comun
import ui

p = comun.perfil()
ui.encabezado(
    "Mapa de oportunidades",
    "Cada punto es una convocatoria ubicada en el distrito de la entidad compradora (los datos abiertos no incluyen "
    "el lugar de ejecución). Si el distrito es ambiguo, el punto va en la capital del departamento con borde "
    "punteado. No se inventan coordenadas.",
    sobre=p["nombre"],
)

panel, zona_mapa = st.columns([1, 3], gap="medium")

# ------------------------------------------------------------------ panel de filtros
with panel:
    with st.container(border=True):
        st.markdown("**Filtros**")
        palabras = comun.selector_palabras(st, "palabras_mapa")
        df = comun.enriquecer(comun.cargar_convocatorias(), {**p, "palabras_clave": palabras})
        solo_abiertas = st.toggle("Solo CONVOCADO", value=True, help="Procesos abiertos en el último corte de datos.")
        niveles = st.pills("Compatibilidad", list(ui.ESTADOS), selection_mode="multi",
                           default=["verde", "amarillo", "gris"],
                           help="Por defecto se ocultan las que la IA descartó. Activa 'No cumple' para verlas.",
                           format_func=lambda k: {"verde": "Alta", "amarillo": "Revisar", "rojo": "No cumple",
                                                  "gris": "Sin evaluar"}[k])
        tipos = st.multiselect("Tipo", comun.TIPOS, default=p["tipos"], placeholder="Todos")
        deps = st.multiselect("Departamento", comun.DEPARTAMENTOS, format_func=str.title, placeholder="Todo el Perú")
        base_prov = df[df["departamento"].isin(deps)] if deps else df
        provs = st.multiselect("Provincia", sorted(base_prov["provincia"].dropna().unique()), format_func=str.title,
                               placeholder="Todas")
        base_dist = base_prov[base_prov["provincia"].isin(provs)] if provs else base_prov
        dists = st.multiselect("Distrito", sorted(base_dist["distrito"].dropna().unique()), format_func=str.title,
                               placeholder="Todos")
        with st.expander("Más filtros"):
            rubro = st.text_input("Categoría o rubro contiene", placeholder="Ej.: limpieza, computadoras")
            montos = st.select_slider(
                "Valor referencial (S/)",
                options=[0, 50_000, 100_000, 400_000, 1_000_000, 5_000_000, 20_000_000, float("inf")],
                value=(0, float("inf")),
                format_func=lambda x: "Sin límite" if x == float("inf") else f"{x / 1e6:g} M" if x >= 1e6 else f"{x / 1e3:g} mil",
            )
            incluir_sin_monto = st.checkbox("Incluir sin monto publicado", value=True)
            fmin, fmax = df["fecha_publicacion"].min().date(), df["fecha_publicacion"].max().date()
            rango_pub = st.date_input("Fecha de publicación", (fmax - timedelta(days=45), fmax), min_value=fmin,
                                      max_value=fmax, format="DD/MM/YYYY")
            rango_cons = st.date_input("Fin de consultas", (), format="DD/MM/YYYY",
                                       help="Única fecha del cronograma que viene en los datos abiertos.")

# Se aplican los filtros uno por uno y se anota cuántas quedan después de cada uno,
# para poder explicar qué filtro dejó el mapa vacío.
lo, hi = montos
clave_rubro = comun.normalizar(rubro) if rubro else ""
pasos = [
    ("Palabras clave", bool(palabras or p.get("categorias")), lambda d: d[d["coincidencia"] > 0]),
    ("Solo CONVOCADO", solo_abiertas, lambda d: d[d["estado"] == "CONVOCADO"]),
    ("Tipo", bool(tipos), lambda d: d[d["categoria"].isin(tipos)]),
    ("Compatibilidad", bool(niveles), lambda d: d[d["semaforo"].isin(niveles)]),
    ("Departamento", bool(deps), lambda d: d[d["departamento"].isin(deps)]),
    ("Provincia", bool(provs), lambda d: d[d["provincia"].isin(provs)]),
    ("Distrito", bool(dists), lambda d: d[d["distrito"].isin(dists)]),
    ("Categoría o rubro", bool(clave_rubro), lambda d: d[comun.contiene(d["texto_rubro"], clave_rubro)
                                                       | comun.contiene(d["texto_desc"], clave_rubro)]),
    ("Valor referencial", True, lambda d: d[d["monto_soles"].between(lo, hi) | (d["monto_soles"].isna() & incluir_sin_monto)]),
    ("Fecha de publicación", isinstance(rango_pub, tuple) and len(rango_pub) == 2,
     lambda d: d[d["fecha_publicacion"].dt.date.between(*rango_pub)]),
    ("Fin de consultas", isinstance(rango_cons, tuple) and len(rango_cons) == 2,
     lambda d: d[d["consultas_fin"].dt.date.between(*rango_cons)]),
]
f, vacio_por = df, None
for nombre, activo, filtro in pasos:
    if not activo:
        continue
    antes = len(f)
    f = filtro(f)
    if antes and f.empty and vacio_por is None:
        vacio_por = (nombre, antes)
f = f.dropna(subset=["lat", "lon"])

with zona_mapa:
    k = st.columns(4)
    ui.kpi(k[0], "Oportunidades en el mapa", f"{len(f):,}", acento=True)
    ui.kpi(k[1], "Departamentos", f"{f['departamento'].nunique()}")
    ui.kpi(k[2], "Alta compatibilidad", f"{int((f['semaforo'] == 'verde').sum())}")
    ui.kpi(k[3], "Sin evaluar", f"{int((f['semaforo'] == 'gris').sum())}")

    if f.empty:
        if vacio_por:
            nombre, antes = vacio_por
            st.warning(f"Había **{antes}** oportunidades hasta que se aplicó el filtro **{nombre}**, que las dejó en 0. "
                       "Ajusta ese filtro para verlas en el mapa.", icon=":material/filter_alt_off:")
        else:
            st.info("Ninguna convocatoria coincide con lo que buscas. Prueba con otras palabras clave.", icon=":material/search_off:")
        st.stop()

    LIMITE = 2000
    if len(f) > LIMITE:
        st.warning(f"Hay {len(f):,} oportunidades: se muestran las {LIMITE:,} más recientes. Usa los filtros para acotar.")
        f = f.sort_values("fecha_publicacion", ascending=False).head(LIMITE)

    def icono(color: str, aproximado: bool) -> folium.DivIcon:
        borde = "2px dashed #fff" if aproximado else "2px solid #fff"
        html = (f'<div style="width:14px;height:14px;border-radius:50%;background:{color};border:{borde};'
                f'box-shadow:0 0 8px 4px {color}88, 0 0 2px 1px {color};"></div>')
        return folium.DivIcon(html=html, icon_size=(14, 14), icon_anchor=(7, 7))

    def ficha(c: dict) -> str:
        s = ui.ESTADOS[c["semaforo"]]
        compat = f"{int(c['compatibilidad'])} %" if pd.notna(c["compatibilidad"]) else "sin evaluar"
        precision = "" if c["precision_geo"] == "distrito" else "<br><i>Ubicación aproximada: solo se conoce el departamento.</i>"
        bases = f'<br><a href="{c["url_bases"]}" target="_blank">Ver bases en el SEACE</a>' if c.get("url_bases") else ""
        return (
            f'<div style="font-family:Inter,sans-serif;font-size:12px;width:290px;color:{ui.TEXTO}">'
            f'<div style="font-weight:600;color:{ui.MARINO};font-size:13px">{ui.e(c["entidad"])}</div>'
            f'<div style="margin:4px 0 8px 0"><span style="background:{s["fondo"]};color:{s["texto"]};padding:1px 8px;'
            f'border-radius:999px;font-weight:600">{s["etiqueta"]} · {compat}</span></div>'
            f'<b>Objeto:</b> {ui.e(c["categoria"])} · {ui.e(c["metodo"])}<br>'
            f'<b>Descripción:</b> {ui.e(str(c["descripcion"])[:220])}<br>'
            f'<b>Ubicación:</b> {ui.e(comun.ubicacion_txt(c))}{precision}<br>'
            f'<b>Valor referencial:</b> {comun.soles(c["monto_soles"])}<br>'
            f'<b>Publicado:</b> {comun.fecha(c["fecha_publicacion"])}<br>'
            f'<b>Cronograma:</b> {comun.plazo_txt(c)}{bases}</div>'
        )

    m = folium.Map(location=[-9.2, -75.0], zoom_start=5, tiles="OpenStreetMap", control_scale=True, min_zoom=4)
    # Mapa base en grises para que los puntos de color destaquen.
    m.get_root().header.add_child(folium.Element(
        "<style>.leaflet-tile-pane{filter:grayscale(1) brightness(1.04) contrast(.92);}</style>"))
    cluster = MarkerCluster(options={"spiderfyOnMaxZoom": True, "showCoverageOnHover": False}).add_to(m)
    for c in f.to_dict("records"):
        folium.Marker(
            [c["lat"], c["lon"]],
            icon=icono(ui.ESTADOS[c["semaforo"]]["color"], c["precision_geo"] != "distrito"),
            popup=folium.Popup(ficha(c), max_width=310),
            tooltip=c["entidad"],
        ).add_to(cluster)

    lat0, lon0, dom = comun.domicilio_coords(p)
    if lat0 is not None:
        folium.Marker([lat0, lon0], tooltip=f"Tu domicilio: {dom.title()}",
                      icon=folium.Icon(color="darkblue", icon="home", prefix="fa")).add_to(m)

    # Centro y zoom: todo el Perú, o el área de los lugares elegidos.
    if deps or provs or dists:
        centro = [(f["lat"].min() + f["lat"].max()) / 2, (f["lon"].min() + f["lon"].max()) / 2]
        extension = max(f["lat"].max() - f["lat"].min(), f["lon"].max() - f["lon"].min(), 0.05)
        zoom = int(max(5, min(13, 9 - math.log2(extension))))
    else:
        centro, zoom = [-9.4, -75.0], 5

    salida = st_folium(m, height=600, width=None, center=centro, zoom=zoom,
                       returned_objects=["last_object_clicked"], key="mapa")
    st.html(
        '<div class="lp-meta">'
        + "".join(f'<span><span class="lp-punto" style="display:inline-block;width:9px;height:9px;border-radius:50%;'
                  f'background:{v["color"]};margin-right:5px"></span>{v["etiqueta"]}</span>' for v in ui.ESTADOS.values())
        + "<span>Los colores salen de la evaluación con IA, no de la ubicación.</span></div>"
    )

with panel:
    st.markdown("**Oportunidades por departamento**")
    por_dep = f.groupby("departamento").size().sort_values().tail(12).rename("n").reset_index()
    fig = px.bar(por_dep, x="n", y="departamento", orientation="h", height=max(180, 26 * len(por_dep)),
                 labels={"n": "", "departamento": ""})
    fig.update_traces(marker_color=ui.AZUL)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

# ------------------------------------------------------------------ detalle del punto elegido
clic = (salida or {}).get("last_object_clicked")
if clic:
    aqui = f[(f["lat"].sub(clic["lat"]).abs() < 1e-6) & (f["lon"].sub(clic["lng"]).abs() < 1e-6)]
    if not aqui.empty:
        ui.seccion(f"{len(aqui)} convocatoria(s) en el punto seleccionado")
        for c in aqui.head(10).to_dict("records"):
            comun.tarjeta(c, clave="mapa")
else:
    st.caption("Haz clic en un punto del mapa para ver su ficha y, debajo, evaluarlo con IA o guardarlo.")
