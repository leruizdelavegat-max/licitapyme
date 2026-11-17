"""Inicio: dashboard personalizado de la empresa activa."""

import pandas as pd
import plotly.express as px
import streamlit as st

import comun
import ui

p = comun.perfil()
df = comun.enriquecer(comun.cargar_convocatorias(), p)
abiertas = df[df["estado"] == "CONVOCADO"]
del_tipo = abiertas[abiertas["categoria"].isin(p["tipos"])] if p["tipos"] else abiertas
candidatas = del_tipo[del_tipo["coincidencia"] > 0]
# Las que la IA descartó (rojas) no se muestran en el Inicio: no estorban.
descartadas = candidatas[candidatas["semaforo"] == "rojo"]
coinciden = candidatas[candidatas["semaforo"] != "rojo"].sort_values(
    ["prioridad", "en_cobertura", "coincidencia", "fecha_publicacion"], ascending=[True, False, False, False])
ev = comun.evaluaciones(solo_vigentes=True)
evaluadas = coinciden[coinciden["ocid"].isin(ev)]
altas = evaluadas[evaluadas["semaforo"] == "verde"]

if st.session_state.pop("_bienvenida", None):
    st.success("Perfil confirmado. Estas son las oportunidades que encontramos para tu empresa.", icon=":material/check_circle:")

# ------------------------------------------------------------------ A. encabezado empresarial
c1, c2 = st.columns([5, 1.2], vertical_alignment="bottom")
with c1:
    ui.encabezado(p["nombre"], p["actividad"], sobre="Panel de oportunidades")
    st.html(ui.meta([("Cobertura", ", ".join(d.title() for d in p["cobertura"]) or "No indicada"),
                     ("Tipo", ", ".join(p["tipos"])), ("Monto máximo", comun.soles(p["monto_max"]))]))
c2.page_link("paginas/perfil.py", label="Editar perfil", icon=":material/edit:")

# ------------------------------------------------------------------ B. indicadores
k = st.columns(5)
ui.kpi(k[0], "Convocatorias abiertas", f"{len(del_tipo):,}", "del tipo que ofreces")
ui.kpi(k[1], "Coinciden con tu perfil", f"{len(coinciden):,}",
       f"{len(descartadas)} descartadas por la IA" if len(descartadas) else "por palabras y categorías", acento=True)
ui.kpi(k[2], "Dentro de tu cobertura", f"{int(coinciden['en_cobertura'].sum()):,}", "de las que coinciden")
ui.kpi(k[3], "Evaluadas por IA", f"{len(evaluadas) + len(descartadas):,}", "con tu perfil actual")
ui.kpi(k[4], "Alta compatibilidad", f"{len(altas):,}", "70 % o más, con confianza")

if coinciden.empty:
    st.info("Ninguna convocatoria abierta coincide con tus palabras clave y categorías. Ajusta tu perfil para ampliar la búsqueda.",
            icon=":material/search_off:")
    st.page_link("paginas/perfil.py", label="Editar perfil", icon=":material/edit:")
    st.stop()

# ------------------------------------------------------------------ C. recomendaciones de IA
ui.seccion("Recomendaciones de la IA", "Las más compatibles con tu empresa")
if evaluadas.empty:
    with st.container(border=True):
        if len(descartadas):
            st.markdown(f"La IA revisó {len(descartadas)} coincidencia(s) y las descartó porque no corresponden a tu "
                        "empresa. Puedes pedirle que revise las siguientes.")
        else:
            st.markdown("Todavía no hay evaluaciones con tu perfil actual. La IA puede revisar tus mejores coincidencias "
                        "en unos segundos y explicarte cuáles te convienen.")
        sin_evaluar = coinciden[coinciden["semaforo"] == "gris"]
        if comun.hay_ia() and not sin_evaluar.empty and st.button(
                "Evaluar mis 5 mejores coincidencias", type="primary", icon=":material/auto_awesome:"):
            with st.spinner("La IA está leyendo las convocatorias…"):
                comun.evaluar_varias(sin_evaluar.head(5).to_dict("records"))
            st.rerun()
