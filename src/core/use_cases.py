"""
The 3 real Ayvens use cases, parameterized. Adding a 4th use case later
means adding one entry here — nothing else in the codebase needs to change.
"""

from typing import TypedDict


class UseCaseConfig(TypedDict):
    name: str
    context: str          # business context, used inside the extraction prompt
    input_fields: list     # structured fields this use case's tickets carry


USE_CASES: dict[str, UseCaseConfig] = {
    "UC1": UseCaseConfig(
        name="Normalization Management",
        context="validating and maintaining normalization mappings used by downstream Datamarts and regulatory reporting",
        input_fields=["Local code", "Holding value", "Class ID", "Subsidiary", "Mapping details"],
    ),
    "UC2": UseCaseConfig(
        name="Monthly Report Reconciliation",
        context="reconciling monthly regulatory/financial reports against source figures (contracts, vehicles) for a subsidiary",
        input_fields=["Subsidiary", "Reporting month", "Contract IDs", "Vehicle IDs", "Reported figures"],
    ),
    "UC3": UseCaseConfig(
        name="Data Verification & Correction",
        context="verifying and correcting records by comparing source and target systems against business rules",
        input_fields=["Contract IDs", "Customer IDs", "Vehicle IDs", "Business rules"],
    ),
}