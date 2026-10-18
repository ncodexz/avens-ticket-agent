"""Formato unico de ticket.

Entrada: los datos de un ticket de cualquier origen (los convierten los adaptadores).
Salida:  un objeto Ticket con siempre los mismos campos.
Lo usa:  toda la capa 1 (lectura de tickets) y los bloques siguientes.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Orden de resolucion: cuanto menor el numero, antes se resuelve.
PRIORITY_RANK = {"Immediate": 0, "High": 1, "Normal": 2, "Low": 3}

SOURCES = {"openproject", "csv", "databricks", "manual"}


@dataclass(frozen=True)
class Ticket:
    title: str
    description: str
    priority: str
    source: str
    created_at: datetime              # siempre con zona horaria (UTC)
    op_id: Optional[int] = None       # numero en OpenProject (32364...)
    mapping_id: Optional[str] = None  # numero interno de Alenia (6041134...)
    source_status: Optional[str] = None  # estado en el origen (New, Closed...)

    def __post_init__(self):
        if not self.title.strip():
            raise ValueError("El ticket no tiene titulo")
        if self.priority not in PRIORITY_RANK:
            raise ValueError(f"Prioridad desconocida: {self.priority!r}")
        if self.source not in SOURCES:
            raise ValueError(f"Origen desconocido: {self.source!r}")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at debe llevar zona horaria")

    def sort_key(self):
        """Prioridad primero; dentro de una prioridad, el mas antiguo."""
        return (PRIORITY_RANK[self.priority], self.created_at, self.op_id or 0)
