"""Metadata changes carried in the atomic mixed board batch."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Keep this request schema independent of board_editor/board_shapes imports:
# board_editor imports BoardShapeCreateSchema, so a reverse import would cycle.
Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
Name = Annotated[str, Field(min_length=1, max_length=120)]


class BoardInsertedGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: Identifier
    name: Name
    members: list[Identifier] = Field(min_length=2, max_length=2000)


class BoardBatchEditorInsert(BaseModel):
    """Members/locks address client IDs of objects created in the SAME batch."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_revision: int = Field(ge=1, strict=True)
    groups: list[BoardInsertedGroup] = Field(default_factory=list, max_length=200)
    locked: list[Identifier] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        group_ids = [group.id for group in self.groups]
        members = [member for group in self.groups for member in group.members]
        if len(group_ids) != len(set(group_ids)) or len(members) != len(set(members)):
            raise ValueError("Inserted groups must have unique IDs and disjoint membership.")
        if len(members) > 2000 or len(self.locked) != len(set(self.locked)):
            raise ValueError("Inserted metadata has duplicate locks or exceeds the member limit.")
        return self


class BoardBatchEditorState(BaseModel):
    """Полный снимок редактора; client_id разрешены только для объектов этого пакета."""

    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)
    metadata: dict[str, Any]

    @field_validator("metadata")
    @classmethod
    def original_collections(cls, value):
        for name in ("groups", "locked", "templates"):
            if not isinstance(value.get(name, []), list):
                raise ValueError("Коллекции настроек редактора должны быть списками.")
        for group in value.get("groups", []):
            if not isinstance(group, dict) or not isinstance(group.get("members"), list):
                raise ValueError("Члены группы должны быть списком ссылок.")
        return value
