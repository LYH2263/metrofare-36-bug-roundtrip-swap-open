import json

import pytest

from app import seed
from app.db import connect
from app.engines.route_quote import RoundTripDataError
from app.repositories import runs as runs_repo
from app.services.metro_service import MetroService


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """每个用例一座临时库：schema + 种子数据（含 1 条种子单程记录）。"""
    monkeypatch.setattr("app.db.DB_PATH", tmp_path / "test.db")
    seed.init_db()
    return tmp_path / "test.db"


def _count() -> int:
    with MetroService() as s:
        return len(s.history(limit=10000))


def _save_pair(start="A1", end="B2"):
    with MetroService() as s:
        res = s.quote_round_trip(start, end, end, start, persist=True)
    assert res["reachable"] is True
    return res


def test_persist_writes_one_outbound_one_inbound_cross_referenced(db):
    before = _count()
    res = _save_pair()
    out_id, in_id = res["outbound_id"], res["inbound_id"]

    # 落库恰好两条：去程一条、返程一条
    assert out_id is not None and in_id is not None and out_id != in_id
    assert _count() == before + 2

    with MetroService() as s:
        out_row, in_row = s.run(out_id), s.run(in_id)
    # 各自带上对方的编号，而不是指向自己
    assert out_row["pair_id"] == in_id
    assert in_row["pair_id"] == out_id
    assert json.loads(out_row["result_json"])["direction"] == "outbound"
    assert json.loads(in_row["result_json"])["direction"] == "inbound"


def test_each_record_shows_only_its_own_side(db):
    res = _save_pair()
    with MetroService() as s:
        out_row = json.loads(s.run(res["outbound_id"])["result_json"])
        in_row = json.loads(s.run(res["inbound_id"])["result_json"])

    # 点开去程只能看到去程站序和去程票价
    assert out_row["path"] == ["A1", "A2", "B1", "B2"]
    assert out_row["start"] == "A1" and out_row["end"] == "B2"
    # 点开返程只能看到返程
    assert in_row["path"] == ["B2", "B1", "A2", "A1"]
    assert in_row["start"] == "B2" and in_row["end"] == "A1"
    # 去程票价加返程票价仍等于当时往返合计
    assert out_row["fare"] + in_row["fare"] == out_row["total_fare"]
    assert in_row["total_fare"] == out_row["total_fare"]


def test_opening_records_does_not_rewrite_pair_id(db):
    res = _save_pair()
    out_id, in_id = res["outbound_id"], res["inbound_id"]

    with MetroService() as s:
        # 从记录列表分别打开两条，重复多次
        for _ in range(3):
            assert s.run(out_id)["pair_id"] == in_id
            assert s.run(in_id)["pair_id"] == out_id
        # 回到列表：对方编号未被打开动作改掉
        rows = {r["id"]: r for r in s.history(limit=10000)}
        assert rows[out_id]["pair_id"] == in_id
        assert rows[in_id]["pair_id"] == out_id


def test_unreachable_side_persists_neither(db):
    before = _count()
    with MetroService() as s:
        res = s.quote_round_trip("A1", "X9", "X9", "A1", persist=True)
    # 有一侧走不通：整体不可达，两边都不得落库，条数保持原样
    assert res["reachable"] is False
    assert res["outbound_id"] is None and res["inbound_id"] is None
    assert _count() == before


def test_trial_without_save_persists_nothing(db):
    before = _count()
    with MetroService() as s:
        res = s.quote_round_trip("A1", "B2", "B2", "A1", persist=False)
    assert res["reachable"] is True
    assert res["outbound_id"] is None and res["inbound_id"] is None
    assert _count() == before


def test_hop_mismatch_rejects_write(db, monkeypatch):
    import app.services.metro_service as svc

    def fake_round_trip(edges, start, end, rules):
        raise RoundTripDataError("往返站数不一致")

    monkeypatch.setattr(svc, "quote_round_trip", fake_round_trip)
    before = _count()
    with pytest.raises(RoundTripDataError):
        with MetroService() as s:
            s.quote_round_trip("A1", "B2", "B2", "A1", persist=True)
    assert _count() == before


def test_return_leg_not_swapped_is_rejected(db):
    before = _count()
    with pytest.raises(ValueError, match="return_start"):
        with MetroService() as s:
            s.quote_round_trip("A1", "B2", "A1", "B2", persist=True)
    assert _count() == before


def test_insert_pair_rolls_back_when_second_insert_fails(db):
    conn = connect()
    try:
        before = len(runs_repo.list_recent(conn, limit=10000))
        with pytest.raises(TypeError):
            runs_repo.insert_pair(
                conn, "roundtrip",
                {"start": "A1", "end": "B2"}, {"fare": 4.0},
                {"start": "B2", "end": "A1"}, {"bad": object()},
            )
        # 返程那条写失败：去程也不得留下，条数保持原样
        assert len(runs_repo.list_recent(conn, limit=10000)) == before
    finally:
        conn.close()


def test_api_roundtrip_save_then_open_each(db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        saved = client.post("/api/quote/roundtrip", json={
            "outbound_start": "A1", "outbound_end": "B2",
            "return_start": "B2", "return_end": "A1",
            "persist": True,
        }).json()
        out_id, in_id = saved["outbound_id"], saved["inbound_id"]

        out = client.get(f"/api/history/{out_id}").json()
        inc = client.get(f"/api/history/{in_id}").json()
        assert out["result"]["path"] == ["A1", "A2", "B1", "B2"]
        assert inc["result"]["path"] == ["B2", "B1", "A2", "A1"]
        assert out["pair_id"] == in_id and inc["pair_id"] == out_id
        assert out["result"]["fare"] + inc["result"]["fare"] == out["result"]["total_fare"]

        # 列表里的编号在打开两条之后仍互指对方
        items = {r["id"]: r for r in client.get("/api/history").json()["items"]}
        assert items[out_id]["pair_id"] == in_id
        assert items[in_id]["pair_id"] == out_id


def test_api_trial_only_and_bad_requests_leave_no_rows(db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        before = len(client.get("/api/history").json()["items"])

        # 只看试算、不点保存
        r = client.post("/api/quote/roundtrip", json={
            "outbound_start": "A1", "outbound_end": "B2",
            "return_start": "B2", "return_end": "A1",
            "persist": False,
        })
        assert r.status_code == 200 and r.json()["outbound_id"] is None

        # 一侧走不通
        r = client.post("/api/quote/roundtrip", json={
            "outbound_start": "A1", "outbound_end": "X9",
            "return_start": "X9", "return_end": "A1",
            "persist": True,
        })
        assert r.status_code == 200 and r.json()["reachable"] is False

        # 返程未与去程对调
        r = client.post("/api/quote/roundtrip", json={
            "outbound_start": "A1", "outbound_end": "B2",
            "return_start": "A1", "return_end": "B2",
            "persist": True,
        })
        assert r.status_code == 400

        assert len(client.get("/api/history").json()["items"]) == before
