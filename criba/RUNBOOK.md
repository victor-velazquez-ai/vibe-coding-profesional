# RUNBOOK · Criba Match

Qué hacer cuando algo va mal, en el orden en que hay que hacerlo. Está escrito
para **el staging local con la configuración de producción**, que es el entorno
que existe hoy; cuando haya un despliegue de verdad cambian las direcciones y los
nombres de los procesos, no el orden.

> Un recordatorio que vale para todo el documento: este sistema **no tiene
> guardia** (D5, R1, supuesto 4 de `docs/fallas.md`), y **quién atiende la alerta
> de pendientes >60 min fuera del horario de Víctor sigue sin decidir** (pregunta
> abierta 4 de `docs/fallas.md`, pregunta abierta 1 de ADR-001: la decide Tomás).
> Hasta que eso se decida, el detector de un ejecutor muerto es que alguien mire.

## El orden

**contener → entender → arreglar → verificar → postmortem**

El orden importa y es el único punto no negociable del documento. Las dos formas
de equivocarse son conocidas:

- **entender antes de contener**: cada minuto de diagnóstico con el incidente
  abierto son CVs saliendo de Criba, gasto contra el techo de D12 o scores
  escritos en la empresa equivocada. Contener primero **no** es arreglar: es
  dejar de sangrar;
- **arreglar antes de entender**: un arreglo sobre una hipótesis no verificada
  cambia el síntoma y borra la evidencia. Si no se puede decir qué causó el
  incidente, no se puede decir que esté arreglado.

«Verificar» es una medición, no una sensación: el mismo número que delató el
incidente, otra vez, después del arreglo. Y el postmortem se escribe **siempre**,
también cuando el incidente duró cuatro minutos
(`postmortems/PLANTILLA.md`).

---

## 1 · Contener

### Apagar Match entero

Match tiene un interruptor global, `CRIBA_MATCH_ACTIVO` (PR-05, R6·I5). Apagado:

- `montar` no monta los endpoints bajo `/match`;
- `encolar` **no toca la base de datos**: ni una fila, ni una consulta;
- el bucle del ejecutor no corre;
- y la vista de vacante de la plataforma **sigue respondiendo 200**, con la lista
  de candidatos de siempre y sin columna de score. Apagar Match no apaga Criba.

```bash
# En staging: quitar la línea de staging/staging.env (o ponerla en 0) y reiniciar
# los dos procesos. Ctrl+C en cada uno y:
poe staging-app
poe staging-ejecutor
```

**Hay que reiniciar el proceso, siempre.** `ajustes_match()` es
`lru_cache(maxsize=1)`: las cuatro variables de Match se leen **una vez por
proceso** (`app/match/configuracion.py`). Exportar la variable en otra terminal,
editar `staging.env` o cambiarla en el gestor de secretos **no cambia nada** en un
proceso ya arrancado. Lo mismo vale para volver al MOCK (abajo) y para la
activación por empresa.

### Apagar Match para una empresa, sin apagarlo para las demás

`CRIBA_MATCH_EMPRESAS_ACTIVADAS` es la lista de slugs activados (D7, CA3). Se
quita el slug de la lista y se reinicia. Con la lista vacía no hay ninguna empresa
activada, que es su valor por omisión: un entorno nuevo nace apagado.

### Cortar el gasto sin apagar Match

`CRIBA_MATCH_PROVEEDOR=mock` y reiniciar. El MOCK no sale del proceso y no gasta
nada; los scores que devuelve son fijos, así que **esto no es una degradación
aceptable para el usuario**, es una forma de parar el grifo mientras se decide.
Que el MOCK sea o no un interruptor legítimo de producción es **pregunta abierta
3** de `docs/arquitectura.md` (y la 4 de ADR-001). Quien lo use en producción
antes de que se decida tiene que dejarlo escrito en el postmortem.

### Qué NO es contener

Borrar filas de `match_trabajos` a mano, o reiniciar el contenedor de Postgres.
Lo primero destruye la evidencia del postmortem y lo segundo no apaga nada: los
trabajos están persistidos (ADR-001 §Decisión 1) y siguen ahí al volver.

