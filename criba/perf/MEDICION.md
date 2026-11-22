# Medición · rendimiento de la vista de vacante (CA5)

Fecha: 22-nov-2026. Autor del informe: sesión de medición (rol constructor).
Qué se mide: `GET /vacantes/{id}` con 500 candidatos puntuados, contra el
presupuesto de `SPEC.md`.

**Esta sesión mide y diagnostica. No optimiza.** No hay ni un cambio en `app/`,
`tests/` ni `migrations/`; lo único que se añade es `perf/` y una línea en
`.gitignore`. Lo que habría que cambiar está en §6, escrito y sin implementar.

## 1 · El presupuesto, citado

| Qué | Número | Fuente |
|---|---|---|
| Abrir vacante de 500 candidatos (servidor) | **p95 < 300 ms**, 0 llamadas al modelo | `SPEC.md` CA5 (RE8, `llamadas/2026-11-20-tomas.md` [04:06]) y la tabla «Rendimiento (números medibles)» |
| Cómo se verifica CA5 | «se mide el tiempo de respuesta del servidor en **50 peticiones**» | `SPEC.md` CA5 |
| Página visible en celular, buena red | < 2 s · **objetivo, no test automático** | tabla «Rendimiento (números medibles)» |
| Volumen de referencia | ~9.000 candidatos/mes, ~600 vacantes abiertas; solo Northstar activo en la v1 | tabla «Rendimiento», `docs/contexto.md`, §8 |

Dos restricciones de la spec acotan qué arreglos son admisibles, y por eso se
citan aquí y no en una nota al pie:

- **CA8**: «ninguno queda oculto ni colapsado». Paginar la lista o cargarla por
  tramos **no es una opción**: las 500 filas tienen que estar en la respuesta.
- **CA19**: la vista completa tiene que funcionar a 360 px de ancho.

## 2 · Entorno declarado

| Qué | Valor |
|---|---|
| Máquina | portátil Windows 11 (10.0.26200), Intel Core i7-12700H, 20 hilos lógicos, 15,7 GB de RAM |
| Servidor medido | uvicorn 0.54.0, **un (1) worker**, `http://127.0.0.1:8046`, ya en marcha al empezar la sesión |
| Base de datos | PostgreSQL **16.13** en contenedor, `localhost:5444`, base **`criba_perf`** (nunca `criba_dev` ni `criba_test`) |
| Driver | **pg8000 1.31.6** (Python puro; la elección está justificada en `pyproject.toml`: esta máquina bloquea el `.dll` de libpq de psycopg) |
| Pila | Python 3.13.11, FastAPI 0.165.0, Starlette 1.10.0, SQLAlchemy 2.1.9, Jinja2 3.1.6 |
| Match | encendido (`CRIBA_MATCH_ACTIVO=1`), activado solo para `northstar-health` (D7), proveedor en modo MOCK por omisión |
| Generador de carga | locust 2.47.0, en la **misma máquina** que el servidor |
| Datos | vacante 1 de Northstar con **500 postulaciones**, 499 con score; sembrados con `perf/sembrar_carga.py` |

**Dos cosas que el entorno hace optimista, declaradas antes de los números**
porque cambian la lectura del resultado:

1. **Cliente y servidor en la misma máquina.** No hay red, y el generador de
   carga le compite CPU al servidor. Con 20 hilos y una carga de 5 usuarios lo
   segundo es menor, pero no es cero.
2. **Los CV sintéticos son cortos.** Media **1.086 caracteres** (mín. 174, máx.
   1.370), 542.091 caracteres en total para las 500 filas. Un CV real en texto
   plano anda en 2.000-4.000 caracteres, o sea entre 2 y 4 veces más. Como el
   texto del CV entra entero en la respuesta (§4), **el resultado real sería
   peor que el medido, no mejor**. La extrapolación está en §5.4, marcada como
   extrapolación.

Un tercer sesgo, este en la dirección contraria, en §5.3: la siembra deja a casi
todos los candidatos de Northstar postulados a la vacante 1, y eso **esconde**
una de las cinco consultas.

