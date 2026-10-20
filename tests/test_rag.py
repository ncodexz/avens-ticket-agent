import re
import zlib
from datetime import datetime, timezone

import numpy as np
import pytest

from core import rag
from core.ticket import Ticket
from tests.conftest import needs_export


def fake_embed(texts, dim=64):
    """Deterministic bag-of-words vectors: texts that share words get similar vectors."""
    out = np.zeros((len(texts), dim), dtype=np.float32)
    for row, text in enumerate(texts):
        for word in re.findall(r"[a-z0-9_]+", text.lower()):
            out[row, zlib.crc32(word.encode()) % dim] += 1.0
    return out


def record(op_id, uc, title, description="", solution="sol"):
    return {"op_id": op_id, "uc": uc, "priority": "Normal", "title": title,
            "description": description, "solution": solution}


def ticket(op_id, title, description=""):
    return Ticket(title=title, description=description, priority="Normal", source="csv",
                  created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), op_id=op_id)


RECORDS = [
    record(1, "UC1", "Make TOYOTA missing in LMS", "make not mapped"),
    record(2, "UC1", "Model YARIS not mapped", "model not mapped"),
    record(3, "UC2", "Contract CON_a missing from Fleet Report", "fleet report contract"),
    record(4, "UC3", "Missing Vehicle VEH_a", "vehicle missing"),
]


@pytest.fixture
def index():
    return rag.build_index(RECORDS, fake_embed, "fake")


def test_infer_uc_rules():
    assert rag.infer_uc("Missing Vehicle", "VEH_1 is missing") == "UC3"
    assert rag.infer_uc("Contract CON_1 not in Fleet Report", "") == "UC2"
    assert rag.infer_uc("Missing Contract", "CON_1 is missing") == "UC3"
    assert rag.infer_uc("Make TOYOTA missing in LMS", "no mapping") == "UC1"


def test_vectors_are_normalised(index):
    assert np.allclose(np.linalg.norm(index.vectors, axis=1), 1.0)


def test_most_similar_ticket_comes_first(index):
    found = rag.retrieve_similar(ticket(99, "Make HONDA missing in LMS", "make not mapped"),
                                 k=2, index=index, embed_fn=fake_embed)
    assert found[0].op_id == 1


def test_the_ticket_itself_is_excluded(index):
    found = rag.retrieve_similar(ticket(1, "Make TOYOTA missing in LMS", "make not mapped"),
                                 k=4, index=index, embed_fn=fake_embed)
    assert 1 not in [n.op_id for n in found]


def test_search_can_be_limited_to_one_use_case(index):
    found = rag.retrieve_similar(ticket(99, "Missing contract in the Fleet Report"),
                                 k=4, uc="UC1", index=index, embed_fn=fake_embed)
    assert {n.uc for n in found} == {"UC1"}
    assert len(found) == 2


def test_k_limits_the_number_of_results(index):
    found = rag.retrieve_similar(ticket(99, "anything"), k=1, index=index, embed_fn=fake_embed)
    assert len(found) == 1


def test_save_and_load_round_trip(index, tmp_path):
    rag.save_index(index, tmp_path)
    loaded = rag.load_index(tmp_path)
    assert loaded.records == index.records
    assert np.allclose(loaded.vectors, index.vectors)
    assert loaded.meta["embedding_model"] == "fake"


def test_load_fails_when_files_do_not_match(index, tmp_path):
    rag.save_index(index, tmp_path)
    np.save(tmp_path / "rag_vectors.npy", index.vectors[:2])
    with pytest.raises(RuntimeError):
        rag.load_index(tmp_path)


def test_ticket_without_op_id_excludes_nobody(index):
    manual = Ticket(title="Make TOYOTA missing in LMS", description="make not mapped", priority="Normal",
                    source="manual", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    found = rag.retrieve_similar(manual, k=4, index=index, embed_fn=fake_embed)
    assert len(found) == 4


@needs_export
def test_load_closed_records_from_the_real_export():
    records = rag.load_closed_records()
    assert len(records) > 1000
    assert {r["uc"] for r in records} == {"UC1", "UC2", "UC3"}
    assert all(r["solution"].strip() for r in records)
