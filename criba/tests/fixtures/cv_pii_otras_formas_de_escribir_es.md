# CV sintético · enfermería · español · el mismo dato, escrito de otra forma

**Este CV es sintético** (D3 modificado, D15, F12): nombre, contacto, dirección,
perfiles y referencias están inventados.

Es la fixture de los hallazgos **I1, I2 y M5** de la revisión de PR-08 (los tres
sobre **CA2** y los tres sobre uno de los seis datos de §1a: links a perfiles,
dirección y teléfono). Las cuatro fixtures anteriores escriben esos tres datos en
**una sola sintaxis** —el link siempre con `https://`, la dirección siempre en
formato estadounidense con el número delante, el teléfono siempre en grupos de
3-3-4—, así que prueban que el patrón reconoce **esa** forma de escribirlo y no
el dato. Aquí van las formas corrientes que faltaban:

- **el link a perfil como dominio pelado**, sin esquema y sin `www.`
  (`linkedin.com/in/…`, `github.com/…`), que es como se escribe un perfil en un
  CV de verdad;
- **la dirección en sintaxis española**, con el nombre de la vía delante y el
  número al final (`Calle Hidalgo 123`). La lista de sufijos del
  pseudonimizador ya nombra `Calle`, `Avenida` y `Carrera`, así que esta es la
  mitad del criterio que CA2 pide probar «en español» y que la fixture ES
  anterior probaba sobre sintaxis inglesa (`1200 Walnut Street`);
- **el teléfono en formato mexicano** (`81-1234-5678`, `+52 81 1234 5678`), que
  es el de la referencia y el que no cae en grupos de 3-3-4.

Es el mismo tipo de hueco que la primera fuga de la segunda ronda (el nombre
escrito sin acentos): la fixture escribía el dato del texto libre igual, carácter
por carácter, que el del campo.

Renata Solís Vega
renata.solis@ejemplo.test · +1 713 555 0122
https://www.linkedin.com/in/renata-solis-sintetica

## Perfil

Soy Renata Solís Vega, enfermera registrada (RN) con licencia vigente en Texas.
Seis años en urgencias pediátricas, los dos últimos como encargada de turno.

Vivo en Calle Hidalgo 123, Col. Centro, Monterrey, NL 64000, y cruzo a diario:
el turno de noche no me supone ningún problema de traslado.

Perfil: linkedin.com/in/renata-solis-sintetica · github.com/rvega88

## Experiencia

Urgencias pediátricas y triaje. Atiendo en español y en inglés sin intérprete.

## Referencias

Mateo Iriarte, supervisor de urgencias: 81-1234-5678, o al conmutador
+52 81 1234 5678, extensión 204.
