"""Bloques del formulario de perfil y la vista de interpretación con IA.

Los usan dos páginas: la configuración inicial (paso a paso) y la edición del perfil.
"""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

import comun
import ui

PASOS = ["Datos de la empresa", "Productos y servicios", "Cobertura y capacidad", "Análisis del perfil"]


# ------------------------------------------------------------------ bloques
def bloque_datos(p: dict, clave: str) -> dict:
    c1, c2 = st.columns([3, 1.3])
    nombre = c1.text_input("Nombre o razón social *", p["nombre"], key=f"{clave}_nombre", placeholder="Ej.: Comercial Andina S.A.C.")
    ruc = c2.text_input("RUC", p["ruc"], max_chars=11, key=f"{clave}_ruc", placeholder="11 dígitos",
                        help="Opcional. Debe empezar con 10 o 20.")
    actividad = st.text_area(
        "¿A qué se dedica tu empresa? *", p["actividad"], height=80, key=f"{clave}_actividad",
        placeholder="Ej.: Venta al por mayor de abarrotes y productos de primera necesidad en Ayacucho.",
        help="Describe tu actividad principal con tus palabras. Si conoces tu código CIIU, inclúyelo.",
    )
    return {"nombre": nombre.strip(), "ruc": ruc.strip(), "actividad": actividad.strip()}


def bloque_oferta(p: dict, clave: str) -> dict:
    c1, c2 = st.columns(2)
    productos = c1.text_area("Productos que comercializas", p.get("productos", ""), height=110, key=f"{clave}_productos",
                             placeholder="Ej.: arroz, azúcar, aceite, conservas, útiles de limpieza…")
    servicios = c2.text_area("Servicios que ofreces", p.get("servicios", ""), height=110, key=f"{clave}_servicios",
                             placeholder="Ej.: distribución a domicilio, catering, limpieza de oficinas…")
    st.caption("Opcional: si dejas estos campos vacíos, la IA deduce lo que vendes a partir de tu actividad "
               "(por ejemplo, de \"tienda de abarrotes\" deduce arroz, azúcar, aceite, víveres…).")
    texto = st.text_input(
        "Palabras clave para buscar convocatorias", ", ".join(p["palabras_clave"]), key=f"{clave}_palabras",
        placeholder="Ej.: abarrotes, víveres, arroz, útiles de limpieza",
        help="Sepáralas con comas. Opcional: la IA agrega las que correspondan a tu actividad.",
    )
    palabras = list(dict.fromkeys(w.strip() for w in texto.split(",") if w.strip()))
    return {"productos": productos.strip(), "servicios": servicios.strip(), "palabras_clave": palabras}


