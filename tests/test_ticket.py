from datetime import datetime, timezone

import pytest

from core.ticket import Ticket


def make(priority, day, op_id):
    return Ticket(
        title="t", description="d", priority=priority, source="csv",
        created_at=datetime(2026, 10, day, tzinfo=timezone.utc), op_id=op_id,
    )


def test_orden_por_prioridad_y_antiguedad():
    tickets = [make("Low", 1, 1), make("High", 3, 2), make("High", 2, 3),
               make("Immediate", 5, 4), make("Normal", 1, 5)]
    orden = [t.op_id for t in sorted(tickets, key=lambda t: t.sort_key())]
    assert orden == [4, 3, 2, 5, 1]


def test_prioridad_desconocida_falla():
    with pytest.raises(ValueError):
        make("Urgent", 1, 1)


def test_fecha_sin_zona_horaria_falla():
    with pytest.raises(ValueError):
        Ticket(title="t", description="d", priority="Low", source="csv",
               created_at=datetime(2026, 10, 1))
