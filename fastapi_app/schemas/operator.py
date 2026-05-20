from typing import Literal
from pydantic import BaseModel, Field

FranchiseType = Literal["individual", "cooperative", "corporation"]


class OperatorPayload(BaseModel):
    operator_id:        str = Field(pattern=r"^OPR-\d{3}$")
    operator_name:      str = Field(min_length=2, max_length=150)
    franchise_type:     FranchiseType
    num_units:          int = Field(ge=1, le=100)
    district_base:      str = Field(min_length=2, max_length=50)
    contact_number:     str = Field(min_length=7, max_length=20)
    is_compliant_puv:   bool = True
    avg_monthly_revenue_php: float = Field(gt=0)
