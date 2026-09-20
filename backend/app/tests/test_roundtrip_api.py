import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    # 每个用例使用独立临时库，TestClient 启动时会执行 seed.init_db()。
    from app import db as db_mod

    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test_roundtrip.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def _history_count(client) -> int:
    return len(client.get("/api/history").json()["items"])


def _roundtrip_body(**over):
    body = {
        "outbound_start": "A1",
        "outbound_end": "B2",
        "return_start": "B2",
        "return_end": "A1",
        "persist": True,
    }
    body.update(over)
    return body


def test_swap_reversed_and_totals_match(client):
    # 试算：去返程对调、两侧站数相等、合计等于两侧票价之和。
    r = client.post("/api/quote/roundtrip", json=_roundtrip_body(persist=False))
    assert r.status_code == 200
    data = r.json()
    assert data["outbound"]["path"] == ["A1", "A2", "B1", "B2"]
    assert data["inbound"]["path"] == ["B2", "B1", "A2", "A1"]
    assert data["outbound"]["hops"] == data["inbound"]["hops"] == 3
    assert data["total_fare"] == data["outbound"]["fare"] + data["inbound"]["fare"]


def test_not_swapped_is_rejected_and_writes_nothing(client):
    before = _history_count(client)
    r = client.post(
        "/api/quote/roundtrip",
        json=_roundtrip_body(return_start="A1", return_end="B2"),
    )
    assert r.status_code == 400
    assert _history_count(client) == before


def test_trial_only_writes_nothing(client):
    # 只试算、不保存：库里不得多出记录。
    before = _history_count(client)
    r = client.post("/api/quote/roundtrip", json=_roundtrip_body(persist=False))
    assert r.status_code == 200
    assert r.json()["outbound_id"] is None
    assert r.json()["inbound_id"] is None
    assert _history_count(client) == before


def test_unreachable_side_writes_nothing(client):
    # 任一侧走不通：两边都不得落库。
    before = _history_count(client)
    r = client.post(
        "/api/quote/roundtrip",
        json=_roundtrip_body(outbound_end="X9", return_start="X9"),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["reachable"] is False
    assert data["outbound_id"] is None and data["inbound_id"] is None
    assert _history_count(client) == before


def test_hop_mismatch_rejected_and_writes_nothing(client, monkeypatch):
    # 两侧站数对不上（底层数据被污染）：拒绝写入。
    import app.engines.route_quote as mod

    def fake_quote(edges, start, end, rules):
        if start == "A1":
            return {"start": start, "end": end, "hops": 2, "fare": 3.0,
                    "reachable": True, "path": [start, "A2", end]}
        return {"start": start, "end": end, "hops": 3, "fare": 4.0,
                "reachable": True, "path": [start, "B1", "A2", end]}

    monkeypatch.setattr(mod, "quote_route", fake_quote)
    before = _history_count(client)
    r = client.post("/api/quote/roundtrip", json=_roundtrip_body())
    assert r.status_code == 500
    assert _history_count(client) == before


def test_persist_creates_cross_referenced_pair(client):
    before = _history_count(client)
    r = client.post("/api/quote/roundtrip", json=_roundtrip_body())
    assert r.status_code == 200
    data = r.json()
    out_id, in_id = data["outbound_id"], data["inbound_id"]
    assert out_id and in_id and out_id != in_id
    # 落库恰好两条。
    assert _history_count(client) == before + 2

    items = {it["id"]: it for it in client.get("/api/history").json()["items"]}
    # 各自带上对方编号。
    assert items[out_id]["pair_id"] == in_id
    assert items[in_id]["pair_id"] == out_id
    # 列表中的方向标注正确。
    assert items[out_id]["result"]["direction"] == "outbound"
    assert items[in_id]["result"]["direction"] == "inbound"


def test_each_detail_shows_only_its_own_side(client):
    data = client.post("/api/quote/roundtrip", json=_roundtrip_body()).json()
    out_id, in_id = data["outbound_id"], data["inbound_id"]

    out = client.get(f"/api/history/{out_id}").json()
    back = client.get(f"/api/history/{in_id}").json()

    # 点开去程只能看到去程站序与去程票价。
    assert out["result"]["path"] == ["A1", "A2", "B1", "B2"]
    assert out["result"]["start"] == "A1" and out["result"]["end"] == "B2"
    assert out["result"]["hops"] == 3 and out["result"]["fare"] == 4.0
    assert "inbound" not in out["result"] and "outbound" not in out["result"]
    # 点开返程只能看到返程。
    assert back["result"]["path"] == ["B2", "B1", "A2", "A1"]
    assert back["result"]["start"] == "B2" and back["result"]["end"] == "A1"
    assert back["result"]["hops"] == 3 and back["result"]["fare"] == 4.0
    assert "inbound" not in back["result"] and "outbound" not in back["result"]

    # 去程票价加返程票价仍等于当时往返合计。
    assert out["result"]["fare"] + back["result"]["fare"] == data["total_fare"]
    assert out["result"]["total_fare"] == back["result"]["total_fare"] == data["total_fare"]


def test_opening_details_does_not_change_pair_ids(client):
    # 分别打开两条后回到列表，对方编号不得被打开动作改掉。
    data = client.post("/api/quote/roundtrip", json=_roundtrip_body()).json()
    out_id, in_id = data["outbound_id"], data["inbound_id"]

    client.get(f"/api/history/{out_id}")
    client.get(f"/api/history/{in_id}")
    client.get(f"/api/history/{out_id}")

    items = {it["id"]: it for it in client.get("/api/history").json()["items"]}
    assert items[out_id]["pair_id"] == in_id
    assert items[in_id]["pair_id"] == out_id
    # 详情接口里也必须是对方编号，而不是自己。
    assert client.get(f"/api/history/{out_id}").json()["pair_id"] == in_id
    assert client.get(f"/api/history/{in_id}").json()["pair_id"] == out_id
