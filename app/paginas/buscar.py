"""Buscar convocatorias: filtros, tarjetas o tabla, y evaluación con IA."""

import io

import pandas as pd
import streamlit as st

import comun
import ui

p = comun.perfil()
df = comun.cargar_convocatorias()

ui.encabezado("Buscar convocatorias", "Filtra las convocatorias del SEACE y deja que la IA te diga cuáles te convienen.",
              sobre=p["nombre"])

# ------------------------------------------------------------------ filtros
with st.container(border=True):
    c1, c2 = st.columns([3, 2])
    palabras = comun.selector_palabras(c1, "palabras_buscar")
    deps = c2.multiselect("Departamento de la entidad", comun.DEPARTAMENTOS, format_func=str.title,
                          placeholder="Todos (tu cobertura aparece primero)")
    c1, c2, c3, c4, c5 = st.columns(5)
    tipos = c1.multiselect("Tipo", comun.TIPOS, default=p["tipos"], placeholder="Todos")
    estados = c2.multiselect("Estado del proceso", sorted(df["estado"].dropna().unique()), default=["CONVOCADO"],
                             help="CONVOCADO = proceso abierto en el último corte de datos.", placeholder="Todos")
    compat = c3.multiselect("Compatibilidad", list(ui.ESTADOS), placeholder="Todas",
                            format_func=lambda k: {"verde": "Alta", "amarillo": "Revisar", "rojo": "No cumple",
                                                   "gris": "Sin evaluar"}[k])
    monto_max = c4.number_input("Monto máximo (S/)", 0, 1_000_000_000, 0, step=100_000,
                                help="0 = sin límite. Incluye las que no publican monto.")
    orden = c5.selectbox("Ordenar por", ["Relevancia", "Compatibilidad IA", "Más recientes", "Mayor monto", "Cierre de consultas"])
    ver_descartadas = st.toggle("Mostrar las descartadas por la IA", value=False,
                                help="La búsqueda por palabras trae candidatas; la IA descarta las que no corresponden a "
                                     "tu empresa (por ejemplo, 'arroz' en una fórmula láctea). Por defecto se ocultan.")

f = comun.enriquecer(df, {**p, "palabras_clave": palabras})
if tipos:
    f = f[f["categoria"].isin(tipos)]
if estados:
    f = f[f["estado"].isin(estados)]
if deps:
    f = f[f["departamento"].isin(deps)]
if compat:
    f = f[f["semaforo"].isin(compat)]
if monto_max:
    f = f[f["monto_soles"].isna() | (f["monto_soles"] <= monto_max)]
if palabras or p.get("categorias"):
    f = f[f["coincidencia"] > 0]
descartadas = int((f["semaforo"] == "rojo").sum())
if not ver_descartadas and "rojo" not in compat:
    f = f[f["semaforo"] != "rojo"]

orden_cols = {
    "Relevancia": (["prioridad", "compatibilidad", "en_cobertura", "coincidencia", "fecha_publicacion"],
                   [True, False, False, False, False]),
    "Compatibilidad IA": (["prioridad", "compatibilidad", "coincidencia"], [True, False, False]),
    "Más recientes": (["fecha_publicacion"], [False]),
    "Mayor monto": (["monto_soles"], [False]),
    "Cierre de consultas": (["consultas_fin"], [True]),
}
cols, asc = orden_cols[orden]
f = f.sort_values(cols, ascending=asc, na_position="last")

# ------------------------------------------------------------------ resumen
k = st.columns(4)
ui.kpi(k[0], "Convocatorias encontradas", f"{len(f):,}", acento=True)
ui.kpi(k[1], "En tu cobertura", f"{int(f['en_cobertura'].sum()):,}")
ui.kpi(k[2], "Evaluadas por IA", f"{int((f['semaforo'] != 'gris').sum()):,}",
       f"{descartadas} descartadas ocultas" if descartadas and not ver_descartadas and "rojo" not in compat else None)
