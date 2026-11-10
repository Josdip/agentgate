"""Typed policy editing; no executable expressions or wildcard permissions."""

from typing import Literal

from pydantic import Field, model_validator

from .policy import DOCUMENTS, SCHEMAS, StrictModel


class RuleSpec(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    tool: str = Field(min_length=1, max_length=80)
    decision: Literal["allow", "deny", "review"]
    scope: list[str] = Field(max_length=25)
    approval_threshold_cents: int | None = Field(default=None, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def valid_scope(self):
        if not self.name.strip() or self.tool not in SCHEMAS:
            raise ValueError("Choose a registered tool and a nonblank name")
        if self.decision != "deny" and not self.scope:
            raise ValueError("Allow/review rules require exact targets")
        if len(set(self.scope)) != len(self.scope) or any(
            not value or len(value) > 200 or value != value.strip() or "*" in value
            for value in self.scope
        ):
            raise ValueError("Targets must be unique, nonblank exact values without wildcards")
        if (
            self.tool == "documents.read"
            and self.decision != "deny"
            and any(target not in DOCUMENTS for target in self.scope)
        ):
            raise ValueError("Only existing synthetic documents can be granted")
        if (
            self.tool == "refunds.create"
            and self.decision != "deny"
            and any(target not in {"T-1001", "T-1002"} for target in self.scope)
        ):
            raise ValueError("Choose a supported synthetic ticket")
        monetary = self.tool in {"refunds.create", "payments.create"}
        needs_threshold = monetary and self.decision == "allow"
        if needs_threshold != (self.approval_threshold_cents is not None):
            raise ValueError("Only allow rules for refunds/payments require an automatic limit")
        return self


class RuleChange(StrictModel):
    revision: int = Field(ge=1)
    rule: RuleSpec
