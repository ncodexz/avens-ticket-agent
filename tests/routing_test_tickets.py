"""
Dedicated test set for comparing routing approaches (traditional label vs
probability distribution). Kept separate from sample_tickets.py so this
throwaway experiment doesn't touch the validated fixture file.
"""

ROUTING_TEST_TICKETS = [
    {
        "ticket_id": "ROUTE-UC1",
        "text": "El código local ES-4471 aparece sin mapeo asignado en el sistema. Llevamos 3 días con reportes de la filial España bloqueados por esto.",
        "expected_use_case": "UC1",
    },
    {
        "ticket_id": "ROUTE-UC2",
        "text": "El Fleet Report de septiembre muestra 50 contratos para la filial Portugal, pero el controlador de negocio solo tiene registrados 47. Hay una diferencia de 3 contratos.",
        "expected_use_case": "UC2",
    },
    {
        "ticket_id": "ROUTE-UC3",
        "text": "El contrato CT-9981 del cliente CL-4420 tiene el vehículo VH-1123 en el sistema origen, pero no aparece ningún vehículo asociado en el Datamart.",
        "expected_use_case": "UC3",
    },
    {
        "ticket_id": "ROUTE-AMBIGUOUS",
        "text": "La filial Italia reporta que el contrato CT-5502 tiene un código local IT-3301 que no coincide con ningún holding, y además el número de contratos del mes no cuadra con lo que ve el controlador de negocio.",
        "expected_use_case": None,  # a propósito ambiguo: toca UC1 (código local sin mapeo) Y UC2 (discrepancia de conteo)
    },
]

HARDER_ROUTING_TEST_TICKETS = [
    {
        "ticket_id": "HARD-UC2-UC3-TIE",
        "text": "El contrato CT-7734 del cliente CL-2210 muestra el vehículo VH-9087 en el sistema origen, pero el Fleet Report de octubre no lo refleja, y el controlador de negocio tampoco lo tiene contado en sus cifras del mes.",
        "expected_use_case": None,  # empate real UC2/UC3: falta el vehículo en el Datamart (UC3) Y afecta el conteo mensual reportado (UC2)
    },
    {
        "ticket_id": "HARD-VAGUE-LOW-SIGNAL",
        "text": "Hay un problema con los datos de la filial Bélgica, algo no está bien desde hace unos días.",
        "expected_use_case": None,  # casi sin señal — debería dar probabilidades bajas y parejas en las 3
    },
    {
        "ticket_id": "HARD-MISLEADING-KEYWORDS",
        "text": "El código local BE-2290 asociado al contrato CT-4455 y al vehículo VH-3321 no tiene mapping a ningún holding activo.",
        "expected_use_case": "UC1",  # menciona "contrato" y "vehículo" (vocabulario de UC3) pero el problema real es de mapping (UC1)
    },
    {
        "ticket_id": "HARD-THREE-WAY",
        "text": "La filial Países Bajos reporta: el código local NL-1180 no tiene holding asignado, el Fleet Report de este mes no coincide con las cifras del controlador, y además faltan datos de matrícula en varios vehículos.",
        "expected_use_case": None,  # toca las 3 categorías a la vez, a propósito
    },
    {
        "ticket_id": "HARD-UC1-UC3-TIE",
        "text": "El vehículo VH-5567 tiene un código local DE-7781 que parece incorrecto, y el registro del vehículo en el Datamart tiene la matrícula vacía.",
        "expected_use_case": None,  # empate real UC1/UC3: código local sospechoso (UC1) Y dato de vehículo faltante (UC3)
    },
]
EVEN_HARDER_ROUTING_TEST_TICKETS = [
    {
        "ticket_id": "HARD2-EXTREME-VAGUE",
        "text": "Revisen por favor, gracias.",
        "expected_use_case": None,  # prácticamente cero información — el caso límite real para el umbral de 0.5
    },
    {
        "ticket_id": "HARD2-REVERSE-MISLEADING",
        "text": "El reporte mensual de la filial Francia muestra cifras distintas a las del controlador de negocio, porque el código local FR-6612 nunca quedó bien mapeado al holding correspondiente.",
        "expected_use_case": "UC1",  # usa vocabulario de UC2 ("reporte mensual", "cifras", "controlador") pero la causa raíz es un mapping sin resolver (UC1)
    },
    {
        "ticket_id": "HARD2-SELF-CONTRADICTING",
        "text": "El código local PT-2290 tiene el mapping correcto según el sistema, aunque en realidad no estamos seguros de si el holding al que apunta sigue activo o si cambió hace poco.",
        "expected_use_case": None,  # el ticket se contradice a sí mismo: dice "correcto" y luego expresa duda real
    },
    {
        "ticket_id": "HARD2-ENGLISH",
        "text": "Vehicle VH-8842 is listed under contract CT-3310 in the source system, but the Datamart shows no vehicle linked to that contract at all.",
        "expected_use_case": "UC3",  # mismo tipo de caso claro que ROUTE-UC3, pero en inglés en vez de español
    },
    {
        "ticket_id": "HARD2-TWO-SUBSIDIARIES",
        "text": "En la filial Alemania, el código local DE-1190 no tiene mapping asignado. Por separado, en la filial Austria, el Fleet Report de este mes no coincide con las cifras del controlador de negocio.",
        "expected_use_case": None,  # dos problemas genuinamente distintos (UC1 y UC2) en dos filiales distintas — ¿debería ser un ticket o dos?
    },
]