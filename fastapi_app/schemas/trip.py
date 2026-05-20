from datetime import date, time
from typing import Annotated, Literal
from pydantic import BaseModel, Field, model_validator

TimePeriod = Literal["AM_peak", "midday", "PM_peak", "off_peak"]
DayOfWeek = Literal["Monday", "Tuesday", "Wednesday",
                    "Thursday", "Friday", "Saturday", "Sunday"]


class TripPayload(BaseModel):
    trip_id:            str = Field(pattern=r"^TRP-\d{7}$")
    route_id:           Annotated[str, Field(pattern=r"^R\d{2}$")]
    vehicle_id:         str = Field(pattern=r"^VHC-\d{3}$")
    trip_date:          date
    departure_time:     time
    arrival_time:       time
    time_period:        TimePeriod
    day_of_week:        DayOfWeek
    passengers_boarded: int = Field(ge=1, le=50)
    revenue_php:        float = Field(ge=0)
    travel_time_min:    int = Field(gt=0)
    scheduled_time_min: int = Field(gt=0)
    delay_min:          int = Field(ge=0)
    is_on_time:         bool
    is_rainy_day:       bool
    load_factor:        float = Field(ge=0.0, le=1.5)
    created_at:         str

    @model_validator(mode="after")
    def validate_on_time_vs_delay(self) -> "TripPayload":
        if self.is_on_time and self.delay_min > 5:
            raise ValueError(
                f"is_on_time=True but delay_min={self.delay_min} > 5"
            )
        return self
