import json
import sqlite3
from datetime import datetime, timezone


def insert(conn: sqlite3.Connection, kind: str, payload: dict, result: dict) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO calc_runs(kind, input_json, result_json, created_at) VALUES (?,?,?,?)",
        (kind, json.dumps(payload, ensure_ascii=False), json.dumps(result, ensure_ascii=False), now),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_pair(
    conn: sqlite3.Connection,
    kind: str,
    outbound_payload: dict,
    outbound_result: dict,
    inbound_payload: dict,
    inbound_result: dict,
) -> tuple[int, int]:
    """同一事务写往返两条记录，并互记对方编号。返回 (去程id, 返程id)。

    任一步失败整体回滚：去程返程要么都落库，要么都不落库。
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        cur = conn.execute(
            "INSERT INTO calc_runs(kind, input_json, result_json, created_at, pair_id) VALUES (?,?,?,?,?)",
            (
                kind,
                json.dumps(outbound_payload, ensure_ascii=False),
                json.dumps(outbound_result, ensure_ascii=False),
                now,
                None,
            ),
        )
        outbound_id = int(cur.lastrowid)
        cur = conn.execute(
            "INSERT INTO calc_runs(kind, input_json, result_json, created_at, pair_id) VALUES (?,?,?,?,?)",
            (
                kind,
                json.dumps(inbound_payload, ensure_ascii=False),
                json.dumps(inbound_result, ensure_ascii=False),
                now,
                outbound_id,
            ),
        )
        inbound_id = int(cur.lastrowid)
        conn.execute("UPDATE calc_runs SET pair_id=? WHERE id=?", (inbound_id, outbound_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return outbound_id, inbound_id


def list_recent(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    q = "SELECT * FROM calc_runs ORDER BY id DESC LIMIT ?"
    return [dict(r) for r in conn.execute(q, (limit,)).fetchall()]


def get_by_id(conn: sqlite3.Connection, run_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM calc_runs WHERE id=?", (run_id,)).fetchone()
    return dict(row) if row else None
