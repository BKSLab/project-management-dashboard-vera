"""Map template grouping into server IDs inside the mixed board batch transaction."""

from src.exceptions.board_editor import BoardEditorValidationError
from src.schemas.board_editor import BoardEditorGroup, BoardEditorMetadata, BoardObjectRef
from src.schemas.board_editor_batch import BoardBatchEditorInsert


def metadata_with_inserted_objects(
    metadata: BoardEditorMetadata,
    insertion: BoardBatchEditorInsert,
    created_objects: dict[str, BoardObjectRef],
) -> BoardEditorMetadata:
    """No commit or I/O. Caller owns board row lock, revision check and rollback.

    created_objects MUST only contain objects created by this transaction, including
    both shapes and stickers. Caller then validates board membership and persists
    the returned metadata with BoardEditorRepository.save_metadata before committing.
    """

    def identify(client_id: str) -> BoardObjectRef:
        result = created_objects.get(client_id)
        if result is None:
            raise BoardEditorValidationError(
                "Metadata шаблона ссылается на объект вне создаваемого пакета."
            )
        return result

    groups = [
        BoardEditorGroup(
            id=group.id,
            name=group.name,
            members=[identify(client_id) for client_id in group.members],
        )
        for group in insertion.groups
    ]
    return BoardEditorMetadata.model_validate(
        {
            **metadata.model_dump(mode="json"),
            "groups": [*metadata.groups, *groups],
            "locked": [*metadata.locked, *(identify(key) for key in insertion.locked)],
        }
    )
