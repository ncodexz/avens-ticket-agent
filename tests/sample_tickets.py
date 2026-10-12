"""
The 13 tickets used to validate the extraction + decision pattern across
UC1, UC2 and UC3. These are a regression suite: if a future prompt change
flips any of these results without a documented reason, something broke.

Ticket content stays in Spanish (or whatever language real tickets arrive
in) — only code identifiers are in English.
"""

from core.state import TicketRaw

TICKETS_UC1: list[TicketRaw] = [
    TicketRaw(
        ticket_id="UC1-001",
        text="El código local ES-4471 aparece sin mapeo asignado en el sistema. Llevamos 3 días con reportes de la filial España bloqueados por esto.",
        fields={"Local code": "ES-4471", "Subsidiary": "España", "Class ID": None, "Mapping details": None},
    ),
    TicketRaw(
        ticket_id="UC1-002",
        text="Hemos abierto una nueva filial en Portugal, necesitamos que se cree el holding value correspondiente para empezar a reportar desde el próximo mes.",
        fields={"Subsidiary": "Portugal (nueva)", "Holding value": "no existe todavía", "Class ID": "PT-STANDARD"},
    ),
    TicketRaw(
        ticket_id="UC1-003",
        text="El mapeo del Class ID AR-200 no coincide con lo que veo en el Datamart de riesgo de activos, pero no estoy seguro si es un error nuestro o un cambio reciente que no nos avisaron.",
        fields={"Class ID": "AR-200", "Mapping details": "no coincide con Datamart ASSET RISK", "Subsidiary": "Argentina"},
    ),
    TicketRaw(
        ticket_id="UC1-004",
        text="Llevamos 3 días esperando que se active el holding value de la nueva filial de Marruecos, los reportes de octubre no se pueden generar hasta que esto se cree.",
        fields={"Subsidiary": "Marruecos (nueva, alta en curso)", "Holding value": "pendiente de creación", "Class ID": "MA-STANDARD"},
    ),
    TicketRaw(
        ticket_id="UC1-005",
        text="Según el comunicado de Data Governance del 1 de octubre, el Class ID DE-330 fue reestructurado y ya no mapea al Datamart antiguo. Desde ese cambio, los reportes de la filial Alemania muestran valores distintos a los de antes.",
        fields={"Class ID": "DE-330", "Subsidiary": "Alemania", "Mapping details": "cambiado según comunicado oficial del 01/10"},
    ),
    TicketRaw(
        ticket_id="UC1-006",
        text="El código IT-150 nunca ha tenido mapeo en el sistema, pero el equipo de Italia dice que lleva usándolo internamente desde hace 2 años sin problema hasta ahora que empezó a fallar la carga al Datamart.",
        fields={"Local code": "IT-150", "Subsidiary": "Italia", "Mapping details": None},
    ),
    TicketRaw(
        ticket_id="UC1-007",
        text="El Class ID FR-220 mapea actualmente al Datamart de riesgo equivocado; el valor correcto según el manual de normalización es ASSET-RISK-02, pero el sistema tiene asignado ASSET-RISK-07.",
        fields={"Class ID": "FR-220", "Subsidiary": "Francia", "Mapping details": "ASSET-RISK-07 (incorrecto, debería ser ASSET-RISK-02)"},
    ),
    TicketRaw(
        ticket_id="UC1-008",
        text="¿Podrían revisar el mapeo del código BR-410? No estoy seguro de si está bien.",
        fields={"Local code": "BR-410", "Subsidiary": "Brasil", "Mapping details": None},
    ),
    TicketRaw(
        ticket_id="UC1-009",
        text="Según el manual de normalización, el valor correcto para el holding value NL-310 es HOL-NL-02, pero el sistema tiene asignado HOL-NL-09 desde siempre. Nadie ha reportado ningún cambio reciente, simplemente está mal desde que se configuró.",
        fields={"Holding value": "HOL-NL-09 (incorrecto según manual)", "Subsidiary": "Países Bajos", "Class ID": "NL-STANDARD"},
    ),
    TicketRaw(
        ticket_id="UC1-010",
        text="El equipo de Data Governance aprobó el 28 de septiembre el cambio de estructura del Class ID BE-500, por lo que ya no coincide con el valor que aparecía antes en el Datamart. Esto es esperado según el approval ticket DG-2291.",
        fields={"Class ID": "BE-500", "Subsidiary": "Bélgica", "Mapping details": "cambiado según approval DG-2291"},
    ),
    TicketRaw(
        ticket_id="UC1-011",
        text="Desde ayer el Datamart de riesgo deja de recibir datos para la filial de Grecia. Antes funcionaba sin problema. El Class ID GR-180 parece haber perdido su mapeo de un día para otro.",
        fields={"Class ID": "GR-180", "Subsidiary": "Grecia", "Mapping details": None},
    ),
]

TICKETS_UC2: list[TicketRaw] = [
    TicketRaw(
        ticket_id="UC2-001",
        text="Los contratos del mes de septiembre para la filial de Italia muestran 50 vehículos reportados, pero el sistema fuente solo tiene registrados 47. No sabemos si faltan 3 contratos por cargar o si el reporte está mal generado.",
        fields={"Subsidiary": "Italia", "Reporting month": "Septiembre", "Contract IDs": "N/A", "Reported figures": "50 vehículos (sistema: 47)"},
    ),
]

TICKETS_UC3: list[TicketRaw] = [
    TicketRaw(
        ticket_id="UC3-001",
        text="El contrato CT-9981 del cliente CL-4420 aparece con el vehículo VH-1123 en el sistema origen, pero en el Datamart objetivo no aparece ningún vehículo asociado a ese contrato.",
        fields={"Contract IDs": "CT-9981", "Customer IDs": "CL-4420", "Vehicle IDs": "VH-1123", "Business rules": "N/A"},
    ),
]

ALL_TICKETS = TICKETS_UC1 + TICKETS_UC2 + TICKETS_UC3
ALL_TICKETS_BY_ID: dict[str, TicketRaw] = {t["ticket_id"]: t for t in ALL_TICKETS}