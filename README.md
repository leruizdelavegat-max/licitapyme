# LicitaPYME

> *Nombre provisional.*

## 1. One-liner
Avisamos a las PYMES proveedoras del Estado a qué convocatorias del SEACE pueden postular, con IA que lee cada convocatoria y la compara con su perfil.

## 2. Founder
**Luz Estefany Ruiz de la Vega Tenorio** — Universidad del Pacífico.
_(foto, una línea sobre ti y por qué eres la persona indicada; cómo cubres producto, ingeniería, diseño y ventas con agentes de IA)_

## 3. Problema
_Pendiente: quién lo sufre con precisión, cuánto le cuesta, cómo lo resuelve hoy._
Evidencia: notas de 3 conversaciones en [`docs/research/`](docs/research/).

## 4. Solución e insight
_Pendiente._

## 5. Why now
_Pendiente._

## 6. Demo
- URL: _pendiente_
- Cómo correrlo en local:

```bash
pip install -r requirements.txt
python scripts/descargar_datos.py      # descarga los datos abiertos del SEACE (OCDS)
python scripts/preparar_convocatorias.py
streamlit run app/app.py
```

**Datos:** contrataciones públicas del SEACE publicadas por el OECE en el estándar
Open Contracting (OCDS), obtenidas del [registro de datos de Open Contracting](https://data.open-contracting.org/es/publication/135).

_Pendiente: 3 capturas y diagrama de arquitectura en `docs/`._

## 7. Modelo de negocio
_Pendiente._

## 8. Herramientas del curso
| Herramienta | Para qué | Dónde está |
|---|---|---|
| APIs / datos abiertos (sesión 03) | Ingesta de convocatorias del SEACE en formato OCDS | `scripts/` |
| Dashboards (sesión 05) | Oportunidades por región, monto y fecha | `app/app.py` |
| LLM con salidas estructuradas (sesión 08) | DeepSeek lee cada convocatoria y el perfil de la PYME y devuelve un JSON (resumen, puntaje de encaje 0-100, qué revisar, alerta) validado con Pydantic | `ai/analizar.py` |

## 9. Qué hizo el agente
_Pendiente._
