from typing import Annotated, Literal
from pydantic import BaseModel, Field


VehicleType = Literal["traditional", "modernized_PUV"]
FuelType = Literal["diesel", "euro4_diesel", "electric"]


class VehiclePayload(BaseModel):
    vehicle_id: str = Field(pattern=r"^VHC-\d{3}$")
    plate_number: str = Field(min_length=5, max_length=15)
    vehicle_type: VehicleType
    capacity: int = Field(ge=10, le=30)
    fuel_type: FuelType
    year_manufactured: int = Field(ge=2000, le=2025)
    route_assigned: Annotated[str, Field(pattern=r"^R\d{2}$")]
    operator_id: str = Field(pattern=r"^OPR-\d{3}$")
    avg_fuel_cost_daily_php: float = Field(gt=0)
    is_active: bool = True
