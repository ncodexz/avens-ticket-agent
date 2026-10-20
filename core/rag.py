"""Block 2: find the closed tickets most similar to a new one.

What is stored (one record per closed ticket that has a solution):
    op_id, uc, priority, title, description, solution
Only title + description are turned into a vector. The solution is stored as
text and returned with each neighbour, because the ticket we search for
does not have a solution yet.

Where it lives: local files in data/ (ignored by git)
    rag_records.jsonl  one JSON record per line
    rag_vectors.npy    one normalised vector per record, same order
    rag_meta.json      embedding model, build date, record count
The index can be searched with no network once the vectors exist.

The use case (uc) of the historical tickets is INFERRED from the ticket text
by infer_uc(); it does not come from Alenia.
"""

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from core.config import PROJECT_ROOT, export_dir

MAX_TEXT_CHARS = 2000
REPORT_WORDS = re.compile(r"fleet report|monthly|reconcil|in the report|in report", re.I)


def data_dir():
    path = PROJECT_ROOT / "data"
    path.mkdir(exist_ok=True)
    return path


def infer_uc(title, description):
    """Label a historical ticket from its text.

    VEH_ code -> UC3. CON_ code + report wording -> UC2. CON_ code otherwise -> UC3.
    No CON_/VEH_ code (mapping problems) -> UC1.
    """
    text = f"{title} {description}"
    if re.search(r"\bVEH_", text):
        return "UC3"
    if re.search(r"\bCON_", text):
        return "UC2" if REPORT_WORDS.search(text) else "UC3"
    return "UC1"


def ticket_text(title, description):
    return f"{title}\n{description}".strip()[:MAX_TEXT_CHARS]


def load_closed_records(export_path=None):
    """Closed tickets that have a solution comment, read from the OpenProject export."""
    base = Path(export_path) if export_path else Path(export_dir()) / "openproject"
    solutions = {}
    with open(base / "activities.jsonl", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            comments = [
                a["comment"]["raw"].strip()
                for a in item["activities"]
                if a.get("comment", {}).get("raw", "").strip()
            ]
            if comments:
                solutions[str(item["work_package"])] = "\n".join(comments)
    with open(base / "work_packages.csv", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    records = []
    for row in rows:
        if row["status"] != "Closed" or row["id"] not in solutions:
            continue
        records.append({
            "op_id": int(row["id"]),
            "uc": infer_uc(row["subject"], row["description"]),
            "priority": row["priority"],
            "title": row["subject"],
            "description": row["description"],
            "solution": solutions[row["id"]],
        })
    return records


@dataclass
class Index:
    records: list
    vectors: np.ndarray   # shape (n, dim), each row has length 1
    meta: dict


@dataclass
class Neighbour:
    op_id: int
    uc: str
    score: float          # cosine similarity, 1.0 = identical direction
    title: str
    solution: str


def _normalise(matrix):
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def build_index(records, embed_fn, model_name="unknown"):
    texts = [ticket_text(r["title"], r["description"]) for r in records]
    vectors = _normalise(embed_fn(texts))
    meta = {
        "embedding_model": model_name,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "records": len(records),
    }
    return Index(records=list(records), vectors=vectors, meta=meta)


def save_index(index, directory=None):
    directory = Path(directory) if directory else data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / "rag_records.jsonl", "w", encoding="utf-8") as handle:
        for record in index.records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    np.save(directory / "rag_vectors.npy", index.vectors)
    with open(directory / "rag_meta.json", "w", encoding="utf-8") as handle:
        json.dump(index.meta, handle, indent=2)


def load_index(directory=None):
    directory = Path(directory) if directory else data_dir()
    with open(directory / "rag_records.jsonl", encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle]
    vectors = np.load(directory / "rag_vectors.npy")
    with open(directory / "rag_meta.json", encoding="utf-8") as handle:
        meta = json.load(handle)
    if len(records) != len(vectors):
        raise RuntimeError("rag_records.jsonl and rag_vectors.npy have different sizes; rebuild the index")
    return Index(records=records, vectors=vectors, meta=meta)


def retrieve_similar(ticket, k=3, uc=None, index=None, embed_fn=None):
    """The k closed tickets most similar to `ticket`.

    uc: search only inside this use case (the one the router decided). None = all.
    The ticket itself is never returned (matched by op_id), so tests are not rigged.
    """
    if index is None:
        index = load_index()
    if embed_fn is None:
        from core import llm_client
        embed_fn = llm_client.embed
    query = _normalise(embed_fn([ticket_text(ticket.title, ticket.description)]))[0]
    scores = index.vectors @ query
    order = np.argsort(-scores)
    found = []
    for position in order:
        record = index.records[position]
        if uc is not None and record["uc"] != uc:
            continue
        if ticket.op_id is not None and record["op_id"] == ticket.op_id:
            continue
        found.append(Neighbour(record["op_id"], record["uc"], float(scores[position]),
                               record["title"], record["solution"]))
        if len(found) == k:
            break
    return found


def _cli():
    parser = argparse.ArgumentParser(description="Build or query the ticket index.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="embed all closed tickets and save the index in data/")
    build.add_argument("--limit", type=int, default=None, help="only the first N tickets (for a cheap trial)")
    search = sub.add_parser("search", help="show the neighbours of one ticket from the CSV export")
    search.add_argument("--id", type=int, required=True)
    search.add_argument("-k", type=int, default=3)
    search.add_argument("--any-uc", action="store_true", help="do not restrict to the ticket's own use case")
    args = parser.parse_args()

    from core import llm_client
    if args.command == "build":
        records = load_closed_records()
        if args.limit:
            records = records[:args.limit]
        index = build_index(records, llm_client.embed, llm_client.model_config("embedding")["model"])
        save_index(index)
        print(f"Saved {len(records)} records in {data_dir()}")
    else:
        from core.sources import csv_export
        ticket = next(t for t in csv_export.read_tickets() if t.op_id == args.id)
        uc = None if args.any_uc else infer_uc(ticket.title, ticket.description)
        print(f"Ticket {ticket.op_id} [{uc or 'any UC'}]: {ticket.title}")
        for n in retrieve_similar(ticket, k=args.k, uc=uc):
            print(f"\n  {n.score:.3f}  {n.op_id} [{n.uc}] {n.title}\n  solution: {' '.join(n.solution.split())[:300]}")


if __name__ == "__main__":
    _cli()
