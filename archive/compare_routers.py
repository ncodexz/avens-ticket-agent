"""
Runs both routing approaches (router_a: single label, router_b: probability
distribution) against the same test tickets and prints results side by side.

Run with: python demo/compare_routers.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.routing_test_tickets import ROUTING_TEST_TICKETS, HARDER_ROUTING_TEST_TICKETS , EVEN_HARDER_ROUTING_TEST_TICKETS
from agent.router_a import route_a
from agent.router_b import route_b


def main():
    for ticket in ROUTING_TEST_TICKETS + HARDER_ROUTING_TEST_TICKETS + EVEN_HARDER_ROUTING_TEST_TICKETS:
        print(f"\n{'=' * 60}")
        print(f"Ticket: {ticket['ticket_id']}")
        print(f"Expected: {ticket['expected_use_case']}")
        print(f"Text: {ticket['text']}")
        print("-" * 60)

        result_a = route_a(ticket["text"])
        print(f"Router A (tradicional): {result_a}")

        result_b = route_b(ticket["text"])
        print(f"Router B (adaptado):    {result_b}")


if __name__ == "__main__":
    main()