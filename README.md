# ticket-masters

Sistema que recibe un ticket (de OpenProject, de una tabla de Databricks o de un archivo), lo
procesa y devuelve la solucion esperada, para entregarla en Databricks y verla en una app visual.
Funciona en dos entornos con la misma logica: Databricks y local.

El diseno y las decisiones viven en el Claude Doc "Guia de requisitos - Alenia AI Ticketing
Challenge" (ver `docs/README.md`).

## Estructura

| Carpeta | Para que sirve |
| --- | --- |
| `core/` | Logica comun, escrita una sola vez |
| `src/` | Entorno Databricks: adaptadores y app desplegable |
| `src_local/` | Entorno local: adaptadores y app |
| `tests/` | Pruebas automaticas sobre lo determinista |
| `data/` | Ejemplos pequenos para pruebas; los datos grandes no se copian |
| `docs/` | Documentacion que viaja con el codigo |
| `runs/` | Registro de ejecuciones (solo se amplia; no se sube a Git) |

## Reglas de desarrollo

1. La logica se escribe una vez en `core`. `src` y `src_local` solo contienen lo que cambia con el entorno.
2. No existen versiones demo del flujo. Un ticket manual entra por la misma ruta que los demas; las
   pruebas son datos que se pasan al sistema real.
3. Cada modulo documenta su entrada, su salida y quien lo llama.
4. El modelo no borra ni sobrescribe nada. Las consultas de investigacion son solo de lectura.
5. La aprobacion se pide antes de ejecutar una respuesta. En pruebas es automatica, por el mismo
   camino de codigo, y queda registrada como automatica.
6. En la plataforma de Alenia solo se lee. Las escrituras en OpenProject quedan apagadas hasta tener un
   OpenProject local.
7. El registro de ejecuciones solo se amplia. Las pruebas no escriben en la tabla oficial
   `solutions_emails_sent`.
8. Las credenciales nunca van en el codigo ni en Git: se leen de `.env` o del vault de Databricks.

## Preparar el entorno (Mac)

    cd ticket-masters
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-dev.txt
    cp .env.example .env     # y rellena los valores

El entorno virtual se crea en tu Mac, no en este repositorio de Git.