## 3 · Los números reales

### 3.1 · Carga con locust, cliente contra el servidor de medición

Tres corridas. La del medio es la que pide el enunciado (`--csv
perf/resultados/antes`); las otras dos acotan por abajo y por arriba.
`wait_time` de 1 a 3 s entre peticiones del mismo usuario, que es un reclutador
abriendo vacantes y no una prueba de saturación.

| Corrida | Usuarios | Duración | Peticiones | Fallas | p50 | p95 | p98 | p99 | máx | req/s |
|---|---|---|---|---|---|---|---|---|---|---|
| `antes-1usuario` | 1 | 2 min | **55** | 0 | 69 ms | **110 ms** | 110 ms | 160 ms | 164 ms | 0,46 |
| `antes` | 5 | 1 min | 152 | 0 | 75 ms | **180 ms** | 290 ms | 320 ms | 341 ms | 2,57 |
| `antes-10usuarios` | 10 | 1 min | 280 | 0 | 78 ms | **220 ms** | 330 ms | 530 ms | 538 ms | 4,69 |

Tamaño medio de respuesta medido por locust: **1.597.568 bytes** (1,52 MiB) en
las tres corridas. Cero fallas: las 487 respuestas pasaron la verificación de
«200 y exactamente 500 filas renderizadas» del `locustfile`.

Por qué 1, 5 y 10 usuarios, y por qué 1 y 2 minutos: CA5 exige **50
peticiones**, y con un usuario y pausa de 1-3 s hacen falta dos minutos para
juntarlas (en un minuto salieron 30, por debajo del mínimo de la spec). Los 5
usuarios son la corrida de referencia: la v1 tiene una sola empresa activa y un
puñado de reclutadores (`app/plataforma/semilla.py` declara tres usuarios de
Northstar). Los 10 usuarios están para ver si el número se mueve, y se mueve: es
la única corrida donde algún percentil cruza el presupuesto.

Salida real de la corrida de referencia (`perf/resultados/antes_stats.csv`, con
el prefijo de la máquina quitado de las líneas de log):

```
Type     Name                    # reqs      # fails |    Avg     Min     Max    Med |   req/s
--------|---------------------|-------|-------------|-------|-------|-------|-------|--------
POST     /entrar                      5     0(0.00%) |    108      78     125    120 |    0.08
GET      /vacantes/{id}             152     0(0.00%) |     92      61     341     75 |    2.57
--------|---------------------|-------|-------------|-------|-------|-------|-------|--------
         Aggregated                 157     0(0.00%) |     92      61     341     75 |    2.66

Response time percentiles (approximated)
Type     Name                          50%    66%    75%    80%    90%    95%    98%    99%   100% # reqs
--------|-------------------------|--------|------|------|------|------|------|------|------|------|------
GET      /vacantes/{id}                 75     84     97    100    130    180    290    320    340    152

[perf] /vacantes/{id} = /vacantes/1 · usuario marcus · 500 filas esperadas · presupuesto p95 300 ms (CA5)
[perf] /vacantes/{id}: 152 peticiones, 0 fallas, p95 180 ms, presupuesto 300 ms → DENTRO de CA5
```

### 3.2 · Del lado del servidor, en proceso

CA5 dice «del lado del servidor», y locust cronometra del lado del cliente. Para
separarlos, `perf/perfil.py` repite la misma petición **dentro del proceso** con
el `TestClient` de Starlette: sin `loopback`, sin `accept` de uvicorn y sin
competencia del generador de carga. 40 muestras tras 5 de calentamiento.

| Escenario | Filas | Bytes | B/fila | Consultas | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|
| **CA5** · `marcus` en `/vacantes/1` | 500 | 1.597.568 | 3.195 | **5** | 62,7 ms | **109,1 ms** | 122,3 ms |
| control · hiring manager, `/vacantes/1` | 500 | 328.630 | 657 | 2 | 37,5 ms | 72,7 ms | 133,5 ms |
| control · fragmento de Match, 3 columnas | 500 | 138.238 | 276 | 4 | 51,5 ms | 67,7 ms | 138,3 ms |
| control · la misma vista con 4 filas | 4 | 83.727 | 20.931 | 5 | 30,5 ms | 45,0 ms | 101,0 ms |

