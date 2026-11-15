"""Análisis del mercado: precios históricos, entidades compradoras y proveedores adjudicados.

Fuente: adjudicaciones de los datos abiertos OCDS del SEACE (desde 2024), a nivel de ítem.
Solo se comparan ítems con la MISMA clasificación CUBSO (catálogo oficial del Estado),
que es el criterio más objetivo disponible de "contratación similar".
"""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import comun

st.title("📊 Análisis del mercado")
st.caption(
    "Contrataciones ya adjudicadas (datos abiertos del SEACE, desde 2024). Te ayudan a estimar precios, "
    "saber quién compra lo que vendes y quién suele ganar. **Los precios pasados no garantizan precios futuros.**"
)

p = comun.perfil()
adj = comun.cargar_adjudicaciones()

# ------------------------------------------------------------------ elegir rubro
with st.container(border=True):
    c1, c2 = st.columns([2, 3])
    busqueda = c1.text_input("Busca tu rubro", value=", ".join(p["palabras_clave"][:2]),
                             help="Palabras separadas por coma. Se buscan en el catálogo CUBSO y en la descripción del ítem.")
    claves = [comun.normalizar(x) for x in busqueda.split(",") if x.strip()]
    if claves:
        mask = np.zeros(len(adj), dtype=bool)
        for k in claves:
            mask |= adj["texto"].str.contains(k, regex=False).to_numpy()
        candidatos = adj[mask]
    else:
        candidatos = adj
    conteo = candidatos["cubso"].value_counts()
    opciones = conteo.index.tolist()[:300]
    elegidos = c2.multiselect(
        "Categorías CUBSO a comparar 🔍", opciones, default=opciones[:2],
        format_func=lambda x: f"{x} ({conteo[x]:,})",
        help="Solo se comparan ítems de la misma categoría del catálogo oficial: así la comparación es razonable.",
    )
    c1, c2 = st.columns(2)
    deps = c1.multiselect("Departamento de la entidad 🔍", comun.DEPARTAMENTOS, format_func=str.title, placeholder="Todo el Perú")
    sin_atipicos = c2.toggle("Excluir valores atípicos", value=True,
                             help="Quita montos extremos (fuera de 3 rangos intercuartílicos en escala logarítmica), "
                                  "por ejemplo contratos que agrupan muchas sedes o años.")

if not elegidos:
    st.info("Elige al menos una categoría CUBSO.")
    st.stop()

d = adj[adj["cubso"].isin(elegidos)]
if deps:
    d = d[d["departamento"].isin(deps)]
n_total = len(d)
if sin_atipicos and len(d) >= 8:
    lg = np.log10(d["monto_item"])
    q1, q3 = lg.quantile([0.25, 0.75])
    d = d[lg.between(q1 - 3 * (q3 - q1), q3 + 3 * (q3 - q1))]
n_excl = n_total - len(d)

if d.empty:
    st.info("No hay adjudicaciones con esos filtros.")
    st.stop()

st.caption(
    f"📅 Periodo analizado: **{d['fecha'].min():%d/%m/%Y} – {d['fecha'].max():%d/%m/%Y}** · "
    f"**{len(d):,} ítems adjudicados** en **{d['ocid'].nunique():,} procesos**"
    + (f" · {n_excl} valores atípicos excluidos" if n_excl else "")
)
if len(d) < 10:
    st.warning("Hay pocas observaciones: toma estas cifras solo como referencia muy general.")

tab_precios, tab_entidades, tab_prov = st.tabs(["💰 Precios históricos", "🏛️ Entidades compradoras", "🏭 Proveedores adjudicados"])