else:
    top = evaluadas.sort_values("compatibilidad", ascending=False).head(3)
    cols = st.columns(len(top))
    for col, c in zip(cols, top.to_dict("records")):
        r = ev[c["ocid"]]
        with col.container(border=True):
            st.html(ui.pastilla(r["semaforo"], f"{r['puntaje']} % compatible") +
                    f'<div class="lp-titulo" style="margin-top:8px">{ui.e(c["entidad"])}</div>'
                    f'<div class="lp-desc">{ui.e(str(c["descripcion"])[:140])}</div>'
                    f'<div class="lp-desc" style="color:{ui.TEXTO_SUAVE}"><b>Por qué:</b> {ui.e(r["por_que"])}</div>'
                    + ui.meta([("Valor ref.", comun.soles(c["monto_soles"])), ("Plazo", comun.plazo_txt(c))]))
            with st.popover("Ver análisis completo", icon=":material/insights:", width="stretch"):
                comun.mostrar_evaluacion_detalle(r)
    pendientes = coinciden[~coinciden["ocid"].isin(ev)]
    if comun.hay_ia() and not pendientes.empty and st.button(
            f"Evaluar 5 coincidencias más ({len(pendientes)} sin evaluar)", icon=":material/auto_awesome:"):
        with st.spinner("La IA está leyendo las convocatorias…"):
            comun.evaluar_varias(pendientes.head(5).to_dict("records"))
        st.rerun()

# ------------------------------------------------------------------ D. resumen geográfico y E. actividad reciente
izq, der = st.columns([1.1, 1])
with izq:
    ui.seccion("Dónde están tus oportunidades", "Coincidencias por departamento")
    por_dep = coinciden.groupby("departamento").size().sort_values().tail(10).rename("n").reset_index()
    por_dep["cobertura"] = por_dep["departamento"].isin(p["cobertura"]).map({True: "En tu cobertura", False: "Fuera de tu cobertura"})
    fig = px.bar(por_dep, x="n", y="departamento", orientation="h", color="cobertura", height=320,
                 color_discrete_map={"En tu cobertura": ui.AZUL, "Fuera de tu cobertura": "#B8C4D6"},
                 labels={"n": "", "departamento": "", "cobertura": ""})
    fig.update_layout(margin=dict(l=0, r=0, t=30, b=0),
                      legend=dict(orientation="h", y=1.08, x=0, yanchor="bottom", title=None))
    st.plotly_chart(fig, width="stretch")
    st.page_link("paginas/mapa.py", label="Abrir el mapa interactivo", icon=":material/map:")

with der:
    ui.seccion("Actividad reciente")
    t_nuevas, t_guard, t_venc = st.tabs(["Nuevas", "Guardadas", "Próximos vencimientos"])
    with t_nuevas:
        for c in coinciden.sort_values("fecha_publicacion", ascending=False).head(5).to_dict("records"):
            st.html(f'<div class="lp-titulo" style="font-size:14px">{ui.e(c["entidad"])}</div>'
                    + ui.meta([("Publicado", comun.fecha(c["fecha_publicacion"])), ("Lugar", str(c["departamento"]).title())]))
    with t_guard:
        g = comun.guardadas()
        if not g:
            st.caption("Aún no guardas oportunidades.")
        else:
            mis = df[df["ocid"].isin(g)].assign(estado_seg=lambda d: d["ocid"].map(lambda o: g[o]["estado"]))
            for c in mis.head(5).to_dict("records"):
                st.html(f'<div class="lp-titulo" style="font-size:14px">{ui.e(c["entidad"])}</div>'
                        + ui.meta([("Estado", c["estado_seg"]), ("Valor ref.", comun.soles(c["monto_soles"]))]))
            st.page_link("paginas/mis_oportunidades.py", label=f"Ver mis {len(g)} oportunidades", icon=":material/bookmarks:")
    with t_venc:
        prox = coinciden[coinciden["dias_consultas"].between(0, 30)].sort_values("consultas_fin").head(5)
        if prox.empty:
            st.caption("No hay cierres de consultas en los próximos 30 días (respecto a la fecha de referencia).")
        for c in prox.to_dict("records"):
            st.html(f'<div class="lp-titulo" style="font-size:14px">{ui.e(c["entidad"])}</div>'
                    + ui.meta([("Cierre de consultas", comun.fecha(c["consultas_fin"])), ("Faltan", f"{int(c['dias_consultas'])} días")]))

st.divider()
st.page_link("paginas/buscar.py", label=f"Revisar las {len(coinciden):,} coincidencias en Buscar convocatorias",
             icon=":material/search:")
