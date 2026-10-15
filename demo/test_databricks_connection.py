import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.databricks_client import execute_query

if __name__ == "__main__":
    result = execute_query(
        "SELECT * FROM aiops_participants_synthethic_data.gold.fleet_report "
        "WHERE contractCode = 5009292"
    )
    for row in result:
        print(row)