El p95 en proceso (109 ms) y el p95 de locust con un usuario (110 ms) coinciden.
**La red local y uvicorn no aportan nada medible**: lo que se mide es la app.

Reparto por fases de la petición de CA5:

```
    fase         p50 ms   p95 ms   p99 ms    media  % del p50
    --------------------------------------------------------
    total          62.7    109.1    122.3     68.0       100%
    SQL            37.2     43.9     56.5     38.3        59%
    render          9.6     11.6     63.7     12.2        15%
    resto          16.1     19.8     59.6     17.5        26%
```

`resto` = total − SQL − render: ASGI, dependencias de FastAPI, lectura de la
cookie firmada y serialización del cuerpo de 1,5 MB.

## 4 · ¿Se cumple CA5?

**Sí, hoy y en esta máquina, con margen de ~2,7× en las condiciones literales de
CA5.**

| Condición | p95 | Presupuesto | Veredicto |
|---|---|---|---|
| CA5 literal: 55 peticiones secuenciales | 110 ms | 300 ms | **cumple** |
| Servidor en proceso, 40 muestras | 109 ms | 300 ms | **cumple** |
| 5 usuarios concurrentes, 1 worker | 180 ms | 300 ms | **cumple** |
| 10 usuarios concurrentes, 1 worker | 220 ms | 300 ms | **cumple** (pero p98 = 330 ms y p99 = 530 ms) |

La otra mitad del presupuesto —«0 llamadas al modelo»— la asercia CA4 en
`tests/match/test_vacante_no_espera.py`, que ya está en el repo. Esta medición es
consistente con él: las cinco consultas de la petición son lecturas, no hay
escrituras, y la suma de fases (SQL + render + resto) no deja hueco para una
llamada de red a un proveedor.

**Tres reservas sobre ese «sí»**, todas con número:

1. Con CV de largo realista el p50 sube ~20 ms y el cuerpo pasa de 1,5 a ~2,6 MB
   (extrapolación medida en §5.4).
2. A 10 usuarios el p98 ya está fuera (330 ms). CA5 habla de p95, así que
   formalmente no importa; a un reclutador al que le toca el p98 sí.
3. El presupuesto se cumple **gracias a** que la siembra esconde la quinta
   consulta (§5.3). En producción esa consulta cuesta ~16 ms hoy y crece con el
   padrón de la empresa, no con las 500 filas.

## 5 · El cuello de botella, con su evidencia

### 5.1 · Mover 500 filas anchas de Postgres a Python: 38 de los 63 ms

De los 62,7 ms del p50, **37,2 ms (59 %) son la fase SQL**. Y de esos 37,2 ms,
Postgres ejecuta **1,24 ms**. El resto es el camino de vuelta: el driver
`pg8000` decodificando filas en Python puro y SQLAlchemy construyendo objetos.

```
### Sondeo · cada consulta de la vista de CA5: la app contra Postgres

    consulta                                                     app   Postgres  fuera de PG
    ----------------------------------------------------------------------------------------
    candidatos_de_vacante · la lista de la vista              19.5ms     0.94ms          95%
    scores_de_vacante · los scores ya guardados               13.5ms     0.11ms          99%
    candidatos_sin_postular_a · el <select> de «añadir»        2.2ms     0.18ms          92%
    empresa_activada · la comprobación de D7/CA3               1.8ms     0.01ms         100%
    vacante · la cabecera de la página                         1.3ms     0.01ms          99%
    suma de las consultas de la petición                      38.3ms     1.24ms          97%
```

**El 97 % del tiempo de «la base de datos» no está en la base de datos.** Y el
desglose de la consulta grande, de dentro hacia fuera, dice de qué está hecho:

