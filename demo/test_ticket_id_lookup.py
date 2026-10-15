import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.ticket_id_lookup import get_ticket_id

TITLE = "Missing contract CON_a496abb07de48cbc in Fleet Report - Wise Potato Industries SL"
DESCRIPTION = """Good morning,

Sorry to bother you - I may be missing something, but I can't see contract CON_a496abb07de48cbc for Wise Potato Industries SL in the Fleet Report. Would you mind double-checking whether it should be there?

Many thanks in advance"""

if __name__ == "__main__":
    ticket_id = get_ticket_id(TITLE, DESCRIPTION)
    print(f"ticket_id encontrado: {ticket_id}")