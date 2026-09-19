from app.engines.fare_rules import fare_for_hops
from app.engines.graph_bfs import shortest_hops, shortest_path


class RoundTripDataError(Exception):
    """去返程站数在无向图上不一致，视为底层数据错误。"""


def quote_route(edges: list[tuple[str, str]], start: str, end: str, rules: list[dict]) -> dict:
    path = shortest_path(edges, start, end)
    if path is None:
        return {"start": start, "end": end, "hops": None, "fare": None, "reachable": False, "path": None}
    hops = len(path) - 1
    fare = fare_for_hops(hops, rules)
    return {"start": start, "end": end, "hops": hops, "fare": fare, "reachable": True, "path": path}


def quote_round_trip(edges: list[tuple[str, str]], start: str, end: str, rules: list[dict]) -> dict:
    """往返联程：去程 start→end，返程 end→start，两侧各自独立寻路。

    无向图上两侧站数必须相等；不相等抛 RoundTripDataError。
    任一侧不可达则整体不可达。
    """
    outbound = quote_route(edges, start, end, rules)
    inbound = quote_route(edges, end, start, rules)

    if not outbound["reachable"] or not inbound["reachable"]:
        return {
            "start": start,
            "end": end,
            "reachable": False,
            "outbound": outbound,
            "inbound": inbound,
            "total_fare": None,
        }

    if outbound["hops"] != inbound["hops"]:
        raise RoundTripDataError(
            f"往返站数不一致：去程 {start}→{end} {outbound['hops']} 站，"
            f"返程 {end}→{start} {inbound['hops']} 站"
        )

    total_fare = round(float(outbound["fare"]) + float(inbound["fare"]), 2)
    return {
        "start": start,
        "end": end,
        "reachable": True,
        "outbound": outbound,
        "inbound": inbound,
        "total_fare": total_fare,
    }