```
### Sondeo · los ~40 ms de «SQL» de la lista, de dentro hacia fuera

    1 · Postgres, Execution Time de EXPLAIN ANALYZE                  0.9 ms
    2 · driver pg8000, cursor crudo, fila completa                  19.1 ms
    3 · driver pg8000, solo las columnas que la lista muestra        8.7 ms
    4 · RepositorioEmpresa.candidatos_de_vacante (lo que corre)     24.9 ms

    fuera de Postgres: 24.0 ms de los 24.9 ms (96 %)
    atribuible al texto del CV en el cursor crudo: 10.5 ms
```

Las cuatro medidas son de **la misma lista de 500 filas**. Leídas como escalera:
0,9 ms los ejecuta Postgres; +18,2 ms los pone el driver al traer y decodificar
la fila entera; de esos 18,2 ms, **10,5 ms son solo la columna `cv_texto`**
(medida 2 contra 3); y +5,8 ms más los pone SQLAlchemy construyendo 500
`Candidato` y 500 `Postulacion`.

Y la columna que cuesta 10,5 ms **la lista no la muestra**: `_candidatos.html`
pinta `{{ fila.candidato.cv_texto|length }} caracteres`, es decir, un número. El
texto completo solo se usa para **precargar un `<textarea>` de edición por
fila**, dentro de un `<details>` cerrado que el reclutador casi nunca abre.

El mismo patrón en la segunda consulta: `scores_de_vacante` cuesta 13,5 ms en la
app y 0,11 ms en Postgres. Trae 499 filas `ScoreDeMatch` completas —con el JSONB
`razones`, que hoy la plantilla de la plataforma **no pinta**— para quedarse con
un `int` por candidato (`_scores_por_candidato` en `app/match/services/listado.py`
construye un `dict` y `_fila` usa `score.score`, `score.razones` y
`score.estado`; de los tres, la plantilla de la plataforma solo pinta `score`).

### 5.2 · El cuerpo de la respuesta: 1,52 MiB sin comprimir

```
    filas de la vacante 1: 500
    suma de `cv_texto` de esas filas: 542,091 caracteres
```

| Vista | Bytes | B/fila | Qué lleva por fila |
|---|---|---|---|
| `marcus` (reclutador) | 1.597.568 | 3.195 | nombre, score, contacto, CV **entero** en un `<textarea>`, etapa, fecha, 2 formularios |
| hiring manager | 328.630 | 657 | lo mismo sin score, sin `<textarea>` y sin formularios |
| fragmento de Match | 138.238 | 276 | nombre, score, fecha |

La diferencia entre la primera y la segunda fila es **1.268.938 bytes (79 % del
cuerpo)**, y es exactamente la columna de acciones de escritura: 542.091 bytes de
texto de CV más ~727.000 bytes de marcado de los dos formularios por fila
(`<details>`, `<form>`, `<label>`, `<textarea>`, dos botones, `hx-*`).

`app/fabrica.py` no monta ningún middleware de compresión, así que ese 1,52 MiB
viaja tal cual. Para CA5 da casi igual —el `loopback` no cobra—, pero la fila
«Página visible en celular, buena red: < 2 s» de la tabla de `SPEC.md` **se
decide aquí**: 1,52 MiB por una red móvil buena (~10 Mbit/s efectivos) son ~1,3 s
de transferencia antes de que el navegador empiece a construir 500 filas con 500
`<textarea>` y 1.000 formularios. Ese objetivo no tiene test automático y, con
este tamaño de respuesta, hoy no se cumpliría en un celular. **No es CA5, pero
está en la misma tabla.**

### 5.3 · La quinta consulta, la que esta medición casi no ve

`contexto_candidatos` (`app/plataforma/fragmentos.py`) llena el `<select>` de
«añadir un candidato» con `candidatos_sin_postular_a`, que trae **todos los
candidatos de la empresa que no están postulados a esta vacante, con su
`cv_texto` entero**.

```
### Sondeo · el <select> de «añadir un candidato», que CA5 no ve

    vacante 1:    7 filas en el <select>      2.0 ms
    vacante 2:  503 filas en el <select>     16.1 ms
    vacante 3:  503 filas en el <select>     16.0 ms
    candidatos de Northstar en la base de medición: 507
```