# ------------------------------------------------------------------ precios
with tab_precios:
    q = d["monto_item"].quantile([0.25, 0.5, 0.75])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Monto mediano por ítem", comun.soles(q[0.5]))
    c2.metric("Rango típico: desde (P25)", comun.soles(q[0.25]), help="El 25 % de los ítems se adjudicó por menos de este monto.")
    c3.metric("Rango típico: hasta (P75)", comun.soles(q[0.75]), help="El 75 % de los ítems se adjudicó por menos de este monto.")
    c4.metric("Observaciones", f"{len(d):,}", help=f"{d['entidad'].nunique():,} entidades distintas")
    st.caption(
        "Usamos la **mediana** y el rango P25–P75 en lugar del promedio porque unos pocos contratos muy grandes "
        "distorsionan el promedio. El monto de un ítem depende de su duración, número de sedes y cantidad: "
        "revisa casos parecidos al tuyo en la tabla de abajo."
    )

    g1, g2 = st.columns(2)
    # Histograma sobre log10 del monto: los montos van de miles a millones.
    hist = px.histogram(x=np.log10(d["monto_item"]), nbins=40, title="¿Cuánto se suele pagar?")
    marcas = list(range(int(np.floor(np.log10(d["monto_item"].min()))), int(np.ceil(np.log10(d["monto_item"].max()))) + 1))
    etiqueta = {2: "S/ 100", 3: "S/ 1 mil", 4: "S/ 10 mil", 5: "S/ 100 mil", 6: "S/ 1 M", 7: "S/ 10 M", 8: "S/ 100 M", 9: "S/ 1,000 M"}
    hist.update_xaxes(tickvals=marcas, ticktext=[etiqueta.get(m, f"10^{m}") for m in marcas], title="Monto adjudicado por ítem")
    hist.add_vline(x=np.log10(q[0.5]), line_dash="dash", annotation_text="mediana")
    hist.update_layout(yaxis_title="Ítems", margin=dict(t=40), bargap=0.05)
    g1.plotly_chart(hist, width="stretch")

    tri = d.assign(trimestre=d["fecha"].dt.to_period("Q").astype(str)).groupby("trimestre").agg(
        mediana=("monto_item", "median"), n=("monto_item", "size")).reset_index()
    tri = tri[tri["n"] >= 3]
    lin = px.line(tri, x="trimestre", y="mediana", markers=True, hover_data=["n"],
                  labels={"mediana": "Monto mediano (S/)", "trimestre": ""}, title="Evolución del monto mediano (trimestres con 3+ casos)")
    g2.plotly_chart(lin, width="stretch")

    anual = d.groupby(d["fecha"].dt.year)["monto_item"].agg(["median", "size"])
    anual = anual[anual["size"] >= 5]
    if len(anual) >= 2:
        a0, a1 = anual.index[-2], anual.index[-1]
        var = (anual.loc[a1, "median"] / anual.loc[a0, "median"] - 1) * 100
        st.markdown(
            f"**Variación del monto mediano {a0} → {a1}:** {var:+.0f} % "
            f"({comun.soles(anual.loc[a0, 'median'])} con {anual.loc[a0, 'size']} casos → "
            f"{comun.soles(anual.loc[a1, 'median'])} con {anual.loc[a1, 'size']} casos)."
        )

    unit = d[(d["cantidad"] > 1) & d["unidad"].notna()]
    unit = unit.groupby("unidad")["precio_unitario"].agg(["median", "size"]).query("size >= 5")
    if not unit.empty:
        st.markdown("**Precio unitario mediano por unidad de medida** (solo ítems con cantidad > 1 y 5+ casos)")
        st.dataframe(unit.rename(columns={"median": "Precio unitario mediano (S/)", "size": "Casos"}),
                     width="content", column_config={"Precio unitario mediano (S/)": st.column_config.NumberColumn(format="%,.2f")})

    if d["departamento"].nunique() > 1:
        top_deps = d["departamento"].value_counts().head(10).index
        box = px.box(d[d["departamento"].isin(top_deps)], x="departamento", y="monto_item", log_y=True, points=False,
                     labels={"monto_item": "Monto por ítem (S/, log)", "departamento": ""}, title="Montos por departamento (10 con más casos)")
        st.plotly_chart(box, width="stretch")

    st.markdown("**Contrataciones adjudicadas más recientes**")
    st.dataframe(
        d.sort_values("fecha", ascending=False)[["fecha", "entidad", "departamento", "item", "cantidad", "unidad", "monto_item", "proveedor", "n_postores"]]
        .head(200).rename(columns={"fecha": "Fecha", "entidad": "Entidad", "departamento": "Departamento", "item": "Ítem",
                                   "cantidad": "Cantidad", "unidad": "Unidad", "monto_item": "Monto (S/)",
                                   "proveedor": "Ganador", "n_postores": "Participantes registrados"}),
        hide_index=True, width="stretch",
        column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"), "Monto (S/)": st.column_config.NumberColumn(format="%,.0f")},
    )

