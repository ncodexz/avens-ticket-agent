import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.router_b import route_b
from agent.propose_sql import propose_sql
from agent.sql_executor import validate_select_only, execute_query
from agent.generate_resolution_from_sql import generate_resolution
from agent.ticket_id_lookup import get_ticket_id

TICKETS = {
    "32366": {
        "title": "Missing contract CON_a496abb07de48cbc in Fleet Report - Wise Potato Industries SL",
        "body": """Missing contract CON_a496abb07de48cbc in Fleet Report - Wise Potato Industries SL

Good morning,
Sorry to bother you - I may be missing something, but I can't see contract CON_a496abb07de48cbc for Wise Potato Industries SL in the Fleet Report. Would you mind double-checking whether it should be there?
Many thanks in advance""",
    },
    "32549": {
        "title": "Help needed: Wise Potato Industries SL contract not appearing in Fleet Report",
        "body": """Help needed: Wise Potato Industries SL contract not appearing in Fleet Report

Hello team,
During our monthly reconciliation we noticed that contract CON_98aef11db46443d9 for Wise Potato Industries SL is not included in the latest Fleet Report. The contract is active on our side and should be part of the report.
Could you please investigate why it is missing and let us know the expected resolution date?
Kind regards""",
    },
}


def run_ticket(ticket_id_op: str, title: str, body: str):
    print(f"\n{'='*60}\nTicket OpenProject #{ticket_id_op}\n{'='*60}")

    # 1. Routing
    routing = route_b(body)
    print(f"[1] Routing: {routing['use_case']} (needs_human_review={routing['needs_human_review']})")

    # 2. Proponer SQL
    proposal = propose_sql(body)
    is_valid, reason = validate_select_only(proposal["sql"])
    print(f"[2] SQL propuesto (válido={is_valid}):\n{proposal['sql']}")
    if not is_valid:
        print(f"    Rechazado: {reason}")
        return

    # 3. (Aquí iría la aprobación humana real; la simulamos como aprobada)
    print("[3] Aprobación humana: APROBADO (simulado)")

    # 4. Ejecutar contra Databricks real
    result = execute_query(proposal["sql"])
    print(f"[4] Resultado real ({len(result)} filas): {result}")

    # 5. Generar resolución
    resolution = generate_resolution(body, proposal["sql"], result)
    print(f"[5] Resolución generada:")
    print(f"    Texto: {resolution['resolution_text']}")
    print(f"    Ready to close: {resolution['ready_to_close']}")

    # 6. Obtener ticket_id real para entrega
    ticket_id = get_ticket_id(title, body)
    print(f"[6] ticket_id interno: {ticket_id}")

    print(f"\n--> LISTO PARA ENTREGAR (pendiente send_fake_email_solution.py)")
    print(f"    ticket_id={ticket_id}, resolution_text={resolution['resolution_text'][:80]}...")


if __name__ == "__main__":
    for op_id, data in TICKETS.items():
        run_ticket(op_id, data["title"], data["body"])