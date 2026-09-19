import json

from fastapi import APIRouter, HTTPException

from app.services.metro_service import MetroService

router = APIRouter(tags=["history"])


def _decode(item: dict | None) -> dict | None:
    if item is None:
        return None
    item["input"] = json.loads(item.pop("input_json"))
    item["result"] = json.loads(item.pop("result_json"))
    return item


@router.get("/history")
def history(limit: int = 50):
    with MetroService() as s:
        return {"items": [_decode(dict(it)) for it in s.history(limit)]}


@router.get("/history/{run_id}")
def history_detail(run_id: int):
    with MetroService() as s:
        item = _decode(s.run(run_id))
    if item is None:
        raise HTTPException(status_code=404, detail=f"记录 #{run_id} 不存在")
    return item