En la vacante 1 cuesta 2 ms **porque la siembra postuló a 495 de los 507
candidatos justamente ahí**, así que al `<select>` le quedan 7. En cualquier otra
vacante de la misma empresa cuesta 16 ms. Se ve también en el control de 4 filas
de §3.2: una página con 4 candidatos pesa 83.727 bytes y su consulta más cara es
esta (14,7 ms de 19,3 ms de SQL).

Esto **no escala con las 500 filas de CA5: escala con el padrón de la empresa**.
Northstar tiene ~2.000 candidatos en su histórico abierto (`SPEC.md` alcance 12),
unas 4 veces los 507 de aquí. Es el único número de esta medición que el entorno
hace parecer **mejor** de lo que será.

### 5.4 · Extrapolación: qué pasa con CV de largo realista

Marcada como extrapolación porque **no se midió**: salen de dos pendientes sí
medidas.

- Driver: 10,5 ms por 542.091 caracteres de CV ⇒ ~19 ms por MB de `cv_texto`.
- Cuerpo: 1 byte de respuesta por carácter de CV (va dentro del `<textarea>`).

Con CV de 3.000 caracteres de media (2,8× los de aquí, extremo bajo de un CV
real): `cv_texto` de la vacante ≈ 1,5 MB ⇒ **+~19 ms** en la fase SQL y **+~1,0
MB** en el cuerpo. El p50 pasaría de ~63 a ~82 ms, el p95 de ~109 a ~135 ms y el
cuerpo de 1,52 a ~2,5 MiB. **CA5 seguiría cumpliéndose; el objetivo de los 2 s en
celular se alejaría más.** Medirlo de verdad es una resiembra con otro largo de
CV, y es la primera cosa que haría la siguiente sesión de medición.

## 6 · Qué cambiaría, y qué número espero que mueva

Escrito, no hecho. El orden es por milisegundos por línea de diff.

| # | Cambio | Dónde | Número que espero mover | Base de la estimación |
|---|---|---|---|---|
| 1 | **No traer `cv_texto` en la lista** y cargar el editor de CV por HTMX cuando se abre el `<details>` | `_candidatos.html` + un método nuevo de lectura en `RepositorioEmpresa` | p50 **−11 ms** (SQL 19,5 → 8,7 ms) y cuerpo **−542 KB** (1,52 → ~1,00 MiB) | medidas 2 y 3 del sondeo de §5.1; suma de `cv_texto` de §5.2 |
| 2 | **No traer la fila `ScoreDeMatch` entera** para la lista: proyectar `(candidato_id, score, estado, razones)` en lugar de hidratar 499 objetos ORM | `RepositorioDeMatch.scores_de_vacante` | p50 **−8 a −11 ms** (13,5 → ~2-5 ms) | 13,5 ms app contra 0,11 ms de Postgres (§5.1); `razones` sí hará falta en PR-20, así que el ahorro es la hidratación, no el JSONB |
| 3 | **Comprimir la respuesta** (`GZipMiddleware`) | `app/fabrica.py` | cuerpo en el cable **1,52 MiB → ~150 KB** (HTML muy repetitivo); p95 del servidor **+5 a +15 ms** de CPU | no medido: es la razón de que sea el cambio nº 3 y no el nº 1. Es el único que mueve el objetivo de «< 2 s en celular» |
| 4 | **Quitar el `<select>` con el padrón entero**: buscador con `hx-get` en vez de 2.000 `<option>` | `_candidatos.html` + `candidatos_sin_postular_a` | **−14 ms** en toda vacante que no sea la 1, y deja de crecer con el padrón (hoy ~16 ms con 503 filas; ~60 ms proyectados con los ~2.000 de Northstar) | §5.3 |
| 5 | **Adelgazar el marcado por fila**: un solo formulario por fila en vez de dos | `_candidatos.html` | cuerpo **−~400 KB**; render **−3 a −5 ms** | 727 KB de marcado de formularios en §5.2; render 9,6 ms contra 4,4 ms del hiring manager |
| 6 | **Índice para la subconsulta de notas**: `(postulacion_id)` o invertir `ix_notas_empresa_postulacion` | migración | **0 ms hoy**; evita que la subconsulta pase de 0,001 ms a dominar cuando `notas_entrevista` crezca | el plan de §7, `SubPlan 1`: 500 `Seq Scan` sobre una tabla de 3 filas |
| 7 | **Driver**: medir la misma vista con `psycopg3` en binario | `pyproject.toml` | hipótesis: fase SQL **38 → 10-15 ms**. **Sin medir y bloqueado**: `pyproject.toml` documenta que esta máquina bloquea el `.dll` de libpq por política de control de aplicaciones | es una **decisión para un humano**, no un cambio que yo proponga a ciegas (§8) |