---

## 2 · Entender

### Dónde están los logs

| Proceso | Archivo | Qué trae |
|---|---|---|
| web | `staging/logs/app.jsonl` | una línea por vista de vacante (`match.listar_vacante`) |
| ejecutor | `staging/logs/ejecutor.jsonl` | una línea por **trabajo cerrado** (`match.trabajo_cerrado`) y las del adaptador del proveedor |

Una línea por objeto JSON. El directorio sale de `CRIBA_LOG_DIR`
(`staging/staging.env`) y su contenido está **ignorado por git**: son la salida de
una corrida, y su retención es pregunta abierta de F12 (decide Priya).

Lo que hay en una línea de trabajo cerrado: `trabajo_id`, `empresa_id`,
`vacante_id`, `estado`, `motivo` y `ms`. Lo que **no** hay, y no es un olvido:
nada del candidato —ni id, ni nombre, ni correo, ni score, ni texto de CV— y
**ninguna traza de excepción** (F12, D15, CA1 «ni log suyo»). Si el diagnóstico
necesita saber por qué falló un trabajo concreto, el `motivo` del log y la columna
`motivo` de su fila en `match_trabajos` dicen el tipo del fallo; el texto del CV no
está en ningún log y no va a estarlo.

```bash
# los trabajos que terminaron en error, con su motivo
grep '"estado": "error"' staging/logs/ejecutor.jsonl

# cuánto tardó el proveedor en las últimas llamadas
grep 'proveedor=claude_cli' staging/logs/ejecutor.jsonl | tail -20
```

### Entrar a la base como `agente_metricas`

Es el rol del agente: `SELECT` sobre las dos vistas de `metricas` y **nada más**.
No puede leer `candidatos`, `usuarios`, `match_scores` ni `match_trabajos`, ni
escribir en ninguna tabla. Se usa para mirar números durante un incidente sin
tener delante un solo dato de un candidato.

```bash
docker exec -it criba-staging-db \
  psql "postgresql://agente_metricas:agente_metricas_staging_local@localhost:5432/criba_staging"
```

```sql
-- cuántos scores por vacante y día, con los ceros y los «sin score» aparte
SELECT * FROM metricas.scores_por_vacante ORDER BY dia DESC, vacante_id;

-- la cola por día, estado y motivo: aquí se ve un montón de `error` de golpe
SELECT * FROM metricas.trabajos_por_estado ORDER BY dia DESC, n DESC;

-- y la comprobación de que el rol es el que se cree que es:
SELECT * FROM candidatos;   -- ERROR: permiso denegado (42501)
```

El rol lo crea `staging/roles.sql` (los roles son del clúster, no de la base) y el
permiso sobre `metricas` lo da la migración `0002_metricas_staging.py`, condicionado
a que el rol exista. La contraseña de arriba es un valor de una máquina local; en
producción sale del gestor de secretos (F19).

### Pedirle hipótesis a tu agente

Cuando el síntoma no es obvio, el prompt es este, literal:

> **dame 3 hipótesis y cómo refutar cada una**

Tres y no una: una sola hipótesis se confirma sola, porque uno busca lo que
espera encontrar. Y «cómo refutar» y no «cómo confirmar»: lo que hace útil a una
hipótesis es que exista una medición capaz de tumbarla. Si las tres hipótesis se
refutan con la misma consulta, no eran tres.

Pégale el contexto que ya tienes: las líneas de log relevantes **tal cual**, los
números de las vistas de `metricas` y qué cambió en el último despliegue. Nunca un
CV ni datos de un candidato (D3 modificado, D15, F12): si hace falta hablar de una
fila, se habla de su `trabajo_id`.

---

## 3 · Arreglar

Con la hipótesis que sobrevivió a su refutación, y nada más. Si el arreglo es
código, va por PR con su test, como todo lo demás (`PLAN.md` §4: el test falla
antes del cambio). Si el arreglo es de operación —una variable, un reinicio, un
rol— va al postmortem con dueño y fecha.

