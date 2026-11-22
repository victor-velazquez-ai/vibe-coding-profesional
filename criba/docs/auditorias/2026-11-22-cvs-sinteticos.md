# Auditoría de CVs sintéticos · 22-nov-2026 · la frontera de PR-08

> **Qué es este archivo y por qué existe.** El código, los tests y dos fixtures de
> PR-08 citan «la auditoría de CVs sintéticos del 22-nov-2026» como la fuente de
> dos reglas del pseudonimizador, y esa fuente **no tenía archivo en el
> repositorio**: solo vivía en el cuerpo del PR. Es el hallazgo M4 de la tercera
> ronda de revisión de PR-08, y CLAUDE.md es explícito: «cita siempre la fuente:
> archivo y minuto de la llamada, o el ID de la decisión». Así que la fuente se
> registra aquí, con la evidencia que **ya está** en el repositorio, y las citas
> apuntan a este archivo.
>
> Se escribe **después** de la auditoría, en la tercera ronda del mismo PR. No es
> acta de una llamada con el cliente ni una decisión nueva: es el registro de una
> revisión interna sobre fixtures **sintéticas**, sin un dato real de nadie.

## Qué se auditó

`pseudonimizar(candidato)` (`app/match/services/pseudonimizador.py`) con los
**siete primeros tests de PR-08 en verde**, o sea con CA2 dada por cumplida: los
seis datos de §1a fuera del cuerpo enviado, en español y en inglés, por el camino
de escritura real y con dos empresas.

El método: **escribir CVs sintéticos nuevos en los que la PII del texto libre no
fuera idéntica, carácter por carácter, a la de los campos estructurados**. Las
cuatro fixtures de entonces la escribían igual en los dos sitios, así que
probaban la **igualdad exacta** y no el **parecido**, que es lo que un CV real
trae.

## Qué encontró · dos datos de §1a saliendo enteros al proveedor

| # | Fuga | Qué salía | Por qué los siete tests no la veían |
|---|---|---|---|
| 1 | **el nombre sin acentos** | el candidato se llama «José Ángel Treviño» en los campos y **firma su CV «Jose Angel Trevino»**: no caían ni el nombre completo ni sus partes | la pasada de valores conocidos comparaba el valor **tal cual** —sin mayúsculas, pero con acentos— |
| 2 | **la foto adjunta** | `[Foto adjunta: sofia_ramirez_2026.png]`: no es una URL, así que el patrón de enlaces no la tocaba, y el nombre que lleva dentro va pegado con guion bajo, así que el borde `(?!\w)` tampoco casaba. **Dos datos de §1a en la misma línea** | el único camino cubierto para la foto era el de la URL (`![Foto de perfil](https://…)`) |

Las dos son de **CA2** y las dos son de los seis datos que §1a **sí** nombra
(nombre, fotos), así que la regla 1.5 de `PLAN.md` no admitía `xfail` en ninguna:
o se arreglaban, o PR-09 no se habilitaba.

## Evidencia, toda dentro del repositorio

- **las fixtures sintéticas** que la auditoría escribió:
  `tests/fixtures/cv_pii_sin_acentos_es.md` y `cv_pii_foto_adjunta_es.md`, las dos
  con la declaración de «este CV es sintético» que la guardia de PR-03 exige (F12);
- **los tests**, escritos en rojo antes del arreglo:
  `test_el_nombre_escrito_sin_acentos_en_el_cv_tampoco_sale_en_el_cuerpo_enviado`,
  `test_el_nombre_del_archivo_de_la_foto_adjunta_no_sale_en_el_cuerpo_enviado` y
  `test_las_dos_fugas_tampoco_salen_por_el_camino_real_ni_cruzan_de_empresa`
  (`tests/match/test_pseudonimizacion.py`), más la guardia
  `test_la_fixture_de_cada_fuga_trae_de_verdad_el_dato_que_se_escapa`, que falla si
  alguien «limpia» una fixture y le quita el dato (F2, F15);
- **los commits**: `test: las dos fugas de CA2 que la auditoria encontro (PR-08)`
  (rojo), `estructural: aislar como se reconoce un valor conocido (PR-08)` y
  `comportamiento: las dos fugas de CA2 de la auditoria del 22-nov (PR-08)`;
- **la salida en rojo y en verde**, en `docs/prs/PR-08.md` (bloques 4 a 6 bis).

## Qué cambió por esto

1. **un valor conocido se reconoce sin acentos**, igual que ya se reconocía sin
   mayúsculas (`_tolerante_a_acentos`), con la tabla de variantes calculada al
   importar desde el bloque latino de Unicode y no escrita a mano (F34); y el
   texto entra normalizado a **NFC**, que es la otra mitad de lo mismo;
2. **un patrón para el nombre de archivo de una imagen**, con su marca propia
   `[foto]` y detrás del patrón de enlaces, para que una URL que acaba en `.jpg`
   caiga entera como enlace y no por su último segmento.

Ninguna de las dos amplía CA2 ni decide la pregunta abierta 2 de `SPEC.md`: §1a
dice «nombre» y dice «fotos», y las dos fugas son esos dos datos escritos de otra
forma.

## La lección, que es lo que hace útil este archivo

**Una fixture que escribe la PII del texto libre idéntica a la de los campos
prueba la igualdad exacta, no el dato.** Vale para cualquier PR que vuelva a tocar
esta frontera, y se confirmó una segunda vez: la **tercera ronda de revisión de
PR-08** (`docs/prs/PR-08.md` §«Tercera ronda») encontró cuatro huecos del mismo
tipo —el link como dominio pelado, la dirección en sintaxis española, el teléfono
en formato mexicano y el nombre con una letra que no se descompone—, todos porque
cada fixture escribía su dato en **una sola sintaxis**.
