"""Schemas de la reprogramación por enlace (C-17 D5). ``extra='forbid'`` (regla dura 4)."""

from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator


class ReprogramarIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inicio: AwareDatetime

    @field_validator("inicio")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
