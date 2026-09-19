import pytest

from app.engines.fare_rules import fare_for_hops
from app.engines.graph_bfs import shortest_hops, shortest_path
from app.engines.route_quote import RoundTripDataError, quote_route, quote_round_trip

EDGES = [("A1", "A2"), ("A2", "A3"), ("A2", "B1"), ("B1", "B2")]
RULES = [{"max_hops": 2, "price": 3.0}, {"max_hops": 4, "price": 4.0}, {"max_hops": None, "price": 6.0}]


def test_hops_a1_a3():
    assert shortest_hops(EDGES, "A1", "A3") == 2


def test_hops_a1_b2():
    assert shortest_hops(EDGES, "A1", "B2") == 3


def test_shortest_path():
    assert shortest_path(EDGES, "A1", "A3") == ["A1", "A2", "A3"]
    assert shortest_path(EDGES, "A1", "X9") is None
    assert shortest_path(EDGES, "A1", "A1") == ["A1"]


def test_fare_by_hops():
    assert fare_for_hops(2, RULES) == 3.0
    assert fare_for_hops(3, RULES) == 4.0
    assert fare_for_hops(10, RULES) == 6.0


def test_quote():
    q = quote_route(EDGES, "A1", "B2", RULES)
    assert q["hops"] == 3 and q["fare"] == 4.0
    assert q["path"] == ["A1", "A2", "B1", "B2"]


def test_round_trip_basic():
    rt = quote_round_trip(EDGES, "A1", "B2", RULES)
    assert rt["reachable"] is True
    assert rt["outbound"]["path"] == ["A1", "A2", "B1", "B2"]
    assert rt["inbound"]["path"] == ["B2", "B1", "A2", "A1"]
    assert rt["outbound"]["hops"] == rt["inbound"]["hops"] == 3
    assert rt["outbound"]["fare"] == rt["inbound"]["fare"] == 4.0
    assert rt["total_fare"] == 8.0


def test_round_trip_unreachable():
    rt = quote_round_trip(EDGES, "A1", "X9", RULES)
    assert rt["reachable"] is False
    assert rt["total_fare"] is None
    assert rt["outbound"]["reachable"] is False
    assert rt["inbound"]["reachable"] is False


def test_round_trip_hop_mismatch_is_data_error(monkeypatch):
    # 无向图上理论上必然对称；若底层数据被污染导致两侧站数不等，必须拒绝。
    import app.engines.route_quote as mod

    def fake_quote(edges, start, end, rules):
        hops = 2 if start == "A1" else 3
        return {"start": start, "end": end, "hops": hops, "fare": 4.0, "reachable": True, "path": [start, "x", end]}

    monkeypatch.setattr(mod, "quote_route", fake_quote)
    with pytest.raises(RoundTripDataError):
        quote_round_trip(EDGES, "A1", "B2", RULES)
