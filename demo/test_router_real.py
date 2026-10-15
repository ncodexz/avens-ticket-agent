import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.router_b import route_b

TICKETS = {
    "32366": """Missing contract CON_a496abb07de48cbc in Fleet Report - Wise Potato Industries SL

Good morning,
Sorry to bother you - I may be missing something, but I can't see contract CON_a496abb07de48cbc for Wise Potato Industries SL in the Fleet Report. Would you mind double-checking whether it should be there?
Many thanks in advance""",

    "32549": """Help needed: Wise Potato Industries SL contract not appearing in Fleet Report

Hello team,
During our monthly reconciliation we noticed that contract CON_98aef11db46443d9 for Wise Potato Industries SL is not included in the latest Fleet Report. The contract is active on our side and should be part of the report.
Could you please investigate why it is missing and let us know the expected resolution date?
Kind regards""",
}

if __name__ == "__main__":
    for ticket_id, text in TICKETS.items():
        print(f"=== Ticket {ticket_id} ===")
        print(route_b(text))
        print()