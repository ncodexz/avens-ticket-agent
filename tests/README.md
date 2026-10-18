# tests

Pruebas automaticas sobre lo determinista: formato unico del ticket, emparejamiento de
identificadores, unicidad, orden de la cola, exclusion de cerrados.

Regla: las pruebas son datos (ver `data/samples`) que se pasan al sistema real. No se crean
versiones demo del flujo para probar. La evaluacion con el modelo se hace aparte, sobre las 1000
muestras etiquetadas.
