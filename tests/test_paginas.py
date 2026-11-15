"""Prueba de humo: abre todas las páginas con perfiles distintos y verifica que ninguna se caiga.

No llama a la IA (no presiona botones de evaluación). Correr con:
    python -m pytest tests -q
"""

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app"))
import comun  # noqa: E402

PAGINAS = ["inicio.py", "mapa.py", "buscar.py", "mis_oportunidades.py", "mercado.py", "perfil.py"]

PERFILES = {
    "limpieza (ejemplo)": {},
    "abarrotes": {"palabras_clave": ["abarrotes", "arroz", "aceite"], "tipos": ["Bienes"], "cobertura": ["AYACUCHO"]},
    "computadoras": {"palabras_clave": ["computadora", "laptop"], "tipos": ["Bienes"], "cobertura": []},
    "sin resultados": {"palabras_clave": ["zzzz-no-existe"], "tipos": ["Obras"], "cobertura": ["TUMBES"]},
    "una sola coincidencia": {"palabras_clave": ["MASCOTACHOS"], "tipos": ["Bienes"], "cobertura": ["LIMA"]},
}


@pytest.mark.parametrize("nombre_perfil", list(PERFILES))
@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_no_se_cae(pagina, nombre_perfil):
    at = AppTest.from_file(str(RAIZ / "app" / "app.py"), default_timeout=120)
    at.session_state["perfil"] = {**comun.PERFIL_DEMO, **PERFILES[nombre_perfil]}
    at.run()
    at.switch_page(f"paginas/{pagina}").run()
    assert not at.exception, f"{pagina} con perfil '{nombre_perfil}': {at.exception[0].message if at.exception else ''}"


def test_buscar_y_mapa_usan_la_misma_busqueda():
    """Lo que se escribe en «¿Qué buscas?» vale para Buscar y Mapa (antes el mapa usaba solo el perfil)."""
    conteos = {}
    for pagina in ["buscar.py", "mapa.py"]:
        at = AppTest.from_file(str(RAIZ / "app" / "app.py"), default_timeout=120)
        # Perfil de limpieza, pero la persona busca "abarrotes" (que son Bienes).
        at.session_state["perfil"] = {**comun.PERFIL_DEMO, "tipos": ["Bienes", "Servicios"]}
        at.session_state["palabras_busqueda"] = ["abarrotes"]
        at.run()
        at.switch_page(f"paginas/{pagina}").run()
        assert not at.exception
        conteos[pagina] = int(at.metric[0].value.replace(",", ""))
    assert conteos["mapa.py"] > 0, "el mapa no muestra las convocatorias de abarrotes"
    # El mapa tiene filtros extra (fecha), así que puede mostrar menos, nunca más que Buscar.
    assert conteos["mapa.py"] <= conteos["buscar.py"], f"el mapa no usa la misma búsqueda: {conteos}"


def test_pagina_con_guardadas():
    """Mis oportunidades con convocatorias guardadas (tabla, requisitos y comparador)."""
    at = AppTest.from_file(str(RAIZ / "app" / "app.py"), default_timeout=120)
    df = comun.cargar_convocatorias()
    ocids = df[df["estado"] == "CONVOCADO"]["ocid"].head(3).tolist()
    at.session_state["guardadas"] = {o: {"estado": "Guardada", "nota": "", "guardada_el": "15/11/2026 10:00"} for o in ocids}
    at.run()
    at.switch_page("paginas/mis_oportunidades.py").run()
    assert not at.exception, at.exception[0].message if at.exception else ""
