"""Mis oportunidades: seguimiento, requisitos desde las bases, comparador e historial."""

import io
from datetime import datetime

import pandas as pd
import streamlit as st

import comun

st.title("⭐ Mis oportunidades")
p = comun.perfil()
g = comun.guardadas()

if not g:
    st.info("Todavía no guardas convocatorias. Usa **☆ Guardar** en *Buscar convocatorias* o en el *Mapa*.")
    st.stop()

df = comun.enriquecer(comun.cargar_convocatorias(), p)
mis = df[df["ocid"].isin(g)].copy()
mis["seguimiento"] = mis["ocid"].map(lambda o: g[o]["estado"])
mis["nota"] = mis["ocid"].map(lambda o: g[o]["nota"])
historial = st.session_state.setdefault("historial", [])

tab_seg, tab_req, tab_comp, tab_hist = st.tabs(["📋 Seguimiento y calendario", "📄 Requisitos de las bases", "⚖️ Comparador", "🕘 Historial"])

# ------------------------------------------------------------------ seguimiento
with tab_seg:
    st.caption("Cambia el estado o escribe una nota directamente en la tabla. Ordenada por cierre de consultas (calendario).")
    vista = mis.sort_values("consultas_fin", na_position="last")[
        ["ocid", "seguimiento", "nota", "entidad", "descripcion", "monto_soles", "consultas_fin", "compatibilidad", "departamento"]
    ]
    editado = st.data_editor(
        vista, hide_index=True, width="stretch", disabled=["ocid", "entidad", "descripcion", "monto_soles", "consultas_fin", "compatibilidad", "departamento"],
        column_config={
            "ocid": None,
            "seguimiento": st.column_config.SelectboxColumn("Estado", options=comun.ESTADOS_SEGUIMIENTO, required=True),
            "nota": st.column_config.TextColumn("Nota"),
            "entidad": "Entidad", "descripcion": st.column_config.TextColumn("Descripción", width="large"),
            "monto_soles": st.column_config.NumberColumn("Valor ref. (S/)", format="%,.0f"),
            "consultas_fin": st.column_config.DateColumn("Fin de consultas", format="DD/MM/YYYY"),
            "compatibilidad": st.column_config.NumberColumn("Compat. IA (%)"),
            "departamento": "Departamento",
        },
        key="editor_seguimiento",
    )
    cambios = False
    for r in editado.to_dict("records"):
        actual = g[r["ocid"]]
        if r["seguimiento"] != actual["estado"]:
            historial.append({"fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "entidad": r["entidad"],
                              "cambio": f"{actual['estado']} → {r['seguimiento']}"})
            actual["estado"] = r["seguimiento"]
            cambios = True
        if (r["nota"] or "") != actual["nota"]:
            actual["nota"] = r["nota"] or ""
    if cambios:
        st.rerun()

    c1, c2 = st.columns(2)
    buf = io.BytesIO()
    exportar = editado.drop(columns=["ocid"]).rename(columns={"seguimiento": "Estado", "nota": "Nota", "entidad": "Entidad",
                                                              "descripcion": "Descripción", "monto_soles": "Valor referencial (S/)",
                                                              "consultas_fin": "Fin de consultas", "compatibilidad": "Compatibilidad IA (%)",
                                                              "departamento": "Departamento"})
    exportar.to_excel(buf, index=False, sheet_name="Mis oportunidades")
    c1.download_button("⬇️ Exportar a Excel", buf.getvalue(), "mis_oportunidades.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    quitar = c2.selectbox("Quitar de mis oportunidades", [None] + list(mis["ocid"]),
                          format_func=lambda o: "—" if o is None else mis.set_index("ocid").loc[o, "entidad"])
    if quitar and c2.button("Quitar"):
        g.pop(quitar, None)
        st.rerun()