Con 1, 2 y 5 hechos —los tres que no necesitan ninguna decisión nueva— el p50
esperado baja de ~63 a ~38 ms y el p95 de ~109 a ~70 ms, y el cuerpo de 1,52 MiB
a ~600 KB. Eso devuelve el margen que §4 dice que se van a comer el largo real de
los CV y la concurrencia.

Lo que **no** propongo: paginar, colapsar o cargar la lista por tramos. CA8 lo
prohíbe explícitamente («ninguno queda oculto ni colapsado») y es la decisión de
producto de `llamadas/2026-11-20-tomas.md` [03:57]. El arreglo tiene que ser
«500 filas más baratas», no «menos de 500 filas».

## 7 · Lo que NO es el cuello de botella, aunque lo parezca

1. **No hay N+1.** Exactamente **5 consultas** por petición, las mismas 5 con 500
   filas que con 4 (`perf/perfil.py`, columna «consultas por petición»: `5 (min)
   … 5 (max)` en los dos casos; «sentencias repetidas dentro de una misma
   petición: ninguna»). La promesa que `app/match/services/listado.py` escribe en
   su docstring —«una consulta para toda la lista», F27— **se sostiene medida**.
   Es el sospechoso número uno de cualquier lista de 500 y aquí está descartado.

2. **Postgres no es el problema.** 1,24 ms de ejecución para las cinco consultas.
   Todo son aciertos de caché (`Buffers: shared hit`, cero `read`), sin disco y
   sin espera de bloqueo. **Añadir un índice hoy no movería el p95.**

3. **La subconsulta correlacionada de notas parece horrible y no cuesta nada.**
   El plan la ejecuta 500 veces con un `Seq Scan`:

   ```
                 SubPlan 1
                   ->  Aggregate  (cost=1.04..1.05 rows=1 width=8) (actual time=0.001..0.001 rows=1 loops=500)
                         Buffers: shared hit=500
                         ->  Seq Scan on notas_entrevista  (cost=0.00..1.04 rows=1 width=4) (actual time=0.000..0.000 rows=0 loops=500)
                               Filter: (postulacion_id = postulaciones.id)
                               Rows Removed by Filter: 3
   ```

   500 recorridos secuenciales de una tabla con **3 filas**: 0,001 ms por
   iteración. El índice `ix_notas_empresa_postulacion` es `(empresa_id,
   postulacion_id)` y la subconsulta solo filtra por `postulacion_id`, así que no
   lo puede usar — y da igual. Es **riesgo latente**, no cuello de botella: ver
   el cambio nº 6.

4. **El render de Jinja no es el problema.** 9,6 ms de 62,7 (15 %). Importa, pero
   no es donde está el tiempo: reescribir la plantilla sin tocar lo que se trae
   de la base sería trabajo por el 15 %.

5. **La red, uvicorn y el número de workers no son el problema.** El p95 en
   proceso (109 ms) y el p95 de locust con un usuario (110 ms) son el mismo
   número. Añadir workers subiría el techo de concurrencia —que a 10 usuarios ya
   se nota— pero no bajaría la latencia de una petición sola, que es lo que CA5
   mide.