Si durante el arreglo aparece una segunda causa, se vuelve al paso 1 con el
incidente nuevo. Dos causas en un arreglo son dos arreglos.

---

## 4 · Verificar

El mismo número que delató el incidente, medido otra vez:

```bash
poe staging-humo    # marcus abre su vacante con score; sofia recibe 404
```

Y, según lo que fuera:

- **trabajos atascados**: `metricas.trabajos_por_estado` sin `pendiente` viejos
  (CA7: nada por encima de 60 min);
- **scores que no llegan**: `metricas.scores_por_vacante` creciendo en el día de
  hoy;
- **aislamiento**: la vacante de una empresa con la sesión de la otra, 404 y sin
  nada del candidato ajeno en el cuerpo. Es lo que `poe staging-humo` mide.

Volver a encender Match es volver a poner `CRIBA_MATCH_ACTIVO=1` y reiniciar. Se
enciende **después** de verificar, no antes.

---

## 5 · Postmortem

Siempre, y dentro de las 48 h. Se copia `postmortems/PLANTILLA.md` a
`postmortems/AAAA-MM-DD-nombre-corto.md`. **Sin culpables**: si el informe
termina en el nombre de una persona, el informe está sin terminar.

---

## Apéndice · levantar el staging desde cero

El orden, y por qué es ese:

```bash
poe staging-arriba     # 1 · contenedor criba-staging-db (5455) + migraciones como DUEÑO
poe staging-sembrar    # 2 · datos sintéticos de app/plataforma/semilla.py
poe staging-app        # 3 · el proceso web, en el 8001
poe staging-ejecutor   # 4 · el ejecutor, en otra terminal
poe staging-humo       # 5 · el E2E de humo contra lo que acabas de levantar
```

1. **las migraciones las corre el dueño**, nunca `criba_app`: `criba_app` no tiene
   `CREATE` en ningún esquema y un `ALTER TABLE` suyo falla con permiso denegado.
   Es a propósito: así el staging prueba el rol que la app usa de verdad;
2. `staging/roles.sql` crea `criba_app` y `agente_metricas` **al inicializar el
   volumen**. El guion es idempotente, así que sobre un volumen ya inicializado se
   puede volver a correr:
   ```bash
   docker exec -i criba-staging-db \
     psql -U criba -d criba_staging -f /docker-entrypoint-initdb.d/10-roles.sql
   ```
   Hace falta, por ejemplo, después de una migración que añada una tabla si las
   privilegios por omisión no estaban puestos cuando se creó;
3. el **ejecutor va en su propio proceso**, y eso es una diferencia con producción
   que está declarada: ADR-001 §Decisión 2 dice «el ejecutor corre en el proceso
   web» y lo deja como **cambio preparado, no hecho**. El staging lo corre aparte
   para poder medir T1 —el p95 de la vista con la cola trabajando— y para poder
   pararlo con Ctrl+C sin tirar la app. El razonamiento completo está en el
   docstring de `app/match/comandos/ejecutor.py`;
4. **todo el dato del staging es sintético** (`app/plataforma/semilla.py`, D3
   modificado, D15, F12). Es la única forma en que la regla 1.7 de `PLAN.md`
   permite encender Match con el proveedor real.

Para empezar de cero: `docker compose -f docker-compose.staging.yml down -v` y
volver al paso 1. Se lleva el volumen del staging y **solo** el del staging: el
Postgres de desarrollo y de tests es otro contenedor, en otro puerto
(`docker-compose.yml`, `criba-db`, 5434).

## Fuentes

- `docs/adr/ADR-001.md` (§Decisión 1 y 2, disparadores T1-T5, preguntas abiertas)
- `docs/arquitectura.md` §2 (componente «Logs JSON»), §4, §5.3, §5.5
- `docs/fallas.md` F11, F12, F16, F19, F23
- `docs/decisiones.md` D3 modificado, D5, D7, D12, D15, D16
- `SPEC.md` CA1, CA3, CA7, CA16
- `PLAN.md` §4 (estructural contra comportamiento), regla 1.7
