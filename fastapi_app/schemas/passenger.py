from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, Field


DestinationType = Literal["work", "school", "market", "hospital", "mall"]
TripPurpose = Literal["daily_commute", "occasional", "weekend_only"]
IncomeBracket = Literal["low", "middle", "high"]


class PassengerPayload(BaseModel):
    passenger_id: str = Field(pattern=r"^PAX-\d{4}$")
    survey_date: date
    origin_barangay: str = Field(min_length=2, max_length=100)
    origin_district: str = Field(min_length=2, max_length=50)
    destination_type: DestinationType
    trip_purpose: TripPurpose
    primary_route_used: Annotated[str, Field(pattern=r"^R\d{2}$")]
    trips_per_week: int = Field(ge=0, le=14)
    avg_fare_paid_php: float = Field(gt=0)
    transfers_required: int = Field(ge=0, le=3)
    wait_time_min: int = Field(ge=0)
    travel_time_min: int = Field(gt=0)
    satisfaction_score: int = Field(ge=1, le=5)
    income_bracket: IncomeBracket
    prefers_aircon: bool = False
