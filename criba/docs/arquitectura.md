# Arquitectura de Criba Match v1

Arquitectura decidida por Víctor (21-nov-2026). Este documento la registra y la cuestiona; no la cambia.
Fuentes: `SPEC.md`, `docs/decisiones.md` (D1-D6), `llamadas/2026-11-21-cambios-decisiones.md` (D3 modificado, D7-D23), `llamadas/2026-11-20-tomas.md` (minutos entre corchetes) e `issues/02`.

## 1. El diagrama

```
Navegador (Jinja2 + HTMX) ── cookie de sesión ──> FastAPI: routers → services → repositories ── Postgres (+ Alembic)
                                                    └─ MatchService (pseudonimiza, tope de tokens, timeout, reintentos, MOCK) ── proveedor de modelos
                                                    └─ logs JSON con request_id y empresa_id
```

Match es un módulo dentro de la plataforma actual: misma app, mismo login, mismo stack (D1, D2).

## 2. Los seis componentes

**Navegador · Jinja2 + HTMX**
Responsabilidad: mostrar la lista de la vacante con score y tres razones, y el cambio a orden por fecha con un clic (D9, CA8). Responsive desde 360 px, con el estilo actual (D22, CA19).
Interfaz: recibe HTML renderizado en el servidor (página completa o fragmento HTMX); envía peticiones con la cookie de sesión.
Depende de: FastAPI. No habla con nada más; no hay JSON de Match hacia el cliente ni estado en el navegador.
Si se cae: no aplica (es el cliente). Si falla el fragmento HTMX, el fallback es la recarga de la página completa.

**FastAPI en tres capas · routers → services → repositories**
Responsabilidad: routers traducen HTTP (sesión, rol, parámetros) y renderizan; services tienen las reglas (quién ve qué, orden, recálculo, activación por empresa); repositories son el único acceso a datos.
Interfaz: recibe petición HTTP con cookie de sesión; devuelve HTML. Entre capas se pasan objetos de dominio, nunca filas crudas ni `Request`.
Depende de: Postgres y, solo en el camino asíncrono, de MatchService.
Si se cae: no hay Match ni plataforma. Es el componente sin redundancia del diagrama.

**Postgres 16 + Alembic**
Responsabilidad: verdad única. Tablas de negocio existentes más las de Match: scores con sus razones, estado «sin score» con motivo (CA13), cola de trabajos, auditoría por score (hash del CV, versión del prompt, versión del modelo, fecha — sin texto del CV, D15/CA15) y contador de gasto del mes (D12).
Interfaz: recibe consultas desde repositories; devuelve filas. Alembic recibe migraciones versionadas en el repo.
Depende de: nada dentro del sistema.
Si se cae: la vacante no abre. No hay degradación posible: los scores ya calculados viven aquí (CA4) y no hay caché.

**MatchService**
Responsabilidad: todo lo que pasa antes y después de hablar con el proveedor. Comprueba las tres condiciones de D3 modificado (pseudonimización, proveedor con retención cero, empresa con anexo firmado) y la activación por empresa (D7, CA3); pseudonimiza nombre, correo, teléfono, dirección, links y fotos (CA2); aplica tope de tokens, timeout y reintentos; consulta el techo de costo antes de gastar (CA10); escribe score, razones o motivo de «sin score», y la fila de auditoría. En modo MOCK no sale de la red: es lo que usan los dobles de CA3, CA4, CA6 y CA10.
Interfaz: recibe un trabajo de la cola (`empresa_id`, `candidato_id`, `vacante_id`, idioma del reclutador por D11); devuelve score 0-100 + tres razones, o estado «sin score» con motivo. Nunca devuelve cero (CA13).
Depende de: Postgres (cola, techo de costo, persistencia) y el proveedor.
Si se cae: no se calculan scores nuevos; los candidatos se acumulan en «Pendientes de score» y la alerta de pendientes con más de 60 min lo delata (CA7). Las vistas siguen funcionando.

**Proveedor de modelos**
Responsabilidad: devolver el score y las razones del par CV pseudonimizado + descripción de la vacante (D13). Elección de Víctor, acotada a proveedores con retención cero y no entrenamiento verificados por escrito por Priya antes de producción (N4 acotada, §1b).
Interfaz: recibe el payload pseudonimizado y el idioma pedido; devuelve la respuesta del modelo. Se registra su versión en cada auditoría (D15).
Depende de: nada nuestro. Es el único punto fuera de la infraestructura de Criba.
Si se cae: CA6. El trabajo se reintenta y luego vuelve a la cola; la vacante responde 200, el candidato queda en «Pendientes de score» y el reclutador no ve ningún error ([01:53]).

**Logs JSON**
Responsabilidad: poder reconstruir qué pasó con un score sin exponer datos. `request_id`, `empresa_id`, decisión tomada, latencia, versión de modelo y prompt.
Interfaz: recibe eventos; devuelve nada al usuario.
Depende de: nada. Escritura que nunca bloquea la respuesta.
Si se cae: se pierde observabilidad, no funcionalidad. Pero se pierde también evidencia para SOC 2 de marzo (`docs/contexto.md`), así que es una caída que hay que ver.

## 3. El recorrido de una request

Sofia, reclutadora, abre una vacante de 500 candidatos y los ve ordenados por fit score:

