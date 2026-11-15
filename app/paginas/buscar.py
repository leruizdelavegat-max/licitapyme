"""Buscar convocatorias: filtros avanzados, tarjetas y evaluación con IA."""

import io

import pandas as pd
import streamlit as st

import comun

st.title("🔎 Buscar convocatorias")
p = comun.perfil()
df = comun.cargar_convocatorias()

# ------------------------------------------------------------------ filtros
with st.container(border=True):
    c1, c2 = st.columns([3, 2])
    palabras = c1.multiselect(
        "¿Qué buscas? 🔍",
        options=sorted(set(p["palabras_clave"])),
        default=p["palabras_clave"],
        accept_new_options=True,
        help="Viene de tu perfil. Escribe otra palabra y presiona Enter para agregarla.",
    )
    deps = c2.multiselect(
        "Departamento de la entidad 🔍", comun.DEPARTAMENTOS, format_func=str.title,
        placeholder="Todos (tu cobertura aparece primero)",
    )
    c1, c2, c3, c4 = st.columns(4)
    tipos = c1.multiselect("Tipo", comun.TIPOS, default=p["tipos"])
    estados = c2.multiselect(
        "Estado del proceso", sorted(df["estado"].dropna().unique()), default=["CONVOCADO"],
        help="CONVOCADO = proceso abierto en el último corte de datos.",
    )
    monto_max = c3.number_input("Monto máximo (S/)", 0, 1_000_000_000, 0, step=100_000,
                                help="0 = sin límite. Incluye las que no publican monto.")
    orden = c4.selectbox("Ordenar por", ["Relevancia", "Compatibilidad IA", "Más recientes", "Mayor monto", "Cierre de consultas"])

f = comun.enriquecer(df, {**p, "palabras_clave": palabras})
if tipos:
    f = f[f["categoria"].isin(tipos)]
if estados:
    f = f[f["estado"].isin(estados)]
if deps:
    f = f[f["departamento"].isin(deps)]
if monto_max:
    f = f[f["monto_soles"].isna() | (f["monto_soles"] <= monto_max)]
if palabras:
    f = f[f["coincidencia"] > 0]

orden_cols = {
    "Relevancia": (["en_cobertura", "coincidencia", "fecha_publicacion"], [False, False, False]),
    "Compatibilidad IA": (["compatibilidad", "coincidencia"], [False, False]),
    "Más recientes": (["fecha_publicacion"], [False]),
    "Mayor monto": (["monto_soles"], [False]),
    "Cierre de consultas": (["consultas_fin"], [True]),
}
cols, asc = orden_cols[orden]
f = f.sort_values(cols, ascending=asc, na_position="last")

# ------------------------------------------------------------------ resumen
c1, c2, c3, c4 = st.columns(4)
c1.metric("Convocatorias encontradas", f"{len(f):,}")
c2.metric("En tu cobertura", f"{int(f['en_cobertura'].sum()):,}")
c3.metric("Entidades", f"{f['entidad'].nunique():,}")
c4.metric("Valor referencial publicado", comun.soles(f["monto_soles"].sum()))

if f.empty:
    st.info("No hay convocatorias con esos filtros. Prueba con otras palabras o quita algún filtro.")
    st.stop()

# ------------------------------------------------------------------ IA en lote
if comun.hay_ia():
    with st.container(border=True):
        st.markdown("**🤖 La IA revisa tus oportunidades**")
        st.caption(
            "La búsqueda encuentra palabras; la IA entiende si de verdad te conviene. Evalúa 7 criterios "
            "y calcula un % de compatibilidad con una metodología fija (ver el detalle en cada tarjeta)."
        )
        c1, c2 = st.columns([3, 1])
        n = c1.slider("¿Cuántas de las primeras evaluar?", 1, min(15, len(f)), min(5, len(f)))
        if c2.button(f"Evaluar {n} con IA", type="primary", width="stretch"):
            with st.spinner(f"La IA está leyendo {n} convocatorias…"):
                ok = comun.evaluar_varias(f.head(n).to_dict("records"))
            st.toast(f"{ok} convocatorias evaluadas")
            st.rerun()
else:
    st.warning("Falta la clave DEEPSEEK_API_KEY: la evaluación con IA está desactivada.")

# ------------------------------------------------------------------ tarjetas
POR_PAGINA = 10
paginas = max(1, -(-len(f) // POR_PAGINA))
pag = st.number_input(f"Página (de {paginas})", 1, paginas, 1) if paginas > 1 else 1
for c in f.iloc[(pag - 1) * POR_PAGINA: pag * POR_PAGINA].to_dict("records"):
    comun.tarjeta(c, clave="buscar")

# ------------------------------------------------------------------ tabla y exportación
with st.expander(f"Ver las {len(f):,} en una tabla y exportar a Excel"):
    tabla = f[["fecha_publicacion", "entidad", "departamento", "provincia", "distrito", "descripcion", "categoria",
               "monto_soles", "metodo", "estado", "consultas_fin", "compatibilidad", "url_bases"]].rename(columns={
        "fecha_publicacion": "Publicado", "entidad": "Entidad", "departamento": "Departamento",
        "provincia": "Provincia", "distrito": "Distrito", "descripcion": "Descripción", "categoria": "Tipo",
        "monto_soles": "Valor referencial (S/)", "metodo": "Procedimiento", "estado": "Estado",
        "consultas_fin": "Fin de consultas", "compatibilidad": "Compatibilidad IA (%)", "url_bases": "Bases"})
    st.dataframe(tabla, hide_index=True, width="stretch", column_config={
        "Publicado": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Fin de consultas": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Valor referencial (S/)": st.column_config.NumberColumn(format="%,.0f"),
        "Bases": st.column_config.LinkColumn(display_text="PDF"),
    })
    buf = io.BytesIO()
    tabla.to_excel(buf, index=False, sheet_name="Convocatorias")
    st.download_button("⬇️ Exportar a Excel", buf.getvalue(), "licitapyme_convocatorias.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
