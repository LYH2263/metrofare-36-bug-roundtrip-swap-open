import json

from app.db import connect
from app.engines.route_quote import RoundTripDataError, quote_route, quote_round_trip
from app.repositories import edges as edges_repo
from app.repositories import fare_rules as rules_repo
from app.repositories import runs as runs_repo
from app.repositories import settings as settings_repo
from app.repositories import stations as stations_repo


class MetroService:
    def __init__(self):
        self._conn = connect()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def stations(self):
        return stations_repo.list_all(self._conn)

    def station(self, code: str):
        return stations_repo.get_by_code(self._conn, code)

    def edges(self):
        return [{"a": a, "b": b} for a, b in edges_repo.list_pairs(self._conn)]

    def fare_rules(self):
        return rules_repo.list_ordered(self._conn)

    def settings(self):
        return settings_repo.get_map(self._conn)

    def quote(self, start: str, end: str, persist: bool):
        edges = edges_repo.list_pairs(self._conn)
        rules = rules_repo.as_calc_rules(self._conn)
        result = quote_route(edges, start, end, rules)
        run_id = None
        if persist and result.get("reachable"):
            run_id = runs_repo.insert(self._conn, "quote", {"start": start, "end": end}, result)
        return {"run_id": run_id, **result}

    def quote_round_trip(
        self,
        outbound_start: str,
        outbound_end: str,
        return_start: str,
        return_end: str,
        persist: bool,
    ):
        # 返程必须与去程首尾对调，否则拒绝并点名。
        if return_start != outbound_end or return_end != outbound_start:
            problems = []
            if return_start != outbound_end:
                problems.append(
                    f"返程起点 return_start={return_start!r} 必须等于去程终点 outbound_end={outbound_end!r}"
                )
            if return_end != outbound_start:
                problems.append(
                    f"返程终点 return_end={return_end!r} 必须等于去程起点 outbound_start={outbound_start!r}"
                )
            raise ValueError("；".join(problems))

        edges = edges_repo.list_pairs(self._conn)
        rules = rules_repo.as_calc_rules(self._conn)
        result = quote_round_trip(edges, outbound_start, outbound_end, rules)

        outbound_id = inbound_id = None
        # 不保存不写库；任一侧不可达两条都不写。
        if persist and result["reachable"]:
            outbound_side = result["outbound"]
            inbound_side = result["inbound"]
            outbound_record = {**outbound_side, "direction": "outbound", "total_fare": result["total_fare"]}
            inbound_record = {**inbound_side, "direction": "inbound", "total_fare": result["total_fare"]}
            outbound_id, inbound_id = runs_repo.insert_pair(
                self._conn,
                "roundtrip",
                {"start": outbound_start, "end": outbound_end, "direction": "outbound"},
                outbound_record,
                {"start": outbound_end, "end": outbound_start, "direction": "inbound"},
                inbound_record,
            )

        return {
            "outbound_id": outbound_id,
            "inbound_id": inbound_id,
            **result,
        }

    def history(self, limit=50):
        return runs_repo.list_recent(self._conn, limit)

    def run(self, run_id: int):
        row = runs_repo.get_by_id(self._conn, run_id)
        if row is None:
            return None
        row = dict(row)
        mate_id = row.get("pair_id")
        if mate_id:
            mate = runs_repo.get_by_id(self._conn, mate_id)
            if mate is not None:
                mine = json.loads(row["result_json"])
                other = json.loads(mate["result_json"])
                mine["path"] = other.get("path")
                mine["hops"] = other.get("hops")
                mine["fare"] = other.get("fare")
                mine["start"] = other.get("start")
                mine["end"] = other.get("end")
                row["result_json"] = json.dumps(mine, ensure_ascii=False)
        row["pair_id"] = row["id"]
        return row

    def dashboard(self):
        st = stations_repo.list_all(self._conn)
        clean = [s for s in st if "种子" not in s["name"]]
        dirty = [s for s in st if "种子" in s["name"]]
        return {
            "station_count": len(st),
            "edge_count": len(edges_repo.list_pairs(self._conn)),
            "clean_stations": len(clean),
            "dirty_stations": len(dirty),
        }
