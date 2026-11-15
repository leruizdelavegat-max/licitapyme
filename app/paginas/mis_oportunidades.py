"""Mis oportunidades: seguimiento, requisitos desde las bases, comparador e historial.

Todo se guarda en la base de datos de la empresa activa.
"""

import io

import pandas as pd
import streamlit as st

import comun
import db
import ui

p = comun.perfil()
eid = comun.empresa_id()
g = comun.guardadas()

ui.encabezado("Mis oportunidades", "Organiza las convocatorias que te interesan, revisa sus requisitos y compáralas.",
              sobre=p["nombre"])

if not g:
    st.info("Todavía no guardas convocatorias. Usa **Guardar** en *Buscar convocatorias*, en el *Mapa* o en el *Inicio*.",
            icon=":material/bookmark_add:")
    st.page_link("paginas/buscar.py", label="Ir a Buscar convocatorias", icon=":material/search:")
    st.stop()

df = comun.enriquecer(comun.cargar_convocatorias(), p)
mis = df[df["ocid"].isin(g)].copy()
mis["seguimiento"] = mis["ocid"].map(lambda o: g[o]["estado"])
mis["nota"] = mis["ocid"].map(lambda o: g[o]["nota"])
por_ocid = mis.set_index("ocid")


def nombre_corto(o: str) -> str:
    return f"{por_ocid.loc[o, 'entidad']} — {str(por_ocid.loc[o, 'descripcion'])[:60]}"


k = st.columns(4)
ui.kpi(k[0], "Guardadas", f"{len(mis)}", acento=True)
ui.kpi(k[1], "En preparación o postuladas",
       f"{int(mis['seguimiento'].isin(['Preparando postulación', 'Postulada']).sum())}")
ui.kpi(k[2], "Adjudicadas", f"{int((mis['seguimiento'] == 'Adjudicada').sum())}")
ui.kpi(k[3], "Evaluadas por IA", f"{int((mis['semaforo'] != 'gris').sum())}")

tab_seg, tab_req, tab_comp, tab_hist = st.tabs(["Seguimiento y calendario", "Requisitos de las bases", "Comparador", "Historial"])

