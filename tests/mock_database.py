"""
Mock database tables that mirror (a guess at) the real Databricks tables
described in the Participant Kit. Used to test the propose_sql -> approve ->
execute flow locally, before we have real table access tomorrow.

Rows here are deliberately tied to tickets we already tested in
tests/routing_test_tickets.py, so the same scenarios stay consistent.
"""

MD_LOCALVALUE_T = [
    {"local_code": "ES-4471", "holding": None},          # ROUTE-UC1: unmapped
    {"local_code": "FR-6612", "holding": None},          # HARD2-REVERSE-MISLEADING
    {"local_code": "DE-1190", "holding": None},          # HARD2-TWO-SUBSIDIARIES (part 1)
    {"local_code": "PT-2290", "holding": "HLD-PT-01"},   # HARD2-SELF-CONTRADICTING: mapped
]

MD_HOLDINGVALUE_T = [
    {"holding_id": "HLD-PT-01", "holding_name": "Portugal Holding", "active": True},
]

MD_LOCALVALUEHISTORY_T = [
    {"local_code": "PT-2290", "old_holding": "HLD-PT-00", "new_holding": "HLD-PT-01",
     "changed_at": "2026-09-02"},
]

CF_SUBSIDIARIES_T = [
    {"subsidiary_id": "SUB-ES", "subsidiary_name": "Spain", "country": "ES"},
    {"subsidiary_id": "SUB-PT", "subsidiary_name": "Portugal", "country": "PT"},
    {"subsidiary_id": "SUB-DE", "subsidiary_name": "Germany", "country": "DE"},
    {"subsidiary_id": "SUB-AT", "subsidiary_name": "Austria", "country": "AT"},
]

FLEET_REPORT = [
    {"report_month": "2026-09", "subsidiary": "SUB-PT", "contract_count": 50},  # ROUTE-UC2
    {"report_month": "2026-10", "subsidiary": "SUB-AT", "contract_count": 112}, # HARD2-TWO-SUBSIDIARIES (part 2)
]

CONTRACT = [
    {"contract_id": "CT-9981", "client_id": "CL-4420", "subsidiary": "SUB-ES", "vehicle_id": "VH-1123"},
]

VEHICLE = [
    {"vehicle_id": "VH-1123", "contract_id": "CT-9981", "registration_plate": "1234-ABC",
     "in_datamart": False},   # ROUTE-UC3: missing in Datamart
]

# Schema summary handed to the LLM when it proposes a SQL query.
# Keep this in sync with the table lists above.
SCHEMA = {
    "MD_LOCALVALUE_T": ["local_code", "holding"],
    "MD_HOLDINGVALUE_T": ["holding_id", "holding_name", "active"],
    "MD_LOCALVALUEHISTORY_T": ["local_code", "old_holding", "new_holding", "changed_at"],
    "CF_SUBSIDIARIES_T": ["subsidiary_id", "subsidiary_name", "country"],
    "FLEET_REPORT": ["report_month", "subsidiary", "contract_count"],
    "CONTRACT": ["contract_id", "client_id", "subsidiary", "vehicle_id"],
    "VEHICLE": ["vehicle_id", "contract_id", "registration_plate", "in_datamart"],
}

TABLES = {
    "MD_LOCALVALUE_T": MD_LOCALVALUE_T,
    "MD_HOLDINGVALUE_T": MD_HOLDINGVALUE_T,
    "MD_LOCALVALUEHISTORY_T": MD_LOCALVALUEHISTORY_T,
    "CF_SUBSIDIARIES_T": CF_SUBSIDIARIES_T,
    "FLEET_REPORT": FLEET_REPORT,
    "CONTRACT": CONTRACT,
    "VEHICLE": VEHICLE,
}