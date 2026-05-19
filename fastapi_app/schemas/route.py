from pydantic import BaseModel, Field, model_validator
from typing import Annotated


class RoutePayload(BaseModel):
    route_id: Annotated[str, Field(pattern=r"^R\d{2}$")]
    route_name: str = Field(min_length=3, max_length=100)
    origin: str = Field(min_length=2, max_length=100)
    destination: str = Field(min_length=2, max_length=100)
    district_covered: str = Field(min_length=2, max_length=50)
    route_length_km: float = Field(gt=0, le=200)
    num_stops: int = Field(gt=0, le=100)
    base_fare_php: float = Field(ge=13.00)
    peak_frequency_min: int = Field(gt=0, le=120)
    off_peak_frequency_min: int = Field(gt=0, le=180)
    is_active: bool = True

    @model_validator(mode="after")
    def offpeak_gte_peak(self) -> "RoutePayload":
        if self.off_peak_frequency_min < self.peak_frequency_min:
            raise ValueError(
                "off_peak_frequency_min must be >= peak_frequency_min"
            )
        return self
