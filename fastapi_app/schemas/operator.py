from typing import Literal
from pydantic import BaseModel, Field


FranchiseType = Literal["individual", "cooperative", "corporation"]


class OperatorPayload(BaseModel):
    operator_id: str = Field(pattern=r"^OPR-\d{3}$")
    operator_name: str = Field(min_length=2, max_length=150)
    contact_number: str | None = Field(default=None, max_length=20)
    franchise_type: FranchiseType
    num_units_owned: int = Field(ge=1)
    base_district: str = Field(min_length=2, max_length=50)
    is_compliant_puv: bool = False
