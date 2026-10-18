# core

Logica comun del sistema. Se escribe una sola vez y la usan `src` (Databricks) y `src_local` (local).

Aqui no hay nada que dependa del entorno: nada de rutas locales, ni de Spark, ni de credenciales.
Lo que cambia con el entorno (de donde llegan los tickets, donde se leen los datos, donde se entrega
la respuesta, que modelo se usa) se pide al exterior mediante adaptadores.

Regla de documentacion: cada modulo que se anada aqui indica en su cabecera su entrada, su salida
y quien lo llama.

## Modulos
(ninguno todavia; el primero sera la capa 1: lectura de tickets)
