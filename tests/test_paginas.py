"""Pruebas de LicitaPYME: páginas, perfil persistente y varias empresas.

Cada prueba usa su propia base SQLite temporal (no toca data/licitapyme.db) y no llama a la IA.
Correr con:
    python -m pytest tests -q
"""

import os
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app"))

APP = str(RAIZ / "app" / "app.py")
PAGINAS = ["inicio.py", "mapa.py", "buscar.py", "mis_oportunidades.py", "mercado.py", "perfil.py"]


@pytest.fixture(autouse=True)
def base_temporal(tmp_path, monkeypatch):
    """Base de datos nueva y vacía para cada prueba; sin clave de IA para no gastar saldo."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'prueba.db'}")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    import streamlit as st
    st.cache_resource.clear()
    yield


def db_y_comun():
    import comun
    import db
    return db, comun


def crear_empresa(datos: dict, usuario: str = "local", confirmada: bool = True) -> int:
    db, comun = db_y_comun()
    db.asegurar_usuario(usuario)
    return db.crear_empresa(usuario, {**comun.PERFIL_VACIO, **datos},
                            estado="confirmado" if confirmada else "borrador", paso=4 if confirmada else 1)


def abrir(pagina: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    if pagina:
        at.switch_page(f"paginas/{pagina}").run()
    assert not at.exception, at.exception[0].message if at.exception else ""
    return at


def textos(at: AppTest) -> str:
    partes = [m.value for m in at.markdown] + [h.value for h in at.title] + [c.value for c in at.caption]
    partes += [x.value for x in at.info] + [x.value for x in at.warning] + [x.value for x in at.success]
    partes += [getattr(x, "body", "") for x in at.get("html")]
    return "\n".join(str(p) for p in partes)


# ------------------------------------------------------------------ estados del perfil
def test_usuario_nuevo_ve_configuracion_inicial():
    at = abrir()
    assert "Comencemos conociendo tu empresa" in textos(at)
    # Las demás secciones están bloqueadas: no hay botón para registrar otra empresa ni dashboard.
    assert not any(b.label == "Registrar otra empresa" for b in at.button)


def test_nube_sin_login_solo_permite_modo_ejemplo(monkeypatch):
    """Con base compartida (Postgres) y sin [auth], nadie entra como usuario común."""
    import db
    monkeypatch.setattr(db, "es_nube", lambda: True)
    at = abrir()
    assert any(b.label == "Explorar con una empresa de ejemplo" for b in at.button)
    assert not any(b.label == "Ingresar con Google" for b in at.button)
    next(b for b in at.button if b.label == "Explorar con una empresa de ejemplo").click().run()
    assert not at.exception
    assert "Panel de oportunidades" in textos(at)
    assert db.empresas_de("local") == []  # el visitante no quedó en el usuario compartido


def test_perfil_incompleto_continua_en_su_paso():
    db, comun = db_y_comun()
    eid = crear_empresa({"nombre": "Borrador SAC"}, confirmada=False)
    db.actualizar_empresa(eid, "local", paso=3)
    at = abrir()
    html = textos(at)
    assert "Comencemos conociendo tu empresa" in html
    assert "lp-activo\">3." in html  # el asistente abre en el paso 3


def test_asistente_paso_1_guarda_borrador():
    db, _ = db_y_comun()
    at = abrir()
    at.text_input(key="cfg_nombre").input("Abarrotes Prueba S.A.C.")
    at.text_area(key="cfg_actividad").input("Venta al por mayor de abarrotes para instituciones públicas.")
    next(b for b in at.button if b.label == "Siguiente").click().run()
    assert not at.exception
    empresas = db.empresas_de("local")
    assert len(empresas) == 1 and empresas[0]["estado"] == "borrador" and empresas[0]["paso"] == 2
    assert empresas[0]["nombre"] == "Abarrotes Prueba S.A.C."


def test_asistente_valida_campos_obligatorios():
    db, _ = db_y_comun()
    at = abrir()
    next(b for b in at.button if b.label == "Siguiente").click().run()
    assert any("nombre" in e.value for e in at.error)
    assert db.empresas_de("local") == []


def test_perfil_confirmado_entra_directo_al_dashboard():
    _, comun = db_y_comun()
    crear_empresa(comun.PERFIL_DEMO)
    at = abrir()
    html = textos(at)
    assert "Panel de oportunidades" in html and comun.PERFIL_DEMO["nombre"] in html
    assert "Comencemos conociendo tu empresa" not in html


# ------------------------------------------------------------------ varias empresas
def test_cambiar_de_empresa_y_datos_separados():
    db, comun = db_y_comun()
    a = crear_empresa({**comun.PERFIL_DEMO, "nombre": "Empresa A"})
    b = crear_empresa({**comun.PERFIL_DEMO, "nombre": "Empresa B", "palabras_clave": ["abarrotes"], "tipos": ["Bienes"]})
    df = comun.cargar_convocatorias()
    ocid = df["ocid"].iloc[0]
    db.guardar(a, ocid, "Entidad X")  # solo la empresa A guarda esta convocatoria

    assert ocid in db.guardadas_de(a)
    assert ocid not in db.guardadas_de(b)

    # La última creada (B) es la activa: su página de oportunidades no ve lo de A.
    at = abrir("mis_oportunidades.py")
    assert "Todavía no guardas convocatorias" in textos(at)

    # Cambiamos a A desde el selector de la barra lateral.
    at = abrir()
    at.selectbox(key="selector_empresa").select(a).run()
    assert not at.exception
    assert db.asegurar_usuario("local")["ultima_empresa_id"] == a
    at.switch_page("paginas/mis_oportunidades.py").run()
    assert not at.exception
    assert "Todavía no guardas convocatorias" not in textos(at)


def test_registrar_otra_empresa():
    db, comun = db_y_comun()
    crear_empresa(comun.PERFIL_DEMO)
    at = abrir()
    next(b for b in at.button if b.label == "Registrar otra empresa").click().run()
    assert not at.exception
    lista = db.empresas_de("local")
    assert len(lista) == 2 and lista[-1]["estado"] == "borrador"
    assert "Comencemos conociendo tu empresa" in textos(at)


def test_empresa_de_otro_usuario_no_es_accesible():
    db, comun = db_y_comun()
    ajena = crear_empresa(comun.PERFIL_DEMO, usuario="otra@persona.pe")
    assert db.empresa(ajena, "local") is None
    assert db.empresas_de("local") == []


# ------------------------------------------------------------------ edición del perfil
def test_editar_perfil_conserva_guardadas_e_historial_y_desactualiza_evaluaciones():
    db, comun = db_y_comun()
    eid = crear_empresa(comun.PERFIL_DEMO)
    ocid = comun.cargar_convocatorias()["ocid"].iloc[0]
    db.guardar(eid, ocid, "Entidad X")
    db.guardar_evaluacion(eid, ocid, 1, {"puntaje": 80, "semaforo": "verde", "confianza": 70})

    at = abrir("perfil.py")
    at.number_input(key="ed_monto").set_value(2_000_000)
    next(b for b in at.button if b.label == "Guardar cambios" and b.form_id == "form_cobertura").click().run()
    assert not at.exception

    emp = db.empresa(eid, "local")
    assert emp["datos"]["monto_max"] == 2_000_000
    assert emp["version"] == 2                       # cambio relevante → nueva versión
    assert ocid in db.guardadas_de(eid)              # no se pierden las guardadas
    assert any(h["evento"] == "Guardada" for h in db.historial_de(eid))      # ni el historial
    assert db.evaluaciones_de(eid)[ocid]["version_perfil"] == 1             # la evaluación queda desactualizada


# ------------------------------------------------------------------ todas las páginas con distintos perfiles
PERFILES = {
    "limpieza (ejemplo)": {},
    "abarrotes": {"palabras_clave": ["abarrotes", "arroz", "aceite"], "tipos": ["Bienes"], "cobertura": ["AYACUCHO"], "categorias": []},
    "computadoras": {"palabras_clave": ["computadora", "laptop"], "tipos": ["Bienes"], "cobertura": [], "categorias": []},
    "sin resultados": {"palabras_clave": ["zzzz-no-existe"], "tipos": ["Obras"], "cobertura": ["TUMBES"], "categorias": []},
    "una sola coincidencia": {"palabras_clave": ["MASCOTACHOS"], "tipos": ["Bienes"], "cobertura": ["LIMA"], "categorias": []},
}


@pytest.mark.parametrize("nombre_perfil", list(PERFILES))
@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_no_se_cae(pagina, nombre_perfil):
    _, comun = db_y_comun()
    crear_empresa({**comun.PERFIL_DEMO, **PERFILES[nombre_perfil]})
    abrir(pagina)


def test_pagina_con_guardadas():
    db, comun = db_y_comun()
    eid = crear_empresa(comun.PERFIL_DEMO)
    df = comun.cargar_convocatorias()
    for o in df[df["estado"] == "CONVOCADO"]["ocid"].head(3):
        db.guardar(eid, o, None)
    abrir("mis_oportunidades.py")


def test_buscar_y_mapa_usan_la_misma_busqueda():
    """Lo que se escribe en las palabras clave vale para Buscar y Mapa."""
    db, comun = db_y_comun()
    eid = crear_empresa({**comun.PERFIL_DEMO, "tipos": ["Bienes", "Servicios"], "categorias": []})
    db.guardar_preferencias(eid, {"palabras_busqueda": ["abarrotes"]})
    conteos = {}
    for pagina in ["buscar.py", "mapa.py"]:
        at = abrir(pagina)
        conteos[pagina] = int(next(h.body for h in at.get("html") if "lp-kpi" in str(getattr(h, "body", "")))
                              .split('lp-val">')[1].split("<")[0].replace(",", ""))
    assert conteos["mapa.py"] > 0, "el mapa no muestra las convocatorias de abarrotes"
    assert conteos["mapa.py"] <= conteos["buscar.py"], f"el mapa no usa la misma búsqueda: {conteos}"


def test_busqueda_no_confunde_arroz_con_carrozable():
    _, comun = db_y_comun()
    df = comun.cargar_convocatorias()
    hallados = df[comun.puntuar_palabras(df, ["arroz"]) > 0]
    assert not hallados["texto_desc"].str.contains("CARROZABLE").all()
    assert not any("CARROZABLE" in t and "ARROZ " not in t.replace("CARROZABLE", "") for t in hallados["texto_desc"])
