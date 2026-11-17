"""Pruebas de la función Premium "Preparar postulación" (sin llamar a la IA)."""

import io
import sys
from pathlib import Path

from docx import Document

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app"))
sys.path.insert(0, str(RAIZ))

from test_paginas import abrir, base_temporal, crear_empresa, db_y_comun, textos  # noqa: E402,F401


def test_postulacion_sin_candidatas_invita_a_buscar():
    _, comun = db_y_comun()
    crear_empresa(comun.PERFIL_DEMO)
    at = abrir("postulacion.py")
    assert "Primero guarda o evalúa" in textos(at)


def test_postulacion_elige_la_mas_compatible_y_arma_el_word():
    db, comun = db_y_comun()
    eid = crear_empresa(comun.PERFIL_DEMO)
    df = comun.cargar_convocatorias()
    a, b = df[df["estado"] == "CONVOCADO"]["ocid"].head(2)
    db.guardar_evaluacion(eid, a, 1, {"puntaje": 60, "semaforo": "amarillo", "confianza": 70, "criterios": {}, "revisar": ["x"]})
    db.guardar_evaluacion(eid, b, 1, {"puntaje": 90, "semaforo": "verde", "confianza": 80, "criterios": {}, "revisar": ["Experiencia"]})
    at = abrir("postulacion.py")
    assert at.selectbox[0].value == b                      # la más compatible queda elegida
    assert any(d.label == "Descargar paquete en Word" for d in at.get("download_button"))


def test_word_resalta_los_datos_por_completar():
    import word
    conv = {"entidad": "Entidad X", "metodo": "Concurso", "nomenclatura": "CP-1", "descripcion": "Servicio", "url_bases": None}
    datos = word.generar("Empresa", conv, "RUC: [COMPLETAR: RUC]",
                         [{"listo": False, "requisito": "RNP", "categoria": "P", "obligatorio": "Sí", "fuente": "General"}],
                         [{"item": "ITEM", "referencia": "Sin referencia"}], "fuente")
    doc = Document(io.BytesIO(datos))
    resaltados = [r.text for p in doc.paragraphs for r in p.runs if r.font.highlight_color]
    assert "[COMPLETAR: RUC]" in resaltados
    assert len(doc.tables) == 2


def test_seleccion_automatica_quita_palabras_de_otro_rubro():
    _, comun = db_y_comun()
    import formulario_perfil as fp
    p = {**comun.PERFIL_VACIO, "actividad": "Tienda de abarrotes",
         "palabras_clave": ["servicio de limpieza", "abarrotes"], "categorias": []}
    analisis = {"palabras_sugeridas": ["arroz", "zzzz-no-existe"], "palabras_no_relacionadas": ["servicio de limpieza"],
                "categorias_sugeridas": ["ARROZ PILADO"]}
    sel = fp.seleccion_automatica(p, analisis)
    assert "servicio de limpieza" not in sel["palabras_clave"] and sel["quitadas"] == ["servicio de limpieza"]
    assert "arroz" in sel["palabras_clave"]                  # sugerida con convocatorias reales
    assert "zzzz-no-existe" not in sel["palabras_clave"]     # sugerida sin convocatorias: descartada
    assert "abarrotes" in sel["palabras_clave"]              # declarada y relacionada: se conserva


def test_carta_reemplaza_ruc_no_declarado():
    from ai.documentos import verificar_numeros
    assert verificar_numeros("Empresa con RUC 20123456789", "") == ["20123456789"]
    assert verificar_numeros("Empresa con RUC 20123456789", "20123456789") == []
