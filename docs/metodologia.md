# Metodología de LicitaPYME

Este documento explica **cómo LicitaPYME calcula cada número que muestra**, qué datos usa y qué
limitaciones tiene. La regla general: si un dato no está, se dice; nunca se inventa.

## 1. Fuente de datos

| Dato | Fuente | Actualización |
|---|---|---|
| Convocatorias y adjudicaciones | Datos abiertos del SEACE publicados por el OECE en el estándar OCDS, vía el [registro de Open Contracting](https://data.open-contracting.org/es/publication/135) | Mensual (el demo usa el corte al 02/10/2026) |
| Ubicación de distritos | [ubigeo-peru-aumentado](https://github.com/jmcastagnetto/ubigeo-peru-aumentado) (RENIEC/INEI, licencia MIT) | Estática |
| Bases de cada convocatoria | PDF que la empresa descarga del SEACE y sube a la app | Manual (el SEACE bloquea descargas automáticas) |

## 2. Ubicación en el mapa

- OCDS trae la **dirección de la entidad compradora** (departamento y distrito), **no el lugar de ejecución**.
  El mapa lo dice explícitamente.
- Se asignan coordenadas de distrito **solo si el nombre del distrito es único dentro de su departamento**
  (98 % de los casos). Si hay ambigüedad (p. ej. "San Miguel" existe en varias provincias), el punto se
  ubica en la capital del departamento y se dibuja con borde punteado.
- La **distancia** al domicilio de la empresa es en línea recta y solo se calcula cuando ambos puntos
  tienen precisión de distrito. Es orientativa: nunca excluye una convocatoria.

## 3. Fechas

En los datos abiertos el "periodo de ofertas" (`tenderPeriod`) coincide con el día de publicación, así que
**no es una fecha límite**. La única fecha del cronograma disponible es el **fin de consultas y
observaciones** (`enquiryPeriod.endDate`). La fecha de presentación de ofertas debe confirmarse en el SEACE.
Por defecto los plazos se calculan respecto a la fecha de corte de los datos; un interruptor permite
usar la fecha de hoy.

## 4. Compatibilidad empresa ↔ convocatoria

### 4.1 Criterios y pesos

| # | Criterio | Peso | Quién lo evalúa | Excluyente |
|---|---|---|---|---|
| 1 | Bienes/servicios vs. objeto de la contratación | 30 | IA | Sí |
| 2 | Actividad económica | 15 | IA | No |
| 3 | Cobertura geográfica | 15 | **Regla fija** | No |
| 4 | Capacidad económica vs. monto | 15 | **Regla fija** | No |
| 5 | Experiencia solicitada | 10 | IA | Sí |
| 6 | Requisitos técnicos y documentarios | 10 | IA | Sí |
| 7 | Otras condiciones (plazos, entrega, lugar) | 5 | IA | No |

**Reglas fijas** (no dependen del modelo):
- *Cobertura*: el departamento de la entidad está en la cobertura declarada → cumple; si no → no cumple
  (resta puntaje pero **no es excluyente**: la empresa puede ampliar su cobertura).
- *Capacidad*: valor referencial ≤ monto máximo → cumple; hasta 1.5× → debe acreditar (financiamiento o
  consorcio); más → no cumple. Sin valor publicado → sin información.

### 4.2 Estados y valores

| Estado | Valor | Significado |
|---|---|---|
| ✅ Cumple | 1.0 | Hay evidencia de que cumple |
| 📎 Debe acreditar | 0.6 | Probablemente cumple, pero debe demostrarlo con documentos |
| ❌ No cumple | 0.0 | Evidencia clara de que no cumple |
| ❔ Sin información | — | **No cuenta** (no se trata como incumplimiento) |

### 4.3 Fórmulas

```
Puntaje   = 100 × Σ(peso × valor) / Σ(pesos de criterios con información)
Confianza = Σ(pesos de criterios con información)          (los pesos suman 100)
```

### 4.4 Semáforo

- 🔴 **Rojo**: "no cumple" en algún criterio excluyente (objeto, experiencia o requisitos).
- 🟢 **Verde**: puntaje ≥ 70, confianza ≥ 60 % y ningún excluyente incumplido.
- 🟡 **Amarillo**: todo lo demás, incluida la información insuficiente.
- ⚪ **Gris**: aún no evaluada. Una convocatoria nunca se muestra como elegible sin evaluación.

### 4.5 Controles sobre la IA

- La IA (DeepSeek, modo JSON) debe devolver un estado y una **evidencia citada** por criterio.
- Cada respuesta se valida con Pydantic; si no cumple el esquema se reintenta y, si vuelve a fallar,
  se descarta (no se muestra nada inventado).
- El porcentaje lo calcula Python, no el modelo.

## 5. Requisitos desde las bases (PDF)

1. `pypdf` extrae el texto de cada página. Si el PDF es escaneado (sin texto) se avisa: haría falta OCR.
2. La IA lista requisitos con **categoría, página y una cita literal**.
3. **Verificación**: cada cita se busca en el texto real del PDF (sin tildes ni signos). Si aparece, el
   requisito queda verificado (y se corrige la página si hacía falta). Si no aparece, se muestra aparte como
   "no confiable" y **no** se usa para evaluar.

## 6. Precios históricos, entidades y proveedores

- Unidad de análisis: **ítem adjudicado** en soles, desde enero de 2024.
- "Contrataciones similares" = misma **categoría CUBSO** (catálogo oficial del Estado), opcionalmente
  del mismo departamento.
- Se muestran **mediana y rango P25–P75**, no promedios. Opcionalmente se excluyen atípicos: montos fuera
  de 3 rangos intercuartílicos en escala logarítmica.
- Siempre se muestran el **periodo analizado** y el **número de observaciones**; con menos de 10 se advierte.
- Los proveedores se agrupan por **RUC**. Se presentan como "proveedores adjudicados en contratos similares",
  no como competidores directos. Las personas naturales (RUC 10) se muestran enmascaradas.
- `numberOfTenderers` se presenta como **participantes registrados**, no como ofertas presentadas.
- Los precios pasados son referencia, no garantía.

## 7. Limitaciones conocidas

- Datos con ~6 semanas de atraso (publicación mensual). En producción se usaría la fuente diaria del SEACE.
- Sin lugar de ejecución ni fecha de presentación de ofertas en los datos abiertos.
- La IA no es 100 % determinista: la misma convocatoria puede variar algunos puntos entre evaluaciones
  (en pruebas, el mismo caso dio 94 % y 77 %, siempre en verde). Por eso se muestran la evidencia y la
  confianza, y cada resultado se guarda para no recalcularlo dentro de la sesión.
- Alertas y carpeta digital: no implementadas. La carpeta digital requiere almacenamiento seguro de
  documentos privados de la empresa, que no se debe improvisar.