def bloque_cobertura(p: dict, clave: str) -> dict:
    distritos = comun.cargar_distritos()
    opciones = distritos["inei"].tolist()
    etiquetas = dict(zip(distritos["inei"], distritos["etiqueta"]))
    st.caption("Tu **domicilio fiscal** solo sirve para estimar distancias. Tu **cobertura** son los departamentos donde "
               "puedes entregar bienes o prestar servicios: no excluye convocatorias, sirve para priorizarlas.")
    c1, c2 = st.columns(2)
    domicilio = c1.selectbox(
        "Domicilio fiscal (distrito)", options=opciones,
        index=opciones.index(p["domicilio_ubigeo"]) if p.get("domicilio_ubigeo") in opciones else None,
        format_func=lambda x: etiquetas.get(x, x).title(), placeholder="Escribe para buscar tu distrito",
        key=f"{clave}_domicilio",
    )
    tipos = c2.multiselect("Tipo de contratación *", comun.TIPOS, default=[t for t in p["tipos"] if t in comun.TIPOS],
                           key=f"{clave}_tipos", placeholder="Bienes, servicios u obras")
    cobertura = st.multiselect(
        "Departamentos donde puedes atender *", comun.DEPARTAMENTOS,
        default=[d for d in p["cobertura"] if d in comun.DEPARTAMENTOS], format_func=str.title,
        key=f"{clave}_cobertura", placeholder="Escribe para buscar un departamento",
    )
    todo = st.checkbox("Puedo atender en todo el Perú", value=len(p["cobertura"]) == len(comun.DEPARTAMENTOS),
                       key=f"{clave}_todo")
    c1, c2, c3 = st.columns(3)
    monto_max = c1.number_input("Monto máximo por contrato (S/) *", 0, 100_000_000, int(p["monto_max"] or 0),
                                step=50_000, key=f"{clave}_monto")
    facturacion = c2.number_input("Facturación anual aprox. (S/)", 0, 1_000_000_000, int(p["facturacion_anual"] or 0),
                                  step=50_000, key=f"{clave}_fact")
    rnp = c3.selectbox("¿Inscrito en el RNP?", comun.RNP_OPCIONES,
                       index=comun.RNP_OPCIONES.index(p["rnp"]) if p["rnp"] in comun.RNP_OPCIONES else 3,
                       key=f"{clave}_rnp", help="El Registro Nacional de Proveedores vigente es obligatorio para contratar con el Estado.")
    experiencia = st.text_area("Experiencia (opcional)", p["experiencia"], height=80, key=f"{clave}_exp",
                               placeholder="Años en el rubro, principales clientes, contratos con el Estado, montos facturados…")
    capacidad = st.text_area("Capacidad operativa (opcional)", p["capacidad"], height=70, key=f"{clave}_cap",
                             placeholder="Personal, vehículos, almacenes, equipos…")
    return {
        "domicilio_ubigeo": domicilio, "tipos": tipos,
        "cobertura": list(comun.DEPARTAMENTOS) if todo else cobertura,
        "monto_max": int(monto_max), "facturacion_anual": int(facturacion), "rnp": rnp,
        "experiencia": experiencia.strip(), "capacidad": capacidad.strip(),
    }


def errores(paso: int, d: dict) -> list[str]:
    e = []
    if paso == 1:
        if not d["nombre"]:
            e.append("Escribe el nombre de la empresa.")
        if d["ruc"] and not re.fullmatch(r"(10|15|17|20)\d{9}", d["ruc"]):
            e.append("El RUC debe tener 11 dígitos y empezar con 10 o 20.")
        if len(d["actividad"]) < 10:
            e.append("Describe en una frase a qué se dedica tu empresa.")
    elif paso == 2:
        pass  # opcional: la IA deduce productos y palabras clave de la actividad
    elif paso == 3:
        if not d["tipos"]:
            e.append("Elige si vendes bienes, servicios u obras.")
        if not d["cobertura"]:
            e.append("Elige al menos un departamento donde puedas atender.")
        if not d["monto_max"]:
            e.append("Indica el monto máximo por contrato que puedes atender.")
    return e


# Campos que, si cambian, hacen que las evaluaciones anteriores queden desactualizadas.
RELEVANTES = ["actividad", "productos", "servicios", "palabras_clave", "categorias", "cobertura", "tipos",
              "monto_max", "facturacion_anual", "experiencia", "capacidad", "rnp"]


def cambio_relevante(antes: dict, despues: dict) -> bool:
    return any(antes.get(k) != despues.get(k) for k in RELEVANTES)


# ------------------------------------------------------------------ interpretación con IA
@st.cache_data(show_spinner=False)
def contar_coincidencias(palabra: str) -> int:
    df = comun.cargar_convocatorias()
    abiertas = df[df["estado"] == "CONVOCADO"]
    return int((comun.puntuar_palabras(abiertas, [palabra]) > 0).sum())


def ejecutar_interpretacion(p: dict, actividad_anterior: str | None = None) -> dict | None:
    from ai.perfil import interpretar
    try:
        r = interpretar(comun.texto_perfil(p), p["palabras_clave"], actividad_anterior)
        if r is None:
            st.session_state["_ia_error"] = "La IA respondió en un formato inesperado. Intenta de nuevo."
        return r
    except Exception as ex:
        print(f"[IA] perfil: {type(ex).__name__}: {ex}")
        st.session_state["_ia_error"] = comun.mensaje_error_ia(ex)
        return None


