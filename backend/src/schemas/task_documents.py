from pydantic import BaseModel, Field

from src.schemas.document_links import DocumentLinkSchema
from src.schemas.documents import DocumentDetailSchema
from src.schemas.task_attachments import TaskAttachmentSchema


class TaskDocumentImportSchema(BaseModel):
    """Результат импорта исходного файла в документы проекта."""

    attachment: TaskAttachmentSchema = Field(
        ...,
        description="Сохранённый оригинал в файлах задачи.",
    )
    document: DocumentDetailSchema = Field(
        ...,
        description="Текстовый документ проекта, полученный из файла.",
    )
    link: DocumentLinkSchema = Field(
        ...,
        description="Связь созданного документа с задачей.",
    )