# ------------------------------------------------------------------ requisitos
with tab_req:
    st.caption(
        "Descarga las bases desde el SEACE (botón 📄 de cada convocatoria) y súbelas aquí. La IA identifica los "
        "requisitos y **cada uno se verifica contra el texto real del PDF**, con su página. El SEACE no permite "
        "descargas automáticas, por eso se suben a mano."
    )
    reqs = st.session_state.setdefault("requisitos", {})
    sel = st.selectbox("Convocatoria", list(mis["ocid"]),
                       format_func=lambda o: f"{mis.set_index('ocid').loc[o, 'entidad']} — {str(mis.set_index('ocid').loc[o, 'descripcion'])[:70]}")
    conv = mis.set_index("ocid").loc[sel].to_dict() | {"ocid": sel}
    if conv.get("url_bases"):
        st.link_button("📄 Abrir las bases en el SEACE", conv["url_bases"])
    pdf = st.file_uploader("Sube el PDF de las bases", type="pdf", key=f"pdf_{sel}")
    if pdf is not None and st.button("🤖 Identificar requisitos", type="primary", disabled=not comun.hay_ia()):
        from ai.requisitos import extraer
        with st.spinner("Leyendo las bases… (puede tardar 1 minuto)"):
            try:
                reqs[sel] = extraer(pdf.getvalue())
            except Exception as e:
                reqs[sel] = {"ok": False, "motivo": f"No se pudo leer el PDF ({type(e).__name__}).", "requisitos": []}
    res = reqs.get(sel)
    if res:
        if not res["ok"]:
            st.error(res["motivo"])
        else:
            from ai.requisitos import NOMBRE_CATEGORIA
            ver = [r for r in res["requisitos"] if r["verificado"]]
            nover = [r for r in res["requisitos"] if not r["verificado"]]
            st.success(f"{len(ver)} requisitos verificados en el documento ({res['n_paginas']} páginas)."
                       + (" Solo se leyó la primera parte: el PDF es muy largo." if res.get("truncado") else ""))
            for cat, nombre in NOMBRE_CATEGORIA.items():
                grupo = [r for r in ver if r["categoria"] == cat]
                if grupo:
                    st.markdown(f"**{nombre}**")
                    for r in grupo:
                        oblig = {True: "🔴 Obligatorio", False: "⚪ Opcional / puntaje", None: "❔ No precisa"}[r["obligatorio"]]
                        st.markdown(f"- {r['requisito']} — {oblig} · *pág. {r['pagina']}*  \n  <small>“{r['cita']}”</small>",
                                    unsafe_allow_html=True)
            if nover:
                with st.expander(f"⚠️ {len(nover)} requisito(s) que la IA mencionó pero NO se encontraron en el PDF (no confiables)"):
                    for r in nover:
                        st.markdown(f"- {r['requisito']} (pág. {r['pagina']} indicada)")
            if st.button("🔁 Re-evaluar compatibilidad usando estos requisitos", disabled=not comun.hay_ia()):
                with st.spinner("Re-evaluando con los requisitos de las bases…"):
                    comun.evaluaciones().pop(sel, None)
                    r = comun.evaluar(conv, requisitos=ver)
                st.success(f"Nueva compatibilidad: {r['puntaje']} % (confianza {r['confianza']} %)" if r else "No se pudo evaluar.")

# ------------------------------------------------------------------ comparador
with tab_comp:
    elegir = st.multiselect(
        "Elige de 2 a 4 oportunidades para comparar", list(mis["ocid"]), max_selections=4,
        default=list(mis["ocid"])[:min(3, len(mis))] if len(mis) >= 2 else [],
        format_func=lambda o: f"{mis.set_index('ocid').loc[o, 'entidad']} — {str(mis.set_index('ocid').loc[o, 'descripcion'])[:50]}",
    )
    if len(elegir) >= 2:
        ev = comun.evaluaciones()
        reqs = st.session_state.get("requisitos", {})
        filas = {}
        for i, o in enumerate(elegir, start=1):
            c = mis.set_index("ocid").loc[o]
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
            st.caption(f"{len(faltan)} sin evaluar: la comparación será mejor si las evalúas primero.")
        if st.button("🤖 ¿Cuál me conviene más?", type="primary", disabled=not comun.hay_ia()):
            from ai.comparador import comparar
            if faltan:
                with st.spinner("Evaluando las que faltan…"):
                    comun.evaluar_varias([mis.set_index("ocid").loc[o].to_dict() | {"ocid": o} for o in faltan])
            with st.spinner("Comparando…"):
                st.session_state["comparacion"] = comparar(comun.texto_perfil(p), [{"codigo": k, **v} for k, v in filas.items()])
        comp = st.session_state.get("comparacion")
        if comp:
            st.markdown(f"**Conclusión:** {comp['conclusion']}")
            for i, x in enumerate(comp["ranking"], start=1):
                st.markdown(f"{i}. **{x['codigo']} — {filas.get(x['codigo'], {}).get('Entidad', '')}**: {x['razon']}")
            st.caption(f"⚠️ {comp['advertencia']}")
    else:
        st.info("Guarda al menos 2 oportunidades para compararlas.")

# ------------------------------------------------------------------ historial
with tab_hist:
    filas = [{"fecha": v["guardada_el"], "entidad": df.set_index("ocid").loc[o, "entidad"] if o in set(df["ocid"]) else o,
              "cambio": "Guardada"} for o, v in g.items()] + historial
    st.dataframe(pd.DataFrame(filas).iloc[::-1], hide_index=True, width="stretch",
                 column_config={"fecha": "Fecha", "entidad": "Entidad", "cambio": "Cambio"})
