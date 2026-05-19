from typing import Annotated, Literal
from pydantic import BaseModel, Field


StopType = Literal["terminal", "market", "school", "hospital", "mall", "residential"]


class StopPayload(BaseModel):
    stop_id: Annotated[str, Field(pattern=r"^S\d{3}$")]
    stop_name: str = Field(min_length=2, max_length=150)
    barangay: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=50)
    latitude: float = Field(ge=6.8, le=7.5)
    longitude: float = Field(ge=125.0, le=126.0)
    stop_type: StopType
    has_shelter: bool = False
    avg_daily_boardings: int = Field(ge=0)
    route_id: Annotated[str, Field(pattern=r"^R\d{2}$")]
