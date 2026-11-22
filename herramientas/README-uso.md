# `uso_sesiones.py`: cuánto costó tu sesión (y cuánto leyó)

Tu agente casi no gasta en lo que **escribe**: gasta en lo que **lee**, una y otra vez. En cada llamada al modelo vuelve a leer todo el contexto: el prompt de sistema, las herramientas, tu `CLAUDE.md`, tu instrucción y todo lo que ya pasó en la sesión. Esta herramienta te lo muestra con números de tus propias sesiones.

Solo usa la biblioteca estándar de Python, así que no hay nada que instalar.

## 1. Guarda una sesión

```bash
claude -p "tu tarea" --output-format stream-json --verbose > sesion.jsonl
```

Cada línea del archivo es un evento de la sesión: cada llamada al modelo (con sus tokens), cada herramienta y el resultado final (con el costo).

## 2. Mídela

```bash
python -I herramientas/uso_sesiones.py sesion.jsonl
```

Para una carpeta entera (busca todas las `.jsonl`, también en subcarpetas):

```bash
python -I herramientas/uso_sesiones.py capturas/
```

> **Tip:** si comparas dos formas de pedir lo mismo, nombra las corridas `vibe-01`, `vibe-02`… y `pro-01`, `pro-02`…. La herramienta las agrupa sola (`vibe`, `pro`) y te da promedios, mínimos y máximos por grupo.

## 3. Lee el informe

**Por sesión:**

| Columna | Qué significa |
|---|---|
| Llamadas | Cuántas veces se llamó al modelo; entre paréntesis, las de subagentes. |
| Tokens leídos | Entrada + escritura de caché + lectura de caché: todo lo que el modelo tuvo que leer, sumando todas las llamadas. |
| de caché | Qué parte de lo leído ya estaba en caché. Es más barato, pero se paga en cada llamada. |
| Escritos | Tokens de salida, incluido el pensamiento. |
| Costo | El costo que reporta Claude Code al terminar la sesión. |
| Duración | Tiempo real, de pared. |
| Read (relecturas) | Lecturas con la herramienta `Read`, y cuántas repitieron un archivo ya leído. |
| Subagentes | Cuántos subagentes lanzó la sesión. |

**Por grupo**, además de totales y promedios:

| Columna | Qué significa |
|---|---|
| Leídos:escritos | Cuántos tokens leyó por cada token que escribió. |
| Contexto 1ª llamada | Lo que el agente carga **antes de leer tu código**: sistema, herramientas, `CLAUDE.md` y tu instrucción. Se vuelve a leer en cada llamada. |
| Contexto por llamada | El promedio del hilo principal. |
| Permisos denegados | Intentos bloqueados por tus reglas de permisos. |

**¿En qué se fue el dinero?** separa el costo en cuatro partes:
- leer caché;
- escribir caché;
- entrada;
- salida.

La columna **Costo de LEER** suma las tres primeras.

> **Verifica:** la última columna, **Precio entrada implícito**, debe salir **igual** en todas las sesiones de un mismo modelo. Si sale igual, el desglose cuadra con el costo real. Si varía, la herramienta te avisa con una línea `ALERTA`.

## 4. Opciones

| Opción | Para qué |
|---|---|
| `--md` | Tablas en Markdown, para tu reporte o tu `PR`. |
| `--salida uso.md` | Escribe el informe en un archivo UTF-8. Úsalo en Windows en lugar de `> uso.md`: en PowerShell 5 esa redirección guarda el archivo en UTF-16. |
| `--json` | Todo en JSON, para tus propios análisis. |
| `--detalle` | Qué archivos releyó cada sesión y cuánto leyeron sus subagentes. |
| `--agrupar carpeta` | Agrupa por carpeta en vez de por prefijo. `ninguno` no agrupa. |
| `--ratio-salida N` | Si un modelo no cobra la salida a 5 veces la entrada. |

## 5. Cómo lo calcula (y sus límites)

- **Totales:** salen del evento final `result` de la sesión: `modelUsage` y `total_cost_usd`. Incluyen los subagentes y las llamadas internas pequeñas que hace el propio Claude Code.
- **Llamadas, herramientas y relecturas:** se cuentan en los mensajes del modelo. Cada mensaje llega partido en varias líneas, así que se deduplica por su `id`. Los tokens de salida que trae cada línea son parciales, por eso la salida solo se reporta en total.
- **Sesiones reanudadas** (`--resume`): Claude Code reporta el costo **acumulado** desde la sesión original. Si la corrida anterior está entre los archivos que le pasas, la herramienta la resta. Si no, te avisa.
- **Desglose del costo:** usa la estructura de precios de lista:
  - leer caché = 0.1× la entrada;
  - escribir caché = 1.25× (dura 5 minutos) o 2× (dura 1 hora);
  - salida = 5× la entrada.

  El precio de entrada lo calcula con tus datos: costo ÷ tokens ponderados.
- **Con suscripción (Pro o Max):** no pagas ese costo por sesión. Es el equivalente a precio de API, y sirve para **comparar** formas de trabajar.
- **Duración:** si existe un archivo `.ts` junto a la `.jsonl` (lo genera nuestro `capture.sh` con la hora de llegada de cada línea), se usa ese. Si no, se usa la mayor entre la duración que reporta Claude Code y lo que abarcan las marcas de tiempo.
- **Relecturas:** solo cuentan la herramienta `Read`. En JSON tienes además `lecturas_shell`, una heurística para `cat`, `Get-Content` y similares.
- **Archivos omitidos:** una `.jsonl` vacía, o que no es una sesión de Claude Code, aparece en "Notas" como omitida. No rompe el informe.

> **Regla:** antes de decidir "uso el modelo barato" o "lanzo más agentes en paralelo", mídelo. El costo que importa no es el de una corrida: es el de **un resultado que puedes defender**.