# ------------------------------------------------------------------ entidades
with tab_entidades:
    ent = d.groupby("entidad").agg(
        procesos=("ocid", "nunique"), monto_total=("monto_item", "sum"), mediana=("monto_item", "median"),
        proveedores=("ruc_proveedor", "nunique"), departamento=("departamento", "first"),
    ).sort_values(["procesos", "monto_total"], ascending=False).reset_index()
    st.markdown(f"**Entidades que más compran en estas categorías** ({len(ent):,} entidades)")
    st.dataframe(ent.head(30).rename(columns={"entidad": "Entidad", "procesos": "Procesos", "monto_total": "Monto total (S/)",
                                              "mediana": "Monto mediano (S/)", "proveedores": "Proveedores distintos", "departamento": "Departamento"}),
                 hide_index=True, width="stretch",
                 column_config={"Monto total (S/)": st.column_config.NumberColumn(format="%,.0f"),
                                "Monto mediano (S/)": st.column_config.NumberColumn(format="%,.0f")})
    st.caption("Si una entidad cambia mucho de proveedor, es un mercado más abierto para una empresa nueva.")

    st.divider()
    todas = sorted(adj["entidad"].dropna().unique())
    sel = st.selectbox("🔍 Revisar el comportamiento de una entidad", todas,
                       index=todas.index(ent["entidad"].iloc[0]) if len(ent) else 0, placeholder="Escribe el nombre…")
    e = adj[adj["entidad"] == sel]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Procesos adjudicados", f"{e['ocid'].nunique():,}")
    c2.metric("Monto adjudicado", comun.soles(e["monto_item"].sum()))
    c3.metric("Proveedores distintos", f"{e['ruc_proveedor'].nunique():,}")
    c4.metric("Ubicación", str(e["departamento"].iloc[0]).title() if len(e) else "—")
    g1, g2 = st.columns(2)
    qué = e.groupby("cubso")["monto_item"].agg(["sum", "size"]).sort_values("sum", ascending=False).head(10).reset_index()
    g1.plotly_chart(px.bar(qué.iloc[::-1], x="sum", y="cubso", orientation="h", labels={"sum": "Monto (S/)", "cubso": ""},
                           title="¿Qué suele comprar?"), width="stretch")
    mens = e.groupby(e["fecha"].dt.to_period("M").astype(str))["monto_item"].sum().reset_index()
    g2.plotly_chart(px.bar(mens, x="fecha", y="monto_item", labels={"fecha": "", "monto_item": "Monto (S/)"},
                           title="Montos adjudicados por mes"), width="stretch")
    c1, c2 = st.columns(2)
    c1.markdown("**Procedimientos que usa**")
    c1.dataframe(e.groupby("metodo")["ocid"].nunique().sort_values(ascending=False).rename("Procesos"), width="stretch")
    c2.markdown("**Proveedores adjudicados**")
    c2.dataframe(e.groupby("proveedor")["monto_item"].agg(["size", "sum"]).sort_values("sum", ascending=False).head(15)
                 .rename(columns={"size": "Ítems", "sum": "Monto (S/)"}), width="stretch",
                 column_config={"Monto (S/)": st.column_config.NumberColumn(format="%,.0f")})
    abiertas = comun.cargar_convocatorias()
    abiertas = abiertas[(abiertas["entidad"] == sel) & (abiertas["estado"] == "CONVOCADO")]
    if not abiertas.empty:
        st.markdown(f"**Esta entidad tiene {len(abiertas)} convocatoria(s) abiertas en el último corte:**")
        for c in comun.enriquecer(abiertas, p).head(5).to_dict("records"):
            comun.tarjeta(c, clave="mercado")

# ------------------------------------------------------------------ proveedores
with tab_prov:
    st.info(
        "Estos son **proveedores que ganaron contratos en las mismas categorías**. Que aparezcan aquí no significa "
        "que sean tu competencia directa: pueden atender otras regiones, tamaños o tipos de cliente."
    )

    def mostrar_nombre(ruc: str, nombre: str) -> str:
        # RUC 10 = persona natural con negocio: no destacamos su nombre.
        return f"Persona natural (RUC 10•••••{ruc[-3:]})" if ruc.startswith("10") else nombre

    prov = d.groupby("ruc_proveedor").agg(
        nombre=("proveedor", lambda s: s.mode().iat[0]), procesos=("ocid", "nunique"), monto=("monto_item", "sum"),
        entidades=("entidad", "nunique"), departamentos=("departamento", lambda s: ", ".join(sorted(s.dropna().str.title().unique())[:4])),
    ).sort_values(["procesos", "monto"], ascending=False).reset_index()
    prov["nombre"] = [mostrar_nombre(r, n) for r, n in zip(prov["ruc_proveedor"], prov["nombre"])]
    total = prov["monto"].sum()
    prov["participacion"] = prov["monto"] / total * 100 if total else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Proveedores adjudicados", f"{len(prov):,}")
    top5 = prov.nlargest(5, "monto")["participacion"].sum()
    c2.metric("Concentración: 5 mayores", f"{top5:.0f} % del monto")
    c3.metric("Participantes registrados por proceso (mediana)",
              f"{d.drop_duplicates('ocid')['n_postores'].median():.0f}" if d["n_postores"].notna().any() else "Sin dato",
              help="Empresas que se registraron como participantes en el SEACE. No todas presentan oferta: "
                   "el dato de ofertas presentadas no viene en los datos abiertos.")
    st.caption("Si pocos proveedores concentran casi todo el monto, el mercado es más difícil de entrar.")
    st.dataframe(
        prov.head(40)[["nombre", "procesos", "monto", "participacion", "entidades", "departamentos"]].rename(columns={
            "nombre": "Proveedor", "procesos": "Procesos ganados", "monto": "Monto (S/)", "participacion": "% del monto",
            "entidades": "Entidades", "departamentos": "Departamentos"}),
        hide_index=True, width="stretch",
        column_config={"Monto (S/)": st.column_config.NumberColumn(format="%,.0f"),
                       "% del monto": st.column_config.ProgressColumn(format="%.1f %%", min_value=0, max_value=100)},
    )
