import json

from fastapi import APIRouter, HTTPException

from app.engines.route_quote import RoundTripDataError
from app.schemas.quote import QuoteRequest, RoundTripQuoteRequest
from app.services.metro_service import MetroService

router = APIRouter(tags=["quote"])


@router.post("/quote")
def post_quote(body: QuoteRequest):
    with MetroService() as s:
        return s.quote(body.start, body.end, body.persist)


@router.post("/quote/roundtrip")
def post_quote_roundtrip(body: RoundTripQuoteRequest):
    with MetroService() as s:
        try:
            return s.quote_round_trip(
                body.outbound_start,
                body.outbound_end,
                body.return_start,
                body.return_end,
                body.persist,
            )
        except ValueError as exc:
            # 返程未与去程首尾对调：拒绝并点名。
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RoundTripDataError as exc:
            # 无向图上两侧站数不一致：底层数据错误，拒绝写入。
            raise HTTPException(status_code=500, detail=f"数据错误：{exc}") from exc