def seleccion_automatica(p: dict, analisis: dict | None) -> dict:
    """Palabras y categorías que la app propone sola a partir de la interpretación de la IA.

    - Quita las palabras declaradas que la IA marcó como ajenas a la actividad (p. ej. tras un cambio de rubro).
    - Agrega las sugeridas que encuentran al menos una convocatoria abierta.
    - Elige las categorías CUBSO reales que corresponden.
    """
    if not analisis:
        return {"palabras_clave": list(p["palabras_clave"]), "categorias": list(p.get("categorias") or []),
                "agregadas": [], "quitadas": []}
    ajenas = {comun.normalizar(w) for w in analisis.get("palabras_no_relacionadas") or []}
    quitadas = [w for w in p["palabras_clave"] if comun.normalizar(w) in ajenas]
    conservadas = [w for w in p["palabras_clave"] if w not in quitadas]
    sugeridas = [w for w in analisis.get("palabras_sugeridas") or [] if contar_coincidencias(w) > 0]
    palabras = list(dict.fromkeys(conservadas + sugeridas))
    agregadas = [w for w in palabras if w not in p["palabras_clave"]]
    cats = categorias_reales(analisis.get("categorias_sugeridas") or [], palabras)
    previas = [c for c in p.get("categorias") or [] if c in set(cats["cubso"])]
    categorias = previas or cats["cubso"].tolist()[:5]
    return {"palabras_clave": palabras, "categorias": categorias, "agregadas": agregadas, "quitadas": quitadas}


def categorias_reales(sugeridas: list[str], palabras: list[str]) -> pd.DataFrame:
    """Busca en el catálogo CUBSO real las categorías sugeridas y las de las palabras clave."""
    cat = comun.catalogo_cubso()
    encontradas = []
    for s in sugeridas:
        tokens = [t for t in comun.normalizar(s).split() if len(t) > 3 and t not in {"SERVICIO", "SERVICIOS", "PARA", "ADQUISICION"}]
        if not tokens:
            continue
        mask = pd.Series(True, index=cat.index)
        for t in tokens[:4]:
            mask &= comun.contiene(cat["norm"], t)
        encontradas.append(cat[mask])
    for pal in palabras:
        encontradas.append(cat[comun.contiene(cat["norm"], comun.normalizar(pal))])
    if not encontradas:
        return cat.head(0)
    res = pd.concat(encontradas).drop_duplicates("cubso")
    res = res[(res["abiertas"] > 0) | (res["adjudicadas"] > 0)]
    return res.sort_values(["abiertas", "adjudicadas"], ascending=False).head(12)


