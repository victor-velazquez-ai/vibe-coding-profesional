# Cambios propuestos a `docs/decisiones.md` · 2026-11-21

Fuente única de este documento: **correo de Tomás Reyes del 21-nov-2026** (respuesta a las preguntas abiertas del delta del 20-nov), decidido por él con Priya Shah (privacidad) y Dana (customer success). Las referencias `§n` son el número de respuesta de ese correo.

No se edita `docs/decisiones.md`. Aquí se **propone** el cambio y se aplica por PR. Aprueban Priya Shah (privacidad y D3) y Tomás Reyes (alcance); Dana lo lee. Fecha comprometida: §25 «Este viernes» → **27-nov-2026** (a confirmar, el correo no da la fecha).

---

## 1. Cambio a una decisión vigente

### D3 — se modifica 🔴

- **Texto vigente (kickoff 12-nov, Priya Shah):** «los CVs y los datos personales de los candidatos **no salen de la infraestructura de Criba**. Ningún tercero los procesa. Es un compromiso contractual con los clientes enterprise y un control de SOC 2.»
- **Decisión nueva (§1):** «CV completo con nombre: NO. Sí se puede mandar a un proveedor externo si (a) antes de enviar se quitan nombre, correo, teléfono, dirección, links a perfiles y fotos; (b) el proveedor firma retención cero y no entrenamiento con nuestros datos (Priya lo verifica por escrito antes de producción); (c) cada empresa activa Match explícitamente y firma el anexo de subprocesador. Northstar ya lo firmó; Meridian todavía no. Priya aprueba el cambio a D3 por PR.»

**Texto propuesto para D3:**

> **Datos de candidatos:** los datos personales directos del candidato no salen de la infraestructura de Criba. El texto del CV puede enviarse a un proveedor externo de modelo **solo si** se cumplen las tres condiciones: (a) antes del envío se eliminan nombre, correo, teléfono, dirección, links a perfiles y fotos; (b) el proveedor tiene por escrito retención cero y no entrenamiento con datos de Criba, verificado por Priya Shah **antes** de producción; (c) la empresa cliente activó Match explícitamente y firmó el anexo de subprocesador. Sin las tres, no se envía nada.

Esto resuelve la contradicción **C1** del delta del 20-nov y el issue `01`.

---

## 2. Propuestas del delta que quedan anuladas o acotadas

| Del delta 20-nov | Qué pasa | Fuente |
|---|---|---|
| **N3** — «el CV se manda completo al modelo, sin recortar ni anonimizar» | **Anulada.** El CV se envía pseudonimizado. | §1 «CV completo con nombre: NO» |
| **RE4** — «el CV se manda completo, con nombre, sin recortar» | **Anulado**, mismo motivo. | §1 |
| **N4** — «la elección del proveedor la decide Víctor» | **Sigue vigente, pero acotada:** solo proveedores que firmen retención cero y no entrenamiento, verificado por Priya antes de producción. | §1(b), §17 |

---

## 3. Decisiones nuevas a añadir (no contradicen nada vigente)

| ID propuesto | Decisión | Fuente |
|---|---|---|
| D7 | **Activación por empresa:** Match se enciende empresa por empresa, con anexo de subprocesador firmado. Northstar firmado; **Meridian no** → Match apagado para Meridian. Solo Northstar hasta la demo. | §1(c), §8 |
| D8 | **Formato del score:** porcentaje 0-100 + tres razones cortas. **Sin semáforo** en la v1 (el rojo parece descarte). | §9, §24 |
| D9 | **El score ordena, no decide.** Orden por score por defecto, con un clic se vuelve al orden por fecha; los candidatos sin score van en sección aparte **arriba**, nunca ocultos. | §11; confirma N1 del delta |
| D10 | **Hiring managers:** en la v1 no ven nada de Match. | §13 (cierra P2 / issue `07`) |
| D11 | **Idioma de la explicación:** el del reclutador, vía `usuarios.idioma` (es/en), que ya existe y ya tiene la UI en los dos idiomas. | §14 (cierra P3 / issue `08`) |
| D12 | **Techo de costo:** 1.500 USD/mes para toda la plataforma, alerta al 80 %. Al llegar al techo los nuevos quedan «pendientes»; nunca se sigue gastando. | §6 (cierra P5 / issue `05`) |
| D13 | **Entradas del score:** solo el CV y la descripción de la vacante. Nada de notas de entrevista. Cada candidato se puntúa contra las vacantes a las que **aplicó**, no contra todas. | §7, §21 |
| D14 | **El prompt es de Criba.** Criterios por empresa, fuera de la v1. | §22, §24 |
| D15 | **Borrado:** máximo 7 días. La auditoría de cada score guarda hash del CV, versión del prompt y versión del modelo; **no** el texto del CV. | §17 (issue `10`) |
| D16 | **Latencia:** score listo como máximo 10 min después de que llega el CV; más de una hora es un problema real. La vacante abre sin esperar al modelo, nunca. | §5 (cierra C2 / issue `03`) |
| D17 | **Demo 15-ene:** tres vacantes de Northstar en Texas (enfermería ~500, administración ~120, TI ~60), manejada por Dana desde su celular. Debe verse lista ordenada, score y razones. | §4 (cierra P8 / issue `11`) |
| D18 | **Criterio de calidad:** 10 vacantes cerradas y anonimizadas de Northstar; en ≥8 de 10, el candidato que contactaron primero queda entre los 5 primeros del score. Lo juzgan Dana y dos reclutadoras de Northstar. | §3, §16 |
| D19 | **No hay plan B con modelo propio.** Si D3 no cambiaba, no había Match. | §2 |
| D20 | **Ley 144 de NY:** el abogado responde por escrito el **10-dic-2026**. Hasta entonces, demo solo con vacantes de Texas. Aviso al candidato y auditoría de sesgo quedan fuera de la v1, como riesgo abierto. | §10 (issue `06`) |
| D21 | **Acceso de staff a Match:** se reusa `auditoria_accesos`, que ya existe. Extiende D6 a scores y explicaciones. | §18 |
| D22 | **Soporte móvil:** iPhone y Android recientes, Safari y Chrome, desde 360 px de ancho. Sin diseño nuevo: Match sigue el estilo responsive actual. | §19 |
| D23 | **Recálculo:** automático cuando el candidato sube un CV nuevo. Al cambiar la vacante **no** se recalcula solo: botón «recalcular vacante» para el admin de la empresa, máximo una vez al día por vacante. | §12, §24 (cierra P10) |

---

## 4. Tensión que este cambio deja abierta

En la llamada del 20-nov, [02:14]: «Probamos con un proveedor recortando cosas y el score salía malísimo.» La v1 va exactamente en esa configuración: CV recortado (sin nombre, correo, teléfono, dirección, links ni fotos) contra un proveedor externo.

No es una contradicción entre dos decisiones — Tomás eligió, con Priya, privacidad sobre calidad de score — pero sí deja un supuesto sin verificar: **que el score recortado sea suficientemente bueno**. El control es D18: si no se alcanza 8 de 10, la decisión vuelve a Tomás y Priya antes del 15-ene, no después. Dos salidas posibles en ese caso, ninguna decidida hoy: aflojar la pseudonimización con autorización de Priya, o aceptar un score peor en la demo.
