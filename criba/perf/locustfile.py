"""Carga del SLO de CA5: `marcus` abriendo la vacante 1 de 500 candidatos.

    uv run --with locust --with "urllib3>=2.2" locust -f perf/locustfile.py --headless \
        --host http://127.0.0.1:8046 --csv perf/resultados/antes --only-summary \
        -u 5 -r 5 -t 1m

El escenario sale de `SPEC.md` y de nada más:

- **CA5** («dada esa misma vacante de 500 candidatos, cuando se mide el tiempo de
  respuesta del servidor en 50 peticiones, el p95 es menor que 300 ms») fija la
  petición: `GET /vacantes/{id}` con 500 filas, y el número mínimo de muestras.
- La tabla de «Rendimiento (números medibles)» repite el presupuesto —p95 < 300 ms
  y 0 llamadas al modelo— y es de donde sale `PRESUPUESTO_MS`.
- **CA4** («abrir la vacante no llama al modelo») es la razón de que este archivo
  no monte ningún doble de proveedor: si abrir la vacante llamara al modelo, esto
  mediría la latencia del modelo. Lo que mide es la vista con scores ya guardados.
- El usuario es **`marcus`, reclutador de Northstar** (`app/plataforma/semilla.py`),
  porque es el rol del que habla CA5 («cuando un reclutador la abre») y el único
  rol que ve la vista completa: el hiring manager no ve Match (CA18) y el staff de
  Criba es de solo lectura. Es además el rol con `puede_escribir`, que es el que
  la plantilla carga con más HTML por fila.

**Lo que esto no mide.** Locust cronometra del lado del cliente: incluye el
`loopback`, el `accept` de uvicorn y la lectura del cuerpo completo. El p95 «del
lado del servidor» de CA5 se separa en `perf/perfil.py`, que cronometra dentro
del proceso. Los dos números van juntos en `perf/MEDICION.md`: si se parecen, la
red local no es el problema.

El `wait_time` no es decorado: sin pausa esto dejaría de ser «un reclutador
abriendo una vacante» y pasaría a ser una prueba de saturación, que no es el
número que pide la spec.
"""

from __future__ import annotations

import os

from locust import HttpUser, between, events, task

VACANTE = int(os.environ.get("PERF_VACANTE", "1"))
USUARIO = os.environ.get("PERF_USUARIO", "marcus")
# La semilla de desarrollo: la contraseña de cada usuario es su nombre + '1234'.
CONTRASENA = os.environ.get("PERF_CONTRASENA", f"{USUARIO}1234")
FILAS_ESPERADAS = int(os.environ.get("PERF_FILAS", "500"))
PRESUPUESTO_MS = 300

RUTA_VACANTE = f"/vacantes/{VACANTE}"
# Un nombre con plantilla y no la URL cruda: así el informe tiene una sola línea
# para la vista aunque mañana se midan varias vacantes.
NOMBRE = "/vacantes/{id}"
MARCA_DE_FILA = 'data-testid="fila-candidato"'
MARCA_DE_LOGIN = 'name="contrasena"'


class ReclutadorAbreLaVacante(HttpUser):
    """Entra una vez y abre la vacante, como quien revisa su cola del día."""

    wait_time = between(1, 3)

    def on_start(self) -> None:
        """Una sesión por usuario simulado: la cookie firmada de la plataforma.

        El login va fuera de las estadísticas de la vista a propósito —tiene su
        propia línea en el informe— porque `verificar_contrasena` cuesta lo que
        cuesta un hash de contraseña y no es parte del presupuesto de CA5.

        `allow_redirects=False` para que el `303` a la vacante **no** se siga
        aquí: si se siguiera, cada arranque de usuario descargaría la página de
        1,5 MB dentro de la línea `/entrar` y la mezcla de las dos cosas haría
        ilegibles los dos números. Un login correcto es `303`; uno incorrecto
        devuelve `401` con el formulario otra vez (`_con_error`).
        """
        with self.client.post(
            "/entrar",
            data={"usuario": USUARIO, "contrasena": CONTRASENA, "destino": RUTA_VACANTE},
            name="/entrar",
            allow_redirects=False,
            catch_response=True,
        ) as respuesta:
            if respuesta.status_code != 303 or MARCA_DE_LOGIN in respuesta.text:
                respuesta.failure(f"login devolvió {respuesta.status_code}, se esperaba 303")
                raise RuntimeError(
                    f"Sin sesión: {USUARIO!r} no entró ({respuesta.status_code}). "
                    "¿La base de medición tiene la semilla de la plataforma?"
                )

    @task
    def abrir_vacante(self) -> None:
        """La petición del SLO, con el cuerpo verificado.

        Verificar las 500 filas en cada respuesta es parte de la medición y no un
        lujo: una vista que respondiera 200 con la lista vacía —o una redirección
        a `/entrar` por sesión caída— daría un p95 excelente y mediría otra cosa.
        """
        with self.client.get(RUTA_VACANTE, name=NOMBRE, catch_response=True) as respuesta:
            if respuesta.status_code != 200:
                respuesta.failure(f"{respuesta.status_code}, se esperaba 200")
                return
            filas = respuesta.text.count(MARCA_DE_FILA)
            if filas != FILAS_ESPERADAS:
                respuesta.failure(f"{filas} filas renderizadas, se esperaban {FILAS_ESPERADAS}")


@events.test_start.add_listener
def _declarar(environment, **_: object) -> None:
    print(
        f"[perf] {NOMBRE} = {RUTA_VACANTE} · usuario {USUARIO} · "
        f"{FILAS_ESPERADAS} filas esperadas · presupuesto p95 {PRESUPUESTO_MS} ms (CA5)"
    )


@events.quitting.add_listener
def _veredicto(environment, **_: object) -> None:
    """El veredicto de CA5 en la salida de la corrida, no en la cabeza de nadie.

    `--csv` deja los percentiles en un archivo; esto deja escrito, al lado de los
    números, si el presupuesto de la spec se cumplió y si hubo fallas. No cambia
    el código de salida: decidir que la medición «falla» es del informe.
    """
    stats = environment.stats.get(NOMBRE, "GET")
    p95 = stats.get_response_time_percentile(0.95)
    print(
        f"[perf] {NOMBRE}: {stats.num_requests} peticiones, {stats.num_failures} fallas, "
        f"p95 {p95} ms, presupuesto {PRESUPUESTO_MS} ms → "
        f"{'DENTRO' if p95 is not None and p95 < PRESUPUESTO_MS else 'FUERA'} de CA5"
    )