1. **Navegador** pide la vista de la vacante con su cookie de sesión. La sesión está atada a una empresa (`docs/contexto.md`).
2. **Router**: resuelve la sesión → usuario, rol y `empresa_id`. Comprueba el rol: reclutador y admin pasan; un hiring manager recibe 403 aquí mismo (D10, CA18). No consulta datos.
3. **Service**: pide al repositorio los candidatos de esa vacante con su score. Aplica las reglas: orden por score por defecto, «Pendientes de score» como sección de arriba con su fecha, nadie oculto, y el parámetro de orden por fecha si viene (D9, CA8). Decide si hay Match para esa empresa (D7). **Cero llamadas al proveedor** (CA4): esta ruta ni toca MatchService.
4. **Repository**: una sola consulta con `empresa_id` inyectado, no recibido. Devuelve filas de una empresa, siempre.
5. **Router** renderiza el fragmento Jinja2; HTMX lo intercambia. El p95 de servidor debe quedar por debajo de 300 ms (CA5, [04:06]).
6. **Logs**: una línea con `request_id`, `empresa_id`, vacante, orden aplicado y latencia.

Con Sofia **en Meridian** el recorrido se detiene conceptualmente en el paso 3: Meridian no firmó el anexo de subprocesador, así que Match está apagado para ellos y la vista se renderiza sin score ni orden por score (D7, CA3). El recorrido completo, hoy, es el de una reclutadora de Northstar. Lo anoto porque el ejemplo del boceto no es ejecutable en la v1, y el sitio donde se resuelve esa diferencia —el service, no el router ni la plantilla— es una decisión de arquitectura, no un detalle.

En paralelo, el camino de escritura: llega un CV nuevo → se encola un trabajo → un ejecutor toma MatchService → pseudonimiza, llama al proveedor, guarda score y auditoría. La vacante nunca espera a esto (D16, CA7).

## 4. Dónde vive el aislamiento entre empresas

En la capa de repositories, y en un único punto de acceso a datos de Match que **exige** `empresa_id` y lo toma del contexto de la petición (o del trabajo de la cola), no de un parámetro de la URL ni de un argumento que cada llamador pueda olvidar. Los routers nunca construyen consultas; los services piden por nombre de negocio.

En un solo lugar por tres razones: (a) Tomás lo pidió así de forma explícita —«eso va con test y en un solo lugar del código» → «eso» ([03:25], [03:29])—; (b) sin un único punto no se puede escribir el test de CA1 que falla cuando alguien añade una consulta sin `empresa_id`, y sin ese test el aislamiento es una convención, no un control; (c) es lo primero que mira SOC 2 en marzo y un lugar es auditable, cuarenta no. Un fallo aquí es un incidente de seguridad, no un bug (D4, [03:03]).

## 5. Lo que cuestiono de este boceto

1. **Falta la cola y su ejecutor como componentes de primera clase.** En el dibujo MatchService cuelga de FastAPI, pero D16 y CA7 exigen scoring fuera de la request. Escenario: la carga inicial de CA20 —~2.000 candidatos del histórico más las tres vacantes de la demo— corriendo el 10-ene dentro del proceso web; las llamadas al proveedor compiten con los 120 reclutadores activos y el p95 de 300 ms de CA5 se cae justo en la semana de la demo. La cola, su ejecutor y su reintento son componentes, no un detalle de MatchService.
2. **El techo de costo no cabe dentro de MatchService.** D12 es un techo mensual para toda la plataforma, o sea estado compartido. Escenario: dos ejecutores en paralelo durante la carga inicial, cada uno con su propio contador; los dos se creen al 70 % y el mes cierra por encima de 1.500 USD sin que la alerta del 80 % se haya emitido nunca (CA10 pasaría en un test de un solo proceso). El contador tiene que ser transaccional en Postgres y leerse antes de cada llamada.
3. **El `empresa_id` del camino asíncrono no está resuelto.** En la request lo da la cookie; en el ejecutor no hay cookie. Escenario: el trabajo de recálculo por CV nuevo toma la empresa del candidato y nadie revalida la activación; entra un CV de Meridian y se emite una llamada al proveedor por una empresa sin anexo firmado, que es exactamente lo que CA3 prohíbe. El `empresa_id` debe venir del propio registro de la cola y la comprobación de D7 debe vivir en el mismo punto de acceso a datos, no en el router.
4. **La pseudonimización debería ser una frontera, no un método dentro de un servicio grande.** CA2 pide un test que falle si el cliente del proveedor se invoca sin pasar por el pseudonimizador; eso solo es sostenible si el cliente del proveedor no acepta otra cosa que un payload ya pseudonimizado. Escenario: enero, presión de demo, alguien añade un segundo prompt para re-puntuar y llama al cliente directo porque es más corto. El test de CA2 pasa para el camino viejo y el CV con nombre sale igual.
5. **Los logs son una superficie de salida de datos y el boceto los trata como telemetría.** `issue 02` ya los nombra. Escenario: timeout del proveedor, el cliente HTTP registra el cuerpo de la petición por defecto, y queda texto de CV de Northstar en los logs de la plataforma. Está pseudonimizado, pero D3 modificado autorizó esa salida bajo tres condiciones y un archivo de log no cumple ninguna; D15 además dice que el texto del CV no se guarda. Hace falta la regla explícita: ni cuerpo de la petición ni respuesta del modelo en logs, y un test que lo sostenga.

## Preguntas abiertas que esta arquitectura añade

1. ¿Qué tecnología de cola? Postgres como cola alcanza para ~9.000 candidatos/mes y evita un componente nuevo, pero no está decidido y afecta a CA7.
2. ¿Dónde corre el ejecutor con 20 h/semana de desarrollo (D5)? Un proceso más que desplegar y vigilar no es gratis.
3. ¿El modo MOCK es solo de test o también un interruptor de producción para cortar gasto a mano? Son dos cosas distintas con el mismo nombre en el boceto.
