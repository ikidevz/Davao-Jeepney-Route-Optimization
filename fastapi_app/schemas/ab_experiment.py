from typing import Literal
from pydantic import BaseModel, Field, model_validator


Group = Literal["control", "treatment"]
RouteVariant = Literal["A_existing_route", "B_express_direct"]


class ABExperimentPayload(BaseModel):
    experiment_record_id: str = Field(min_length=3, max_length=20)
    experiment_id: str = Field(default="EXP-001", max_length=10)
    passenger_id: str = Field(pattern=r"^PAX-\d{4}$")
    cluster_id: Literal[3]  # only Cluster 3 (Underserved Riders) allowed in A/B experiment
    group: Group
    route_variant: RouteVariant
    test_week: int = Field(ge=1, le=8)
    simulated_travel_time_min: int = Field(gt=0)
    simulated_fare_php: float = Field(gt=0)
    transfers_needed: int = Field(ge=0, le=3)
    satisfaction_score: int = Field(ge=1, le=5)
    would_use_again: bool

    @model_validator(mode="after")
    def validate_group_variant(self) -> "ABExperimentPayload":
        if self.group == "control" and self.route_variant != "A_existing_route":
            raise ValueError(
                "control group must use route_variant A_existing_route"
            )
        if self.group == "treatment" and self.route_variant != "B_express_direct":
            raise ValueError(
                "treatment group must use route_variant B_express_direct"
            )
        return self
