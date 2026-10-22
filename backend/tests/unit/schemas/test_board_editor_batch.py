import pytest
from pydantic import ValidationError

from src.exceptions.board_editor import BoardEditorValidationError
from src.schemas.board_editor import BoardEditorMetadata, BoardObjectRef
from src.schemas.board_editor_batch import BoardBatchEditorInsert
from src.services.board_editor_batch import metadata_with_inserted_objects


def insertion():
    return BoardBatchEditorInsert(
        expected_revision=3,
        groups=[{"id": "new-group", "name": "Схема", "members": ["shape", "note"]}],
        locked=["note"],
    )


def test_insert_maps_both_kinds_and_keeps_original_metadata():
    original = BoardEditorMetadata(locked=[{"type": "shape", "id": 9}])
    mapped = metadata_with_inserted_objects(
        original,
        insertion(),
        {
            "shape": BoardObjectRef(type="shape", id=11),
            "note": BoardObjectRef(type="sticker", id=12),
        },
    )
    assert [(ref.type, ref.id) for ref in mapped.groups[0].members] == [
        ("shape", 11),
        ("sticker", 12),
    ]
    assert [(ref.type, ref.id) for ref in mapped.locked] == [("shape", 9), ("sticker", 12)]
    assert original.groups == [] and len(original.locked) == 1


def test_insert_rejects_partial_mappings_instead_of_losing_group_members():
    with pytest.raises(BoardEditorValidationError):
        metadata_with_inserted_objects(
            BoardEditorMetadata(), insertion(), {"shape": BoardObjectRef(type="shape", id=11)}
        )


def test_insert_rejects_alias_ids_and_collisions_with_existing_groups():
    same = BoardObjectRef(type="shape", id=11)
    with pytest.raises(ValidationError):
        metadata_with_inserted_objects(
            BoardEditorMetadata(), insertion(), {"shape": same, "note": same}
        )
    existing = BoardEditorMetadata(
        groups=[
            {
                "id": "new-group",
                "name": "Старая",
                "members": [{"type": "shape", "id": 1}],
            }
        ]
    )
    with pytest.raises(ValidationError):
        metadata_with_inserted_objects(
            existing,
            insertion(),
            {
                "shape": BoardObjectRef(type="shape", id=11),
                "note": BoardObjectRef(type="sticker", id=12),
            },
        )


@pytest.mark.parametrize(
    "patch",
    [
        {"expected_revision": 0},
        {"locked": ["note", "note"]},
        {"groups": [{"id": "g", "name": "Группа", "members": ["shape", "shape"]}]},
    ],
)
def test_insert_schema_rejects_invalid_metadata(patch):
    with pytest.raises(ValidationError):
        BoardBatchEditorInsert.model_validate({**insertion().model_dump(), **patch})
