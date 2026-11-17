# Guion del pitch (3 minutos)

Formato del curso: 0:00–0:30 problema · 0:30–2:30 demo en vivo · 2:30–3:00 negocio. A los 3:00 se corta.
Ensaya con cronómetro. Lo que está entre [corchetes] lo completas con tus conversaciones.

**Antes de empezar:** app abierta en el **Inicio** de una empresa ya configurada (con 3 o 4 convocatorias ya
evaluadas y 2 guardadas), segunda pestaña con el **Mapa**, pantalla compartida probada. Video de respaldo listo.

---

## 0:00 – 0:30 · El problema
> "En solo dos meses el Estado publicó más de **13 mil procesos** de compra en el SEACE. Una MYPE que quiere
> venderle al Estado tendría que revisarlos uno por uno. [Una dueña de una empresa de ___ me dijo: *'___'*.]
> Hoy lo resuelven a mano, por WhatsApp o pagándole a un tramitador. Y aunque encuentren la convocatoria,
> no saben si les conviene, cuánto se suele pagar ni quién suele ganar."

## 0:30 – 2:30 · Demo (un caso real, de principio a fin)

| Tiempo | Qué muestras | Qué dices |
|---|---|---|
| 0:30 | **Inicio**: encabezado de la empresa e indicadores | "Esta es una empresa de limpieza de Lima. LicitaPYME ya sabe qué vende y dónde puede atender, porque la empresa se presentó una sola vez y su perfil queda guardado." |
| 0:50 | **Recomendaciones de la IA**: abre "Ver análisis completo" en la de mayor % | "La IA leyó cada convocatoria y la comparó con la empresa. Este 92 % no lo inventa el modelo: son 7 criterios con pesos fijos; dos los calcula una regla y cinco la IA, citando la evidencia. Si falta información, no se castiga: baja la confianza." |
| 1:20 | **Buscar**: una tarjeta en amarillo o rojo (p. ej. la limpieza del Banco de la Nación en agencias de Cusco y Puno) | "La búsqueda por palabras encuentra 'limpieza' y la entidad tiene sede en Lima. Pero el servicio es en agencias de Cusco, Apurímac y Puno, fuera de mi cobertura: la IA lo detecta y no la recomienda como alta compatibilidad. Ese es el valor: no encontrar palabras, sino decirte si te conviene." |
| 1:40 | **Mapa**: acercar a Lima y hacer clic en un punto | "Aquí ves dónde están. Ojo: los datos abiertos no traen el lugar de ejecución, así que ubicamos la sede de la entidad, y no inventamos coordenadas." |
| 2:00 | **Análisis del mercado** → Precios y Proveedores | "Y antes de postular: un servicio de limpieza de oficinas se adjudica a una mediana de ~S/ 488 mil, y estas son las empresas que más ganan. Con eso la MYPE fija su precio." |
| 2:20 | (Opcional, si sobra tiempo) **Mis oportunidades → Comparador** | "Guardo dos y la IA me dice cuál priorizar, sin confundir el mayor monto con la mayor rentabilidad." |

## 2:30 – 3:00 · El negocio
> "Cobramos **S/ 49 al mes** a la MYPE y **S/ 199** a contadores con varias empresas. Cada usuario nos cuesta
> unos **S/ 4** en IA, servidor y cobro: el margen es de 92 %. Si LicitaPYME te ayuda a ganar un solo contrato,
> la suscripción anual se paga cientos de veces. Lo que sigue: datos diarios del SEACE y alertas por WhatsApp."

---

## Preguntas probables en los comentarios (2 minutos)
- **¿De dónde salen los datos?** Datos abiertos del SEACE que publica el OECE en estándar OCDS; ~13 mil convocatorias y 83 mil ítems adjudicados desde 2024.
- **¿Por qué el corte es de octubre?** La fuente abierta se publica una vez al mes. En producción se leería el SEACE a diario.
- **¿Cómo sabes que la IA no inventa?** El porcentaje lo calcula una fórmula; cada criterio trae su evidencia; los requisitos de las bases se buscan en el texto real del PDF y los que no aparecen se descartan.
- **¿Qué herramientas del curso usaste?** APIs y datos abiertos, dashboards, mapas con Folium, LLM con salidas estructuradas y Document AI (lectura de las bases).
- **Muéstrame el código de X.** `ai/compatibilidad.py` (metodología), `ai/requisitos.py` (verificación de citas), `app/db.py` (persistencia).
- **¿Qué hizo el agente?** Ver sección 9 del README: yo elegí el problema, el usuario, el alcance y el modelo de negocio; Claude Code escribió y probó el código.
