# 03 · Scoring asíncrono: la página nunca espera al modelo

## Contexto

Tomás se contradice dentro de la misma llamada sobre la latencia:

> **[01:32]** «Lo que sí es que tiene que ser instantáneo: llega el CV y ya tiene su score. En tiempo real.»

> **[01:53]** «Sí, o sea… idealmente. Aunque, bueno, siendo honesto, los reclutadores revisan en la mañana lo que llegó en la noche. Si se tarda unos minutos, nadie se va a dar cuenta. Lo que no puede pasar es que la página se trabe esperando.»

Lo único firme es la última frase. El requisito de latencia exacto sigue abierto (delta P7).

Con ~9.000 candidatos nuevos al mes ([04:06]) y vacantes de 500+ candidatos ([00:16]), calcular scores al abrir la página no es viable.

## Criterio de aceptación

- [ ] El score se calcula fuera del ciclo de la petición HTTP y se guarda en Postgres; la vista de la vacante solo lee valores ya guardados.
- [ ] Abrir una vacante nunca dispara una llamada al modelo de forma sincrónica.
- [ ] Un candidato recién llegado y todavía sin score se muestra en un estado explícito ("calculando"), no como score 0 ni como error, y no bloquea el render del resto.
- [ ] Si el proveedor del modelo está caído o lento, la vacante abre igual, con los scores que ya existan (delta RI10).
- [ ] Está medido y documentado el tiempo real entre "llega el CV" y "el score está disponible", para poder responder P7 con un número.

Fuente: `llamadas/2026-11-20-tomas.md` [01:32], [01:53], [04:06]. Delta: N8, RE7, C2, RI2, RI10.
