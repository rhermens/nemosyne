from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nemosyne.data.sequence import SemanticOutcome, TriggerReason


class EventAnnotation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    type: Literal["event"] = "event"
    index: int = Field(ge=0)
    semantic_outcome: SemanticOutcome


class MessageAnnotation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    type: Literal["message"] = "message"
    index: int = Field(ge=0)
    semantic_outcome: SemanticOutcome


class SkillUsageAnnotation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    type: Literal["skill_usage"] = "skill_usage"
    index: int = Field(ge=0)
    trigger_reason: TriggerReason


SequenceAnnotation = EventAnnotation | MessageAnnotation | SkillUsageAnnotation


class SessionAnnotation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    sequence: list[SequenceAnnotation]

    @model_validator(mode="after")
    def indexes_are_unique(self) -> "SessionAnnotation":
        indexes = [item.index for item in self.sequence]
        if len(indexes) != len(set(indexes)):
            raise ValueError("annotation sequence indexes must be unique")
        return self
