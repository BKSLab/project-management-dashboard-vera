"""Agent diagram inputs: graph semantics, strict updates and board selection."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.schemas.board_shapes import (
    MAX_BATCH_OPS,
    MAX_SHAPE_LABEL_LENGTH,
    BoardShapeChangesSchema,
    ShapeColor,
)

NodeKey = Annotated[str, Field(min_length=1, max_length=48, pattern=r"^[a-zA-Z0-9_-]+$")]


class DiagramModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoardSceneInput(DiagramModel):
    board_id: int = Field(gt=0)
    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=200)


class DiagramNode(DiagramModel):
    key: NodeKey
    label: str = Field(min_length=1, max_length=MAX_SHAPE_LABEL_LENGTH)
    kind: Literal["rect", "ellipse", "diamond", "text"] = "rect"
    color: ShapeColor = "none"

    @field_validator("label")
    @classmethod
    def valid_label(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("Node label must be nonempty and contain no null bytes.")
        return value


class NewNodeRef(DiagramModel):
    type: Literal["node"]
    key: NodeKey


class ExistingObjectRef(DiagramModel):
    type: Literal["shape", "sticker"]
    id: int = Field(gt=0)


DiagramRef = Annotated[NewNodeRef | ExistingObjectRef, Field(discriminator="type")]


class DiagramEdge(DiagramModel):
    source: DiagramRef
    target: DiagramRef
    label: str = Field("", max_length=MAX_SHAPE_LABEL_LENGTH)

    @field_validator("label")
    @classmethod
    def valid_label(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Edge label must contain no null bytes.")
        return value


class BoardDiagramInput(DiagramModel):
    board_id: int = Field(gt=0)
    direction: Literal["TB", "LR"] = "TB"
    nodes: list[DiagramNode] = Field(default_factory=list, max_length=100)
    edges: list[DiagramEdge] = Field(default_factory=list, max_length=300)

    @model_validator(mode="after")
    def valid_graph(self) -> Self:
        keys = [node.key for node in self.nodes]
        if len(keys) != len(set(keys)):
            raise ValueError("Node keys must be unique.")
        if not self.nodes and not self.edges:
            raise ValueError("Provide at least one node or edge.")
        if len(self.nodes) + len(self.edges) > MAX_BATCH_OPS:
            raise ValueError("Diagram exceeds batch operation limit.")
        known = set(keys)
        for edge in self.edges:
            for ref in (edge.source, edge.target):
                if ref.type == "node" and ref.key not in known:
                    raise ValueError(f"Unknown node key: {ref.key}.")
        return self


class AgentShapeUpdate(DiagramModel):
    id: int = Field(gt=0)
    revision: int = Field(ge=1)
    data: BoardShapeChangesSchema

    @model_validator(mode="after")
    def existing_refs_only(self) -> Self:
        for ref in (self.data.start_ref, self.data.end_ref):
            if ref is not None and ref.client_id is not None:
                raise ValueError("Updates accept only existing object references.")
        return self


class BoardShapeUpdatesInput(DiagramModel):
    board_id: int = Field(gt=0)
    updates: list[AgentShapeUpdate] = Field(min_length=1, max_length=MAX_BATCH_OPS)

    @model_validator(mode="after")
    def unique_updates(self) -> Self:
        ids = [item.id for item in self.updates]
        if len(ids) != len(set(ids)):
            raise ValueError("Each shape may be updated only once per batch.")
        return self


class ArrangeObjectRef(ExistingObjectRef):
    revision: int = Field(ge=1)


class BoardArrangeInput(DiagramModel):
    board_id: int = Field(gt=0)
    expected_revision: int = Field(ge=0)
    objects: list[ArrangeObjectRef] = Field(min_length=1, max_length=200)
    mode: Literal["layout", "align"]
    direction: Literal["TB", "LR"] = "TB"
    alignment: Literal["left", "center", "right", "top", "middle", "bottom"] | None = None

    @model_validator(mode="after")
    def valid_selection(self) -> Self:
        keys = [(item.type, item.id) for item in self.objects]
        if len(keys) != len(set(keys)):
            raise ValueError("Each selected object must occur only once.")
        if self.mode == "align" and self.alignment is None:
            raise ValueError("alignment is required for align.")
        return self


class PersonalBoardsInput(DiagramModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=200)