ui.kpi(k[3], "Valor referencial publicado", comun.soles(f["monto_soles"].sum()))

if f.empty:
    st.info("No hay convocatorias con esos filtros. Prueba con otras palabras o quita algún filtro.", icon=":material/search_off:")
    st.stop()

# ------------------------------------------------------------------ IA en lote
if comun.hay_ia():
    with st.container(border=True):
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.markdown("**La IA revisa tus oportunidades.** La búsqueda encuentra palabras; la IA entiende si de verdad "
                    "te conviene. Evalúa 7 criterios y calcula el porcentaje con una metodología fija.")
        sin_evaluar = f[f["semaforo"] == "gris"]
        tope = min(15, len(sin_evaluar))
        if tope == 0:
            c1.caption("Todas las convocatorias de esta lista ya están evaluadas.")
        else:
            n = c1.slider("¿Cuántas sin evaluar revisar?", 1, tope, min(5, tope)) if tope > 1 else 1
            if c2.button(f"Evaluar {n} con IA", type="primary", icon=":material/auto_awesome:", width="stretch"):
                with st.spinner(f"La IA está leyendo {n} convocatorias…"):
                    ok = comun.evaluar_varias(sin_evaluar.head(n).to_dict("records"))
                st.toast(f"{ok} convocatorias evaluadas")
                st.rerun()
else:
    st.warning("Falta la clave DEEPSEEK_API_KEY: la evaluación con IA está desactivada.")

# ------------------------------------------------------------------ resultados
vista = st.segmented_control("Vista", ["Tarjetas", "Tabla"], default="Tarjetas", label_visibility="collapsed")
tabla = f[["fecha_publicacion", "entidad", "departamento", "provincia", "distrito", "descripcion", "categoria",
           "monto_soles", "metodo", "estado", "consultas_fin", "compatibilidad", "url_bases", "ocid"]].rename(columns={
    "fecha_publicacion": "Publicado", "entidad": "Entidad", "departamento": "Departamento", "provincia": "Provincia",
    "distrito": "Distrito", "descripcion": "Descripción", "categoria": "Tipo", "monto_soles": "Valor referencial (S/)",
    "metodo": "Procedimiento", "estado": "Estado", "consultas_fin": "Fin de consultas",
    "compatibilidad": "Compatibilidad IA (%)", "url_bases": "Bases"})

if vista == "Tabla":
    sel = st.dataframe(
        tabla.drop(columns=["ocid"]), hide_index=True, width="stretch", height=480,
        on_select="rerun", selection_mode="single-row", key="tabla_buscar",
        column_config={
            "Publicado": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Fin de consultas": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Valor referencial (S/)": st.column_config.NumberColumn(format="%,.0f"),
            "Compatibilidad IA (%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d %%"),
            "Bases": st.column_config.LinkColumn(display_text="PDF"),
            "Descripción": st.column_config.TextColumn(width="large"),
        },
    )
    filas = sel.selection.rows if sel and sel.selection else []
    if filas:
        st.caption("Detalle de la convocatoria seleccionada")
        comun.tarjeta(f.iloc[filas[0]].to_dict(), clave="tabla")
    else:
        st.caption("Selecciona una fila para ver el detalle, guardarla o evaluarla con IA.")
else:
    POR_PAGINA = 10
    paginas = max(1, -(-len(f) // POR_PAGINA))
    pag = st.number_input(f"Página (de {paginas})", 1, paginas, 1) if paginas > 1 else 1
    for c in f.iloc[(pag - 1) * POR_PAGINA: pag * POR_PAGINA].to_dict("records"):
        comun.tarjeta(c, clave="buscar")

buf = io.BytesIO()
tabla.drop(columns=["ocid"]).to_excel(buf, index=False, sheet_name="Convocatorias")
st.download_button(f"Exportar las {len(f):,} a Excel", buf.getvalue(), "licitapyme_convocatorias.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:")
