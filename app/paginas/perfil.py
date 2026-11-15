"""Perfil de mi empresa: lo que la IA usa para evaluar la compatibilidad."""

import json

import streamlit as st

import comun

st.title("🏢 Perfil de mi empresa")
st.caption(
    "Con este perfil LicitaPYME busca convocatorias y la IA evalúa la compatibilidad. "
    "Viene cargado con una empresa de ejemplo: reemplázalo con los datos de la tuya."
)

p = comun.perfil()
distritos = comun.cargar_distritos()

with st.form("perfil"):
    st.subheader("Datos de la empresa")
    c1, c2 = st.columns([3, 1])
    nombre = c1.text_input("Nombre o razón social", p["nombre"])
    ruc = c2.text_input("RUC (opcional)", p["ruc"], max_chars=11)
    actividad = st.text_input("Actividad económica (giro / CIIU)", p["actividad"])
    productos = st.text_area("Bienes y servicios que ofreces", p["productos"], height=90)
    palabras = st.multiselect(
        "Palabras clave para buscar convocatorias",
        options=sorted(set(p["palabras_clave"])),
        default=p["palabras_clave"],
        accept_new_options=True,
        help="Escribe una palabra y presiona Enter para agregarla. Ej.: servicio de limpieza, uniformes, tóner.",
    )

    st.subheader("Ubicación y cobertura")
    st.caption(
        "Tu **domicilio fiscal** solo sirve para estimar distancias. Tu **cobertura** son los departamentos "
        "donde estás dispuesta(o) a entregar bienes o prestar servicios: no excluye convocatorias, "
        "sirve para priorizarlas."
    )
    opciones_dom = distritos["inei"].tolist()
    etiquetas = dict(zip(distritos["inei"], distritos["etiqueta"]))
    domicilio = st.selectbox(
        "Domicilio fiscal (distrito) 🔍",
        options=opciones_dom,
        index=opciones_dom.index(p["domicilio_ubigeo"]) if p["domicilio_ubigeo"] in opciones_dom else None,
        format_func=lambda x: etiquetas.get(x, x).title(),
        placeholder="Escribe para buscar tu distrito…",
    )
    cobertura = st.multiselect(
        "Departamentos donde puedes atender 🔍",
        options=comun.DEPARTAMENTOS,
        default=[d for d in p["cobertura"] if d in comun.DEPARTAMENTOS],
        format_func=str.title,
        placeholder="Escribe para buscar un departamento…",
    )
    todo_peru = st.checkbox("Puedo atender en todo el Perú", value=len(p["cobertura"]) == len(comun.DEPARTAMENTOS))

    st.subheader("Capacidad")
    c1, c2, c3 = st.columns(3)
    tipos = c1.multiselect("Tipo de contratación", comun.TIPOS, default=p["tipos"])
    monto_max = c2.number_input("Monto máximo por contrato (S/)", 0, 100_000_000, int(p["monto_max"]), step=50_000)
    facturacion = c3.number_input("Facturación anual (S/)", 0, 1_000_000_000, int(p["facturacion_anual"]), step=50_000)
    experiencia = st.text_area("Experiencia (años, clientes, montos, contratos con el Estado)", p["experiencia"], height=90)
    capacidad = st.text_area("Capacidad operativa (personal, equipos, locales)", p["capacidad"], height=70)
    rnp = st.radio(
        "¿Inscrito en el RNP (Registro Nacional de Proveedores)?",
        ["Sí, vigente", "En trámite", "No", "No sé"],
        index=["Sí, vigente", "En trámite", "No", "No sé"].index(p["rnp"]),
        horizontal=True,
        help="El RNP vigente es obligatorio para contratar con el Estado.",
    )

    if st.form_submit_button("💾 Guardar perfil", type="primary"):
        st.session_state["perfil"] = {
            "nombre": nombre.strip() or "Mi empresa",
            "ruc": ruc.strip(),
            "actividad": actividad.strip(),
            "productos": productos.strip(),
            "palabras_clave": palabras,
            "domicilio_ubigeo": domicilio,
            "cobertura": list(comun.DEPARTAMENTOS) if todo_peru else cobertura,
            "tipos": tipos or list(comun.TIPOS),
            "monto_max": monto_max,
            "facturacion_anual": facturacion,
            "experiencia": experiencia.strip(),
            "capacidad": capacidad.strip(),
            "rnp": rnp,
        }
        # El perfil cambió: las evaluaciones anteriores ya no aplican.
        st.session_state["evaluaciones"] = {}
        st.success("Perfil guardado. Las evaluaciones anteriores se borraron porque dependían del perfil anterior.")

st.divider()
st.subheader("Llevar mi perfil a otra sesión")
st.caption("Esta versión no tiene cuentas de usuario: descarga tu perfil y tus oportunidades guardadas y vuelve a cargarlos después.")
c1, c2 = st.columns(2)
paquete = {
    "perfil": comun.perfil(),
    "guardadas": comun.guardadas(),
    "evaluaciones": comun.evaluaciones(),
}
c1.download_button(
    "⬇️ Descargar mi espacio (JSON)",
    json.dumps(paquete, ensure_ascii=False, indent=1, default=str),
    file_name="licitapyme_mi_espacio.json",
    mime="application/json",
)
archivo = c2.file_uploader("Cargar mi espacio", type="json", label_visibility="collapsed")
if archivo is not None and st.session_state.get("_espacio_cargado") != archivo.file_id:
    try:
        datos = json.loads(archivo.getvalue())
        st.session_state["perfil"] = {**comun.PERFIL_DEMO, **datos.get("perfil", {})}
        st.session_state["guardadas"] = datos.get("guardadas", {})
        st.session_state["evaluaciones"] = datos.get("evaluaciones", {})
        st.session_state["_espacio_cargado"] = archivo.file_id
        st.rerun()
    except (json.JSONDecodeError, AttributeError):
        st.error("El archivo no es un espacio de LicitaPYME válido.")