def vista_analisis(emp: dict, al_confirmar_texto: str, automatico: bool = True) -> dict | None:
    """Muestra la interpretación del perfil. Devuelve {palabras, categorias} si la persona confirma.

    automatico=False: no llama a la IA hasta que la persona lo pida (página de edición).
    """
    p = {**comun.PERFIL_VACIO, **emp["datos"]}
    analisis = emp.get("analisis")

    pedir = automatico
    if analisis is None and comun.hay_ia() and not automatico:
        pedir = st.button("Pedir sugerencias a la IA", icon=":material/auto_awesome:", key=f"pedir_ia_{emp['id']}")
    if analisis is None and comun.hay_ia() and pedir:
        with st.spinner("La IA está interpretando tu perfil…"):
            analisis = ejecutar_interpretacion(p)
        if not analisis and st.session_state.get("_ia_error"):
            st.error(st.session_state.pop("_ia_error"), icon=":material/error:")
        if analisis:
            import db
            db.actualizar_empresa(emp["id"], emp["usuario_id"], analisis=analisis)

    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.markdown("**Lo que entendimos de tu empresa**")
        if analisis:
            if analisis["actividades"]:
                st.markdown("Actividades: " + "; ".join(analisis["actividades"]))
            if analisis["productos"]:
                st.markdown("Productos: " + ", ".join(analisis["productos"]))
            if analisis["servicios"]:
                st.markdown("Servicios: " + ", ".join(analisis["servicios"]))
            st.caption("Resumen generado por IA a partir de lo que declaraste. Si algo no es correcto, vuelve a editar.")
        else:
            st.caption("La interpretación con IA no está disponible ahora. Puedes confirmar el perfil igual.")
    with c2.container(border=True):
        st.markdown("**Cobertura y capacidad declaradas**")
        _, _, dom = comun.domicilio_coords(p)
        st.html(ui.meta([("Domicilio", (dom or "No indicado").title())]) +
                ui.meta([("Cobertura", ", ".join(d.title() for d in p["cobertura"]) or "No indicada")]) +
                ui.meta([("Tipo", ", ".join(p["tipos"]) or "No indicado"), ("Monto máximo", comun.soles(p["monto_max"]))]) +
                ui.meta([("Facturación anual", comun.soles(p["facturacion_anual"]) if p["facturacion_anual"] else "No indicada"),
                         ("RNP", p["rnp"])]))
        st.caption("Estos datos no los interpreta la IA: se usan tal como los escribiste.")

    # Palabras clave: la app ya deja marcadas las que corresponden a la actividad (selección automática);
    # la persona solo ajusta si quiere.
    sel = seleccion_automatica(p, analisis)
    ui.seccion("Palabras clave para buscar", "Número = convocatorias abiertas que encuentra cada una")
    candidatas = list(dict.fromkeys(sel["palabras_clave"] + p["palabras_clave"]
                                    + (analisis.get("palabras_sugeridas") or [] if analisis else [])))
    conteos = {w: contar_coincidencias(w) for w in candidatas}
    utiles = [w for w in candidatas if conteos[w] > 0 or w in p["palabras_clave"]]
    descartadas = [w for w in candidatas if w not in utiles]
    if sel["agregadas"] or sel["quitadas"]:
        st.caption("Ya dejamos marcadas las palabras según tu actividad"
                   + (f". Agregadas: {', '.join(sel['agregadas'])}" if sel["agregadas"] else "")
                   + (f". Quitadas porque no corresponden a tu actividad: {', '.join(sel['quitadas'])}" if sel["quitadas"] else "")
                   + ". Puedes ajustarlas.")
    elegidas = st.multiselect(
        "Palabras con las que buscaremos lo que vendes", options=utiles,
        default=[w for w in sel["palabras_clave"] if w in utiles],
        format_func=lambda w: f"{w} ({conteos[w]})", key=f"analisis_palabras_{emp['id']}_{emp['version']}",
        accept_new_options=True,
    )
    if descartadas:
        st.caption("Sugerencias descartadas porque no encuentran ninguna convocatoria abierta: " + ", ".join(descartadas))

    ui.seccion("Categorías del catálogo del Estado (CUBSO)", "Solo categorías que existen en los datos reales")
    cats = categorias_reales(analisis.get("categorias_sugeridas") or [] if analisis else [], elegidas)
    if cats.empty:
        st.caption("No encontramos categorías del catálogo para este perfil. La búsqueda usará tus palabras clave.")
        categorias = []
    else:
        info = cats.set_index("cubso")
        categorias = st.multiselect(
            "Categorías relacionadas con tu empresa", options=cats["cubso"].tolist(),
            default=[c for c in sel["categorias"] if c in set(cats["cubso"])] or cats["cubso"].tolist()[:5],
            format_func=lambda c: f"{c.title()} ({info.loc[c, 'abiertas']} abiertas)",
            key=f"analisis_cats_{emp['id']}_{emp['version']}",
        )
    if analisis and analisis.get("observacion"):
        st.info(analisis["observacion"], icon=":material/lightbulb:")

    if st.button(al_confirmar_texto, type="primary", icon=":material/check_circle:", disabled=not elegidas):
        return {"palabras_clave": elegidas, "categorias": categorias}
    if not elegidas:
        st.caption("Elige al menos una palabra clave para continuar.")
    return None
