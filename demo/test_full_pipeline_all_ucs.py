import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from demo.full_pipeline_demo import run_full_pipeline

TICKETS_TO_TEST = [
    ("ROUTE-UC1", "El código local ES-4471 aparece sin mapeo asignado en el sistema. "
                   "Llevamos 3 días con reportes de la filial España bloqueados por esto."),
    ("ROUTE-UC2", "El Fleet Report de septiembre muestra 50 contratos para la filial Portugal, "
                   "pero el controlador de negocio solo tiene registrados 47. "
                   "Hay una diferencia de 3 contratos."),
    ("ROUTE-UC3", "El contrato CT-9981 del cliente CL-4420 tiene el vehículo VH-1123 en el "
                   "sistema origen, pero no aparece ningún vehículo asociado en el Datamart."),
]

if __name__ == "__main__":
    for ticket_id, ticket_text in TICKETS_TO_TEST:
        run_full_pipeline(ticket_id, ticket_text)