6. **El modelo no está en este camino.** 0 llamadas al proveedor (CA4,
   `tests/match/test_vacante_no_espera.py`). La decisión de puntuar asíncrono y
   persistido (D16, RI2) **ya pagó**: lo que queda es un problema de lista, no de
   latencia de modelo.

En una frase: **el cuello de botella no es la base de datos ni el modelo; es la
cantidad de datos que esta vista mueve y pinta por fila** —el texto del CV y el
marcado de edición que la lista no necesita— y el precio en Python puro de
materializarlos.

## 8 · Lo que esta medición no cubre

1. **Driver alternativo.** No se midió `psycopg3`: no está instalado y
   `pyproject.toml` documenta por qué no se puede en esta máquina. Como es la
   palanca potencialmente más grande (§6 nº 7), queda como **decisión y medición
   para un humano**, no como conclusión de este informe.
2. **CV de largo realista.** Extrapolado en §5.4, no medido.
3. **El padrón de ~2.000 candidatos de Northstar.** La base de medición tiene 507
   candidatos de Northstar. §5.3 proyecta; no mide.
4. **Varios workers de uvicorn.** El servidor de medición corre con uno, que es
   lo que había al empezar la sesión.
5. **Celular de verdad.** La fila «< 2 s en celular» se diagnostica por tamaño de
   respuesta (§5.2); nadie midió un teléfono. La spec dice que es objetivo y
   medición manual, no test.
6. **La cola y el camino de escritura.** CA7 (CV → score en ≤ 10 min) no se tocó:
   esta sesión midió la lectura de la vista.

## 9 · Cómo repetir esto

Con el servidor de medición en marcha sobre `criba_perf` y `CRIBA_URL_BD`
apuntando ahí:

```
uv run --with locust python -m perf.sembrar_carga
uv run --with locust --with "urllib3>=2.2" locust -f perf/locustfile.py --headless \
    --host http://127.0.0.1:8046 --csv perf/resultados/antes --only-summary -u 5 -r 5 -t 1m
uv run --with locust python -m perf.perfil
```

`perf/sembrar_carga.py` es idempotente y determinista, y **aborta si
`CRIBA_URL_BD` no termina en `criba_perf`**:

```
cerrojo con criba_dev: SystemExit -> CRIBA_URL_BD apunta a
'postgresql+pg8000://criba:criba@localhost:5434/criba_dev' y esta siembra solo
corre contra 'criba_perf'. No se escribió nada.
```

Los CSV de locust no se versionan (`.gitignore`, con la misma forma que
`evals/resultados/`); los números reales están pegados en este archivo.

**Dependencias nuevas:** ninguna en `pyproject.toml`. `locust` y `urllib3` entran
por `uv run --with` solo durante la corrida, igual que en el comando del
enunciado. `perf/perfil.py` no usa nada que no esté ya instalado.

`uv run python -m poethepoet check` queda en verde con `perf/` dentro: 196
pasados, 1 xfailed.

### Un hallazgo que no es de rendimiento

La primera versión de `perf/sembrar_carga.py` contaba los scores con un
`select(func.count(…))` sobre `ScoreDeMatch`, y
`tests/match/test_aislamiento.py::test_ninguna_consulta_de_match_se_construye_fuera_del_repositorio`
la rechazó:

```
AssertionError: DML sobre `match_*` fuera de app/match/repositories/:
  perf\sembrar_carga.py:246: select(func.count(func.distinct(ScoreDeMatch.candidato_id)))
```

La regla (a) de PR-04 se enumera sobre **todo** el repositorio y sin lista
blanca, así que también alcanza a un script de medición — y hace bien: un
contador suelto sobre `match_scores` es una segunda puerta a los datos de Match,
y da igual que quien la abra sea un perfilador (D4, CA1). El conteo pasó a
`RepositorioDeMatch.scores_de_vacante` con `ContextoDeEmpresa.desde_la_vacante`.
Queda escrito aquí porque es evidencia de que el cerrojo de aislamiento funciona
contra código que nadie había previsto, que es justo para lo que se puso.
