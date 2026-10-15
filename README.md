# Ayvens Ticket Agent

Agente para el hackathon Ayvens/Alenia/Ironhack: clasifica tickets de soporte
en 3 casos de uso (UC1 mapeo de códigos locales, UC2 reconciliación de
reportes mensuales, UC3 verificación de datos de vehículos/contratos),
verifica los hechos contra el sistema de registro con una consulta SQL
propuesta y aprobada por un humano, y publica la resolución con dos
aprobaciones humanas más (comentario y cambio de estado).

## Cómo correrlo

```bash
source .venv/bin/activate
pip install -r requirements.txt   # si falta algo: langgraph, python-dotenv, etc.
python demo/test_full_pipeline_all_ucs.py
```

Esto corre el flujo completo (routing → SQL → resolución → escalación →
comentario → estado) para un ticket de cada UC, con datos falsos. Pide
`GROQ_API_KEY` en `.env`.

## Arquitectura real

1. **Routing** (`src/agent/router_b.py`) — el LLM devuelve una distribución
   de probabilidad sobre los 3 UC, no una sola etiqueta. Dos chequeos
   deterministas en Python (`is_ambiguous`, `is_insufficient_information`)
   deciden si el ticket necesita revisión humana antes de seguir.
2. **Propuesta + aprobación + ejecución de SQL** (`src/agent/propose_sql.py`,
   `src/agent/sql_executor.py`, usados dentro de
   `demo/test_sql_approval_flow.py`) — el LLM propone una consulta SELECT
   contra el esquema real (hoy, uno simulado en `tests/mock_database.py`);
   se pausa con `interrupt()` de LangGraph esperando aprobación humana; si
   se aprueba, se ejecuta de verdad contra SQLite en memoria.
3. **Resolución** (`src/agent/generate_resolution_from_sql.py`) — genera el
   texto de resolución a partir del **resultado real** de la consulta, no
   de inferencia sobre el texto del ticket. Devuelve también
   `ready_to_close`: si queda alguna acción pendiente (nuestra o del
   solicitante), el caso no se cierra.
4. **Escalación** (`src/agent/decide_escalation.py`) — ladder de 3 niveles;
   nivel 3 (autoridad) es un placeholder, nunca se devuelve (no tenemos
   la regla real de Ayvens para eso todavía).
5. **Aprobación de comentario y de estado**
   (`src/agent/ticket_actions.py` + el patrón genérico en
   `src/agent/approval_flow.py`) — mismo patrón propose → pausa → aprobar/
   rechazar → ejecutar, reusado para las 2 aprobaciones restantes del
   contrato.
6. **Pipeline conectado** (`demo/full_pipeline_demo.py`, función
   `run_full_pipeline`) — encadena los 5 pasos anteriores para un ticket.
   `demo/test_full_pipeline_all_ucs.py` lo corre para los 3 UC.

## Estructura del repo

src/
├── llm_client.py # wrapper a Groq (hoy); cambia a Databricks cuando haya acceso
├── core/ # tipos compartidos (state.py) y definición de los 3 UC
├── agent/ # la lógica real: router_b, propose_sql, sql_executor,
│ # generate_resolution_from_sql, decide_escalation,
│ # approval_flow, ticket_actions
└── tools/ # EL CONTRATO oficial de herramientas (read_ticket,
# retrieve_similar_tickets, create_comment, update_status),
# con mocks en tools/mock/ y el switch en registry.py
# para apuntar a tools/alenia/ el día del hackathon
tests/
├── mock_database.py # tablas SQL falsas, ligadas a los tickets de prueba
├── mock_openproject.py # validación para las aprobaciones de comentario/estado
├── routing_test_tickets.py # 14 tickets de prueba para el router (3 tandas)
└── sample_tickets.py # usado por tools/mock/read_ticket.py — NO TOCAR

demo/
├── full_pipeline_demo.py # el pipeline conectado (función run_full_pipeline)
├── test_full_pipeline_all_ucs.py # ENTRY POINT principal — correr esto
├── test_sql_approval_flow.py # aprobación de SQL aislada
├── test_action_approval_flow.py # aprobación de comentario/estado aislada
└── test_rejection_flow.py # prueba el camino de rechazo en las 3 aprobaciones

archive/ # experimentos y versiones descartadas — no corren,
# quedan solo de referencia (ver “Historial” abajo)


## Pendiente de resolver en cuanto tengamos acceso real

Ver el documento aparte de investigación/checklist para el checkpoint.
Resumen de lo más urgente:

- **Dos capas de mock sin fusionar.** `src/tools/` es el patrón de contrato
  oficial (pensado para que, cambiando `PROVIDER` en `registry.py`, se
  conecte a Alenia sin tocar `agent/`). Lo construido esta madrugada
  (`tests/mock_openproject.py`, la ejecución de SQL) es una capa paralela
  que no pasa por ese registro todavía. Hay que fusionarlas: añadir la
  consulta SQL como una 5ª herramienta del contrato, y hacer que
  `ticket_actions.py` ejecute a través de `tools/registry.py` en vez de
  `mock_openproject.py` directamente.
- **No usamos LangChain**, solo LangGraph + llamadas directas a la API.
  Confirmar en el checkpoint si de verdad lo exigen; si sí, cambiar
  `llm_client.py` para pasar por `ChatDatabricks`/`ChatGroq`.
- **Umbrales de Router B sin calibrar** con tickets reales
  (`AMBIGUITY_MARGIN = 0.20`, `MIN_CONFIDENCE_THRESHOLD = 0.5`).
- **Esquema real de las tablas de Databricks desconocido** — todo lo de
  hoy corre contra `mock_database.py`, inventado.

## Limitaciones conocidas y documentadas (no son bugs, son decisiones)

- Un ticket con dos incidentes genuinamente distintos (dos filiales) no se
  divide — el sistema asume un ticket = un problema, igual que el contrato
  de herramientas del reto.
- Nivel 3 de escalación (autoridad) nunca se devuelve — no hay regla real
  de Ayvens para definirlo todavía.
- `tests/mock_database.py` no modela todas las cifras que un ticket puede
  mencionar (ej. UC2 no tiene el "conteo del controlador de negocio" como
  dato consultable) — por diseño, para no inventar datos que no existen.

## Historial (en `archive/`, no corren)

- `router.py`, `router_a.py` — versiones de routing descartadas en favor de
  `router_b.py` (probabilidades + detección de ambigüedad, probado contra
  14 tickets).
- `extract_signals.py`, `decide_verdict.py`, `generate_resolution.py`,
  `run_demo.py` — el primer pipeline, construido antes de confirmar (vía el
  PDF oficial) que el sistema real verifica hechos con SQL, no con
  inferencia de señales de texto.
- `compare_routers.py` — el experimento que demostró por qué se eligió
  Router B sobre Router A.