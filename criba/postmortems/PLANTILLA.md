# Postmortem · <nombre corto del incidente>

Se copia este archivo a `postmortems/AAAA-MM-DD-nombre-corto.md` y se rellena
dentro de las 48 h del cierre del incidente. El orden del incidente está en
`RUNBOOK.md`: contener → entender → arreglar → verificar → **postmortem**.

> **Sin culpables.** Este informe habla de sistemas, no de personas. La pregunta
> no es «quién lo rompió» sino «qué hizo que fuera fácil romperlo y difícil
> verlo». Si el informe termina en el nombre de una persona, el informe está sin
> terminar: el nombre de una persona no se puede arreglar, y un sistema sí.
>
> Los nombres **sí** aparecen en una sola columna: la de **dueño de una acción**.
> Ahí no son responsabilidad del fallo, son quien se compromete al arreglo.
>
> **Nada de datos reales de cliente, ni texto de CV, ni datos de un candidato**
> (D3 modificado, D15, F12). Para hablar de una fila se usa su identificador
> (`trabajo_id`, `empresa_id`, `vacante_id`). Si el incidente **fue** una fuga de
> datos, lo que se describe es el alcance —cuántos, de qué empresa, por qué
> superficie—, nunca el dato.

- **Fecha del incidente:**
- **Duración:** detectado <hh:mm> · contenido <hh:mm> · cerrado <hh:mm>
- **Quién escribe este informe:**
- **Severidad:** (y la fila de `docs/fallas.md` que lo había previsto, si la hay: F#)
- **Entorno:** producción / staging / desarrollo

---

## 1 · Qué pasó

Tres o cuatro frases, en lenguaje de usuario y no de código. Qué dejó de
funcionar, para quién, y cómo se enteró alguien.

Si hubo **datos de una empresa visibles para otra**, va en la primera frase: es el
requisito número uno del cliente (D4, CA1) y no es un detalle de implementación.

## 2 · Línea de tiempo

Todas las horas en UTC, para que cuadren con los logs y con el `dia` de las vistas
de `metricas`. Una fila por hecho **observable**, no por hipótesis.

| Hora (UTC) | Qué pasó | Cómo se sabe |
|---|---|---|
|  | <el cambio, el pico, el despliegue> | <línea de log, consulta, captura> |
|  | <alguien lo nota> |  |
|  | **contenido** (qué se apagó exactamente) |  |
|  | <hipótesis que sobrevivió a su refutación> |  |
|  | **arreglado** |  |
|  | **verificado** (qué medición, con qué número) |  |

## 3 · Impacto

Números, no adjetivos. «Mucho» no se puede comparar con el siguiente incidente.

- **Usuarios afectados:** qué empresas, cuántos reclutadores.
- **Datos:** cuántos scores mal calculados, no calculados o visibles donde no
  debían. De `metricas.scores_por_vacante` y `metricas.trabajos_por_estado`.
- **Gasto:** contra el techo de D12, si lo hubo.
- **Lo que NO se vio afectado**, y por qué se puede afirmar: es la mitad del
  impacto que nadie escribe y la única que acota el susto.

## 4 · Causa raíz

La causa **del sistema**, no la acción de una persona. Dos preguntas, y las dos
se contestan:

- **¿qué lo hizo posible?** (el mecanismo: la variable que se lee una vez por
  proceso, la consulta sin filtro de empresa, el `GRANT` incondicional…)
- **¿qué lo hizo invisible?** El tiempo entre que empezó y que alguien lo notó es
  tan parte de la causa raíz como el fallo. Si el detector era «alguien mira»,
  decirlo.

Si hay **más de una** causa, van las dos. Un incidente con una sola causa suele
ser un incidente mal entendido.

## 5 · Qué funcionó

No es cortesía: es la lista de lo que **no** hay que tocar al arreglar, y la que
dice qué controles valieron lo que costaron.

- qué detector avisó, y cuánto tardó;
- qué contención funcionó a la primera;
- qué test, qué rol de base de datos o qué decisión previa acotó el daño.

## 6 · Acciones

Cada una con **dueño y fecha**, y cada una verificable por alguien que no estuvo
en el incidente. «Tener más cuidado» no es una acción. «Añadir un test que falla
si <el mecanismo de la causa raíz> vuelve» sí lo es.

| # | Acción | Tipo | Dueño | Para cuándo | Hecha |
|---|---|---|---|---|---|
| 1 |  | detectar |  |  | [ ] |
| 2 |  | prevenir |  |  | [ ] |
| 3 |  | contener más rápido |  |  | [ ] |

Los tres tipos están a propósito y en ese orden: **detectar** antes que
**prevenir**, porque un fallo que se ve a los dos minutos cuesta menos que uno
prevenido a medias; y **contener más rápido**, porque el siguiente incidente va a
ser otro.

Si una acción depende de una decisión de otra persona, se nombra a quién decide y
la pregunta abierta (`PLAN.md` §9, `docs/fallas.md`, `docs/arquitectura.md`), y la
acción es «conseguir la decisión», con dueño.

## 7 · Qué queda sin arreglar

Lo que se decide **no** hacer, con el motivo. Un riesgo aceptado y escrito es
información; uno aceptado en silencio es el próximo postmortem.
