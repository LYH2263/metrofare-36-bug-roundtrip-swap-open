from pydantic import BaseModel


class QuoteRequest(BaseModel):
    start: str
    end: str
    persist: bool = True


class RoundTripQuoteRequest(BaseModel):
    outbound_start: str
    outbound_end: str
    return_start: str
    return_end: str
    persist: bool = True
