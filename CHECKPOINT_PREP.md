# Qué investigar/confirmar y qué pruebas correr en cuanto tengamos acceso real

## Preguntas para hacer en el checkpoint (09:30)

1. ¿El stack exige LangChain explícitamente, o LangGraph cuenta como parte válida?
2. ¿Esquema real de las tablas (`MD_LOCALVALUE_T`, `FLEET_REPORT`, `CONTRACT`,
   `VEHICLE`, `CF_SUBSIDIARIES_T`, etc.)? Nombres de columna, tipos, y si existe
   alguna tabla con el "conteo del controlador de negocio" para UC2 — hoy no
   existe en ningún lado, ni real ni simulado.
3. ¿El modelo del endpoint compartido es fijo o hay elección? ¿Mistral existe
   de verdad en el catálogo?
4. ¿Cómo se conecta `create_comment`/`update_status` en la práctica — API REST
   directa de OpenProject, o algo que Alenia ya da envuelto?
5. ¿Un ticket con dos incidentes distintos se debe dividir, o marcarlo para
   revisión humana (lo que hacemos hoy) es aceptable?
6. ¿Hay algún criterio real para escalación de nivel 3 (autoridad)?
7. ¿Cuántos tickets reales vamos a tener disponibles para calibrar antes de
   la presentación? (esto decide qué tan agresivo podemos ser con las
   pruebas estadísticas de abajo — con pocos tickets, algunas no alcanzan).

## Pruebas estadísticas a correr en cuanto tengamos tickets reales

Esto es lo que normalmente se salta por falta de tiempo, y es justo lo que
nos puede dar ventaja — convertir "elegimos 0.20 porque sonaba razonable" en
"elegimos 0.20 porque lo medimos".

1. **Tamaño de muestra mínimo.** Antes de confiar en cualquier número medido
   (accuracy, tasa de ambigüedad), calcular cuántos tickets reales hacen
   falta para que el intervalo de confianza sea razonablemente estrecho
   (regla simple: con ~30-40 tickets ya se puede estimar una proporción con
   margen de error aceptable; con menos de 15, cualquier número es ruido).

2. **Barrido de umbrales con matriz de confusión** (el método que ya
   documentamos, ahora ejecutable). Para cada ticket real: correr Router B
   una sola vez, guardar los scores crudos, y etiquetar a mano si
   debería haber ido a revisión humana o no (ground truth). Después, SIN
   volver a llamar al LLM, probar una grilla de valores candidatos
   (`AMBIGUITY_MARGIN` de 0.05 a 0.40, `MIN_CONFIDENCE_THRESHOLD` de 0.3 a
   0.7) y para cada combinación calcular falsos positivos (marcó ambiguo
   sin serlo) y falsos negativos (no marcó ambiguo siéndolo). Elegir el
   punto que minimiza falsos negativos primero (son los caros), aceptando
   más falsos positivos (son baratos: solo una aprobación humana de más).

3. **Prueba de McNemar (Router A vs Router B).** Con los mismos tickets
   reales evaluados por ambos routers, esta prueba dice si la diferencia
   de aciertos entre A y B es estadísticamente significativa o si los 14
   tickets de anoche fueron casualidad. Si tenemos pocos tickets reales,
   puede no alcanzar significancia — está bien decirlo así en la
   presentación, es más honesto que inventar certeza.

4. **Curva de calibración de las probabilidades del LLM.** Entre los
   tickets donde Router B dio, por ejemplo, 0.5-0.6 de confianza, ¿qué
   fracción fue realmente correcta? Si el LLM dice "60% seguro" y acierta
   solo el 40% de las veces en ese rango, sus números no son probabilidades
   reales, son solo un orden relativo — y eso cambia cómo hay que
   interpretar los umbrales.

5. **Reproducibilidad.** Correr el mismo ticket real 3-5 veces (mismo
   texto, llamadas distintas al LLM) y medir cuánto varían los scores de
   Router B y el SQL propuesto. Si varía mucho, puede hacer falta bajar la
   temperatura del modelo o usar un esquema de "repetir y votar" en los
   casos más críticos.

6. **Tasa de error de `propose_sql`.** Sobre una muestra de tickets reales,
   contar cuántas veces el SQL propuesto tiene el tipo de error que ya
   vimos esta madrugada (valor inventado, columna equivocada, nombre vs.
   código sin resolver) — nos dice si el arreglo de prompt de hoy
   generaliza bien a datos reales o si hace falta más ajuste.

7. **Costo y latencia por ticket.** Contar cuántas llamadas al LLM hace el
   pipeline completo por ticket (hoy: routing, propuesta SQL, resolución =
   3 llamadas; `propose_status` es determinista, no cuenta) y medir el
   tiempo total — importante porque en la presentación tiran tickets en
   vivo con tiempo limitado (25 min + 5 de preguntas).

8. **Comparación entre modelos, si hay más de uno disponible.** No fiarse
   solo de benchmarks genéricos de internet — correr el mismo lote de
   tickets reales contra cada modelo del catálogo y comparar accuracy real
   en nuestra tarea específica, no en tareas genéricas.

## Trabajo de integración (no son pruebas, son tareas)

1. Fusionar las dos capas de mock — que `create_comment`/`update_status`
   pasen por `tools/registry.py`, y añadir la consulta SQL como 5ª
   herramienta del contrato.
2. Escribir las implementaciones reales en `tools/alenia/` y cambiar
   `PROVIDER = "alenia"`.
3. Cambiar `llm_client.py` a `ChatDatabricks`/`ChatGroq` si el checkpoint
   confirma que hace falta.
4. Reemplazar el esquema de `tests/mock_database.py` por el real.
5. Probar con un ticket que nadie del equipo haya escrito.

## Lo que NO vamos a intentar resolver hoy (decisión consciente)

- Nivel 3 de escalación (sin criterio real, no lo vamos a inventar).
- División de tickets con dos incidentes (documentado como límite).
- UI/Dashboard (bono de +15) — solo si queda tiempo después de lo crítico.