# ------------------------------------------------------------------ seguimiento
with tab_seg:
    st.caption("Cambia el estado o escribe una nota directamente en la tabla. Ordenada por cierre de consultas (calendario).")
    vista = mis.sort_values("consultas_fin", na_position="last")[
        ["ocid", "seguimiento", "nota", "entidad", "descripcion", "monto_soles", "consultas_fin", "compatibilidad", "departamento"]
    ]
    editado = st.data_editor(
        vista, hide_index=True, width="stretch",
        disabled=["ocid", "entidad", "descripcion", "monto_soles", "consultas_fin", "compatibilidad", "departamento"],
        column_config={
            "ocid": None,
            "seguimiento": st.column_config.SelectboxColumn("Estado", options=comun.ESTADOS_SEGUIMIENTO, required=True),
            "nota": st.column_config.TextColumn("Nota"),
            "entidad": "Entidad", "descripcion": st.column_config.TextColumn("Descripción", width="large"),
            "monto_soles": st.column_config.NumberColumn("Valor ref. (S/)", format="%,.0f"),
            "consultas_fin": st.column_config.DateColumn("Fin de consultas", format="DD/MM/YYYY"),
            "compatibilidad": st.column_config.ProgressColumn("Compatibilidad IA", min_value=0, max_value=100, format="%d %%"),
            "departamento": "Departamento",
        },
        key=f"editor_seguimiento_{eid}",
    )
    cambios = False
    for r in editado.to_dict("records"):
        actual = g[r["ocid"]]
        nota = r["nota"] or ""
        if r["seguimiento"] != actual["estado"] or nota != actual["nota"]:
            db.actualizar_guardada(eid, r["ocid"], r["entidad"], estado=r["seguimiento"], nota=nota)
            cambios = True
    if cambios:
        comun.invalidar("guardadas")
        st.rerun()

    c1, c2, c3 = st.columns([1.3, 2, 1], vertical_alignment="bottom")
    buf = io.BytesIO()
    editado.drop(columns=["ocid"]).rename(columns={
        "seguimiento": "Estado", "nota": "Nota", "entidad": "Entidad", "descripcion": "Descripción",
        "monto_soles": "Valor referencial (S/)", "consultas_fin": "Fin de consultas",
        "compatibilidad": "Compatibilidad IA (%)", "departamento": "Departamento"}).to_excel(buf, index=False, sheet_name="Mis oportunidades")
    c1.download_button("Exportar a Excel", buf.getvalue(), "mis_oportunidades.xlsx", icon=":material/download:",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    quitar = c2.selectbox("Quitar de mis oportunidades", [None] + list(mis["ocid"]),
                          format_func=lambda o: "Elige una…" if o is None else nombre_corto(o))
    if quitar and c3.button("Quitar", icon=":material/delete:"):
        db.quitar_guardada(eid, quitar, por_ocid.loc[quitar, "entidad"])
        comun.invalidar("guardadas")
        st.rerun()

# ------------------------------------------------------------------ requisitos
with tab_req:
    st.caption(
        "Descarga las bases desde el SEACE y súbelas aquí. La IA identifica los requisitos y **cada uno se verifica "
        "contra el texto real del PDF**, con su página. El SEACE no permite descargas automáticas, por eso se suben a mano."
    )
    reqs = comun.requisitos()
    sel = st.selectbox("Convocatoria", list(mis["ocid"]), format_func=nombre_corto)
    conv = por_ocid.loc[sel].to_dict() | {"ocid": sel}
    if conv.get("url_bases"):
        st.link_button("Abrir las bases en el SEACE", conv["url_bases"], icon=":material/open_in_new:")
    pdf = st.file_uploader("Sube el PDF de las bases", type="pdf", key=f"pdf_{eid}_{sel}")
    if pdf is not None and st.button("Identificar requisitos", type="primary", icon=":material/auto_awesome:",
                                     disabled=not comun.hay_ia()):
        from ai.requisitos import extraer
        with st.spinner("Leyendo las bases… (puede tardar 1 minuto)"):
            try:
                res_nuevo = extraer(pdf.getvalue())
            except Exception as ex:
                res_nuevo = {"ok": False, "motivo": f"No se pudo leer el PDF ({type(ex).__name__}).", "requisitos": []}
        db.guardar_requisitos(eid, sel, res_nuevo)
        if res_nuevo.get("ok"):
            db.registrar_evento(eid, "Requisitos identificados desde las bases", sel, conv["entidad"])
        comun.invalidar("requisitos")
        st.rerun()
    res = reqs.get(sel)
    if res:
        if not res["ok"]:
            st.error(res["motivo"], icon=":material/error:")
        else:
            from ai.requisitos import NOMBRE_CATEGORIA
            ver = [r for r in res["requisitos"] if r["verificado"]]
            nover = [r for r in res["requisitos"] if not r["verificado"]]
            st.success(f"{len(ver)} requisitos verificados en el documento ({res['n_paginas']} páginas)."
                       + (" Solo se leyó la primera parte: el PDF es muy largo." if res.get("truncado") else ""),
                       icon=":material/fact_check:")
            for cat, nombre in NOMBRE_CATEGORIA.items():
                grupo = [r for r in ver if r["categoria"] == cat]
                if grupo:
                    st.markdown(f"**{nombre}**")
                    for r in grupo:
                        oblig = {True: "Obligatorio", False: "Opcional / puntaje", None: "No precisa"}[r["obligatorio"]]
                        st.markdown(f"- {r['requisito']} — *{oblig} · pág. {r['pagina']}*  \n  <small>“{r['cita']}”</small>",
                                    unsafe_allow_html=True)
            if nover:
                with st.expander(f"{len(nover)} requisito(s) que la IA mencionó pero NO se encontraron en el PDF (no confiables)",
                                 icon=":material/warning:"):
                    for r in nover:
                        st.markdown(f"- {r['requisito']} (pág. {r['pagina']} indicada)")
            if st.button("Re-evaluar compatibilidad usando estos requisitos", icon=":material/refresh:", disabled=not comun.hay_ia()):
                with st.spinner("Re-evaluando con los requisitos de las bases…"):
                    r = comun.evaluar(conv, requisitos=ver)
                st.success(f"Nueva compatibilidad: {r['puntaje']} % (confianza {r['confianza']} %)" if r else "No se pudo evaluar.")

# ------------------------------------------------------------------ comparador
with tab_comp:
    elegir = st.multiselect(
        "Elige de 2 a 4 oportunidades para comparar", list(mis["ocid"]), max_selections=4,
        default=list(mis["ocid"])[:min(3, len(mis))] if len(mis) >= 2 else [], format_func=nombre_corto,
    )
    if len(elegir) >= 2:
        ev = comun.evaluaciones(solo_vigentes=True)
        reqs = comun.requisitos()
        filas = {}
        for i, o in enumerate(elegir, start=1):
            c = por_ocid.loc[o]
            e = ev.get(o)
            rq = [r for r in (reqs.get(o) or {}).get("requisitos", []) if r["verificado"]]
            filas[f"C{i}"] = {
                "Entidad": c["entidad"],
                "Objeto": str(c["descripcion"])[:160],
                "Valor referencial": comun.soles(c["monto_soles"]),
                "Ubicación": comun.ubicacion_txt(c.to_dict()),
                "Distancia": f"~{c['distancia_km']:,.0f} km" if pd.notna(c["distancia_km"]) else "No disponible",
                "Plazo disponible": comun.plazo_txt(c.to_dict()),
                "Requisitos principales": "; ".join(r["requisito"] for r in rq[:4]) or "Sube las bases para identificarlos",
                "Experiencia solicitada": e["criterios"]["experiencia"]["evidencia"] if e else "Sin evaluar",
                "Compatibilidad": f"{e['puntaje']} % (confianza {e['confianza']} %)" if e else "Sin evaluar",
                "Principales dificultades": "; ".join(e["dificultades"]) if e else "Sin evaluar",
            }
        st.dataframe(pd.DataFrame(filas), width="stretch")
        faltan = [o for o in elegir if o not in ev]
        if faltan:
            st.caption(f"{len(faltan)} sin evaluar: se evaluarán antes de comparar.")
        if st.button("¿Cuál me conviene más?", type="primary", icon=":material/balance:", disabled=not comun.hay_ia()):
            if faltan:
                with st.spinner("Primero evalúo las que faltan…"):
                    comun.evaluar_varias([por_ocid.loc[o].to_dict() | {"ocid": o} for o in faltan])
            st.session_state["comparar_ahora"] = True
            st.rerun()
        if st.session_state.pop("comparar_ahora", False):
            from ai.comparador import comparar
            with st.spinner("Comparando…"):
                st.session_state["comparacion"] = {"empresa": eid, "res": comparar(
                    comun.texto_perfil(p), [{"codigo": k_, **v} for k_, v in filas.items()])}
        comp = st.session_state.get("comparacion")
        if comp and comp["empresa"] == eid and comp["res"]:
            res = comp["res"]
            with st.container(border=True):
                st.markdown(f"**Conclusión:** {res['conclusion']}")
                for i, x in enumerate(res["ranking"], start=1):
                    st.markdown(f"{i}. **{x['codigo']} — {filas.get(x['codigo'], {}).get('Entidad', '')}**: {x['razon']}")
                st.caption(res["advertencia"])
    else:
        st.info("Guarda al menos 2 oportunidades para compararlas.")

# ------------------------------------------------------------------ historial
with tab_hist:
    h = pd.DataFrame(db.historial_de(eid))
    if h.empty:
        st.caption("Sin movimientos todavía.")
    else:
        st.dataframe(h[["fecha", "entidad", "evento"]], hide_index=True, width="stretch",
                     column_config={"fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
                                    "entidad": "Entidad", "evento": "Movimiento"})
