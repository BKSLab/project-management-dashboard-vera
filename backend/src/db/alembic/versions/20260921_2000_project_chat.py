"""Общий чат проекта: история, read state и transactional outbox. Без backfill."""

from alembic import op

revision = "f29c7618a403"
down_revision = "ed781b034ac9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создаёт схему и lifecycle только для будущих проектов."""
    op.execute(
        "\nCREATE TABLE project_chats (\n\tid SERIAL NOT NULL, \n\tproject_id INTEGER NOT NULL, \n\tlast_event_seq BIGINT DEFAULT '0' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (id, project_id), \n\tUNIQUE (project_id), \n\tFOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("COMMENT ON COLUMN project_chats.id IS 'ID чата.'")
    op.execute("COMMENT ON COLUMN project_chats.project_id IS 'Проект чата.'")
    op.execute("COMMENT ON COLUMN project_chats.last_event_seq IS 'Последний курсор событий.'")
    op.execute("COMMENT ON COLUMN project_chats.created_at IS 'Дата и время создания записи.'")
    op.execute(
        "COMMENT ON COLUMN project_chats.updated_at IS 'Дата и время последнего обновления записи.'"
    )
    op.execute(
        "\nCREATE TABLE chat_events (\n\tid BIGSERIAL NOT NULL, \n\tchat_id INTEGER NOT NULL, \n\tseq BIGINT NOT NULL, \n\tevent_type VARCHAR(40) NOT NULL, \n\tpayload JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tpublished_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tUNIQUE (chat_id, seq), \n\tFOREIGN KEY(chat_id) REFERENCES project_chats (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_chat_events_pending ON chat_events (id) WHERE published_at IS NULL")
    op.execute("COMMENT ON COLUMN chat_events.id IS 'ID записи outbox.'")
    op.execute("COMMENT ON COLUMN chat_events.chat_id IS 'Чат события.'")
    op.execute("COMMENT ON COLUMN chat_events.seq IS 'Курсор внутри чата.'")
    op.execute("COMMENT ON COLUMN chat_events.event_type IS 'Тип изменения.'")
    op.execute(
        "COMMENT ON COLUMN chat_events.payload IS 'ID изменённых объектов без копии переписки.'"
    )
    op.execute("COMMENT ON COLUMN chat_events.created_at IS 'Время события.'")
    op.execute("COMMENT ON COLUMN chat_events.published_at IS 'Время передачи Redis.'")
    op.execute(
        "\nCREATE TABLE chat_messages (\n\tid SERIAL NOT NULL, \n\tchat_id INTEGER NOT NULL, \n\tproject_id INTEGER NOT NULL, \n\tseq BIGINT NOT NULL, \n\tauthor_user_id INTEGER, \n\tcontent TEXT NOT NULL, \n\tclient_message_id UUID NOT NULL, \n\treply_to_message_id INTEGER, \n\trevision INTEGER DEFAULT '1' NOT NULL, \n\tedited_at TIMESTAMP WITH TIME ZONE, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tsearch_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('russian', coalesce(content, '')) || to_tsvector('simple', coalesce(content, ''))) STORED NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(chat_id, project_id) REFERENCES project_chats (id, project_id) ON DELETE CASCADE, \n\tUNIQUE (id, chat_id), \n\tUNIQUE (chat_id, seq), \n\tUNIQUE (chat_id, author_user_id, client_message_id), \n\tCONSTRAINT fk_chat_reply_same_chat FOREIGN KEY(reply_to_message_id, chat_id) REFERENCES chat_messages (id, chat_id), \n\tFOREIGN KEY(author_user_id) REFERENCES users (id) ON DELETE SET NULL\n)\n\n"
    )
    op.execute("CREATE INDEX ix_chat_messages_search ON chat_messages USING gin (search_vector)")
    op.execute("COMMENT ON COLUMN chat_messages.id IS 'ID сообщения.'")
    op.execute("COMMENT ON COLUMN chat_messages.chat_id IS 'Чат сообщения.'")
    op.execute("COMMENT ON COLUMN chat_messages.project_id IS 'Проект сообщения.'")
    op.execute("COMMENT ON COLUMN chat_messages.seq IS 'Порядок внутри чата.'")
    op.execute("COMMENT ON COLUMN chat_messages.author_user_id IS 'Автор.'")
    op.execute("COMMENT ON COLUMN chat_messages.content IS 'Безопасный текст сообщения.'")
    op.execute("COMMENT ON COLUMN chat_messages.client_message_id IS 'Ключ повторной отправки.'")
    op.execute("COMMENT ON COLUMN chat_messages.reply_to_message_id IS 'Ответ в том же чате.'")
    op.execute("COMMENT ON COLUMN chat_messages.revision IS 'Версия для защиты правок.'")
    op.execute("COMMENT ON COLUMN chat_messages.edited_at IS 'Время правки.'")
    op.execute("COMMENT ON COLUMN chat_messages.deleted_at IS 'Время удаления.'")
    op.execute(
        "COMMENT ON COLUMN chat_messages.search_vector IS 'Полнотекстовый индекс русского и английского текста.'"
    )
    op.execute("COMMENT ON COLUMN chat_messages.created_at IS 'Дата и время создания записи.'")
    op.execute(
        "COMMENT ON COLUMN chat_messages.updated_at IS 'Дата и время последнего обновления записи.'"
    )
    op.execute(
        "\nCREATE TABLE chat_read_states (\n\tchat_id INTEGER NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tlast_read_seq BIGINT DEFAULT '0' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (chat_id, user_id), \n\tFOREIGN KEY(chat_id) REFERENCES project_chats (id) ON DELETE CASCADE, \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("COMMENT ON COLUMN chat_read_states.chat_id IS 'Чат.'")
    op.execute("COMMENT ON COLUMN chat_read_states.user_id IS 'Участник.'")
    op.execute(
        "COMMENT ON COLUMN chat_read_states.last_read_seq IS 'Порядок последнего прочитанного сообщения.'"
    )
    op.execute("COMMENT ON COLUMN chat_read_states.created_at IS 'Дата и время создания записи.'")
    op.execute(
        "COMMENT ON COLUMN chat_read_states.updated_at IS 'Дата и время последнего обновления записи.'"
    )
    op.execute(
        "\nCREATE TABLE chat_attachments (\n\tid UUID NOT NULL, \n\tchat_id INTEGER NOT NULL, \n\tmessage_id INTEGER, \n\tuploader_id INTEGER, \n\tstorage_key VARCHAR(500) NOT NULL, \n\toriginal_name VARCHAR(255) NOT NULL, \n\tcontent_type VARCHAR(150) NOT NULL, \n\tsize_bytes INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(message_id, chat_id) REFERENCES chat_messages (id, chat_id) ON DELETE CASCADE, \n\tFOREIGN KEY(chat_id) REFERENCES project_chats (id) ON DELETE CASCADE, \n\tFOREIGN KEY(uploader_id) REFERENCES users (id) ON DELETE SET NULL\n)\n\n"
    )
    op.execute(
        "CREATE INDEX ix_chat_attachments_drafts ON chat_attachments (chat_id, uploader_id, created_at)"
    )
    op.execute("CREATE INDEX ix_chat_attachments_message ON chat_attachments (message_id)")
    op.execute("COMMENT ON COLUMN chat_attachments.id IS 'ID загрузки.'")
    op.execute("COMMENT ON COLUMN chat_attachments.chat_id IS 'Чат.'")
    op.execute("COMMENT ON COLUMN chat_attachments.message_id IS 'Сообщение; NULL у черновика.'")
    op.execute("COMMENT ON COLUMN chat_attachments.uploader_id IS 'Автор загрузки.'")
    op.execute("COMMENT ON COLUMN chat_attachments.storage_key IS 'Внутренний ключ файла.'")
    op.execute("COMMENT ON COLUMN chat_attachments.original_name IS 'Безопасное имя.'")
    op.execute("COMMENT ON COLUMN chat_attachments.content_type IS 'Проверенный MIME.'")
    op.execute("COMMENT ON COLUMN chat_attachments.size_bytes IS 'Размер содержимого.'")
    op.execute("COMMENT ON COLUMN chat_attachments.created_at IS 'Дата и время создания записи.'")
    op.execute(
        "COMMENT ON COLUMN chat_attachments.updated_at IS 'Дата и время последнего обновления записи.'"
    )
    op.execute(
        "\nCREATE TABLE chat_message_entities (\n\tid SERIAL NOT NULL, \n\tmessage_id INTEGER NOT NULL, \n\tentity_type VARCHAR(16) NOT NULL, \n\tentity_id INTEGER NOT NULL, \n\tposition INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (message_id, entity_type, entity_id), \n\tFOREIGN KEY(message_id) REFERENCES chat_messages (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute(
        "CREATE INDEX ix_chat_message_entities_message_id ON chat_message_entities (message_id)"
    )
    op.execute("COMMENT ON COLUMN chat_message_entities.id IS 'ID ссылки.'")
    op.execute("COMMENT ON COLUMN chat_message_entities.message_id IS 'Сообщение.'")
    op.execute("COMMENT ON COLUMN chat_message_entities.entity_type IS 'Тип объекта.'")
    op.execute("COMMENT ON COLUMN chat_message_entities.entity_id IS 'ID объекта.'")
    op.execute("COMMENT ON COLUMN chat_message_entities.position IS 'Положение карточки.'")
    op.execute("COMMENT ON COLUMN chat_message_entities.created_at IS 'Время добавления ссылки.'")
    op.execute(
        "\nCREATE TABLE chat_message_mentions (\n\tmessage_id INTEGER NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tPRIMARY KEY (message_id, user_id), \n\tFOREIGN KEY(message_id) REFERENCES chat_messages (id) ON DELETE CASCADE, \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("COMMENT ON COLUMN chat_message_mentions.message_id IS 'Сообщение.'")
    op.execute("COMMENT ON COLUMN chat_message_mentions.user_id IS 'Упомянутый участник.'")
    op.execute(
        "\nCREATE TABLE chat_reactions (\n\tmessage_id INTEGER NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\treaction VARCHAR(16) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (message_id, user_id, reaction), \n\tFOREIGN KEY(message_id) REFERENCES chat_messages (id) ON DELETE CASCADE, \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("COMMENT ON COLUMN chat_reactions.message_id IS 'Сообщение.'")
    op.execute("COMMENT ON COLUMN chat_reactions.user_id IS 'Участник.'")
    op.execute("COMMENT ON COLUMN chat_reactions.reaction IS 'Символ реакции.'")
    op.execute("COMMENT ON COLUMN chat_reactions.created_at IS 'Дата и время создания записи.'")
    op.execute(
        "COMMENT ON COLUMN chat_reactions.updated_at IS 'Дата и время последнего обновления записи.'"
    )
    op.execute(
        "\nCREATE OR REPLACE FUNCTION chat_entities_invalidated() RETURNS trigger AS $$\nBEGIN\n    IF TG_TABLE_NAME = 'projects' THEN\n        PERFORM chat_emit(NEW.id, 'entities.refresh', '{}'::jsonb);\n    ELSE\n        PERFORM chat_emit(NEW.project_id, 'entities.refresh', '{}'::jsonb);\n    END IF;\n    RETURN NULL;\nEND;\n$$ LANGUAGE plpgsql;\n"
    )
    op.execute(
        "\nCREATE OR REPLACE FUNCTION chat_emit(pid integer, kind text, data jsonb) RETURNS void AS $$\nDECLARE cid integer; next_seq bigint;\nBEGIN\n    UPDATE project_chats SET last_event_seq = last_event_seq + 1, updated_at = now()\n        WHERE project_id = pid RETURNING id, last_event_seq INTO cid, next_seq;\n    IF cid IS NOT NULL THEN\n        INSERT INTO chat_events(chat_id, seq, event_type, payload)\n            VALUES (cid, next_seq, kind, data);\n    END IF;\nEND;\n$$ LANGUAGE plpgsql;\n"
    )
    op.execute(
        "\nCREATE OR REPLACE FUNCTION chat_project_created() RETURNS trigger AS $$\nBEGIN\n    INSERT INTO project_chats(project_id) VALUES (NEW.id);\n    RETURN NULL;\nEND;\n$$ LANGUAGE plpgsql;\n"
    )
    op.execute(
        "\nCREATE OR REPLACE FUNCTION chat_membership_changed() RETURNS trigger AS $$\nDECLARE cid integer; boundary bigint;\nBEGIN\n    IF TG_OP = 'DELETE' THEN\n        DELETE FROM chat_read_states WHERE user_id = OLD.user_id AND chat_id IN\n            (SELECT id FROM project_chats WHERE project_id = OLD.project_id);\n        PERFORM chat_emit(OLD.project_id, 'member.removed', jsonb_build_object('user_id', OLD.user_id));\n    ELSE\n        IF TG_OP = 'INSERT' THEN\n            SELECT id INTO cid FROM project_chats WHERE project_id = NEW.project_id FOR UPDATE;\n            IF cid IS NOT NULL THEN\n                SELECT coalesce(max(seq), 0) INTO boundary FROM chat_messages WHERE chat_id = cid;\n                INSERT INTO chat_read_states(chat_id, user_id, last_read_seq)\n                    VALUES (cid, NEW.user_id, boundary)\n                    ON CONFLICT (chat_id, user_id) DO UPDATE SET last_read_seq = excluded.last_read_seq;\n            END IF;\n        END IF;\n        PERFORM chat_emit(NEW.project_id, 'member.changed', jsonb_build_object('user_id', NEW.user_id));\n    END IF;\n    RETURN NULL;\nEND;\n$$ LANGUAGE plpgsql;\n"
    )
    op.execute(
        "\nCREATE OR REPLACE FUNCTION chat_entity_changed() RETURNS trigger AS $$\nDECLARE item jsonb;\nBEGIN\n    IF TG_OP = 'DELETE' THEN item := to_jsonb(OLD); ELSE item := to_jsonb(NEW); END IF;\n    PERFORM chat_emit((item->>'project_id')::integer, 'entity.updated',\n        jsonb_build_object('entity_type', TG_ARGV[0], 'entity_id', (item->>'id')::integer));\n    RETURN NULL;\nEND;\n$$ LANGUAGE plpgsql;\n"
    )
    op.execute(
        "\nCREATE OR REPLACE FUNCTION chat_user_changed() RETURNS trigger AS $$\nDECLARE pid integer;\nBEGIN\n    FOR pid IN SELECT project_id FROM project_members WHERE user_id = NEW.id ORDER BY project_id LOOP\n        PERFORM chat_emit(pid, CASE WHEN NEW.is_active THEN 'member.changed' ELSE 'member.removed' END,\n            jsonb_build_object('user_id', NEW.id));\n    END LOOP;\n    RETURN NULL;\nEND;\n$$ LANGUAGE plpgsql;\n"
    )
    op.execute(
        "CREATE OR REPLACE TRIGGER chat_project_key AFTER UPDATE OF key ON projects FOR EACH ROW EXECUTE FUNCTION chat_entities_invalidated()"
    )
    op.execute(
        "CREATE OR REPLACE TRIGGER chat_stage AFTER UPDATE OF name ON project_stages FOR EACH ROW EXECUTE FUNCTION chat_entities_invalidated()"
    )
    op.execute(
        "CREATE OR REPLACE TRIGGER chat_new_project AFTER INSERT ON projects FOR EACH ROW EXECUTE FUNCTION chat_project_created()"
    )
    op.execute(
        "CREATE OR REPLACE TRIGGER chat_membership AFTER INSERT OR UPDATE OR DELETE ON project_members FOR EACH ROW EXECUTE FUNCTION chat_membership_changed()"
    )
    op.execute(
        "CREATE OR REPLACE TRIGGER chat_user AFTER UPDATE OF is_active, first_name, last_name, username ON users FOR EACH ROW EXECUTE FUNCTION chat_user_changed()"
    )
    op.execute(
        "CREATE OR REPLACE TRIGGER chat_entity AFTER INSERT OR UPDATE OR DELETE ON tasks FOR EACH ROW EXECUTE FUNCTION chat_entity_changed('TASK')"
    )
    op.execute(
        "CREATE OR REPLACE TRIGGER chat_entity AFTER INSERT OR UPDATE OR DELETE ON documents FOR EACH ROW EXECUTE FUNCTION chat_entity_changed('DOCUMENT')"
    )
    op.execute(
        "CREATE OR REPLACE TRIGGER chat_entity AFTER INSERT OR UPDATE OR DELETE ON project_risks FOR EACH ROW EXECUTE FUNCTION chat_entity_changed('RISK')"
    )
    op.execute(
        "CREATE OR REPLACE TRIGGER chat_entity AFTER INSERT OR UPDATE OR DELETE ON project_milestones FOR EACH ROW EXECUTE FUNCTION chat_entity_changed('MILESTONE')"
    )
    op.execute(
        "CREATE OR REPLACE TRIGGER chat_entity AFTER INSERT OR UPDATE OR DELETE ON wbs_nodes FOR EACH ROW EXECUTE FUNCTION chat_entity_changed('WBS_NODE')"
    )


def downgrade() -> None:
    """Удаляет только контур чата; проекты и личные диалоги сохраняются."""
    op.execute("DROP TRIGGER IF EXISTS chat_entity ON wbs_nodes")
    op.execute("DROP TRIGGER IF EXISTS chat_entity ON project_milestones")
    op.execute("DROP TRIGGER IF EXISTS chat_entity ON project_risks")
    op.execute("DROP TRIGGER IF EXISTS chat_entity ON documents")
    op.execute("DROP TRIGGER IF EXISTS chat_entity ON tasks")
    op.execute("DROP TRIGGER IF EXISTS chat_user ON users")
    op.execute("DROP TRIGGER IF EXISTS chat_membership ON project_members")
    op.execute("DROP TRIGGER IF EXISTS chat_new_project ON projects")
    op.execute("DROP TRIGGER IF EXISTS chat_stage ON project_stages")
    op.execute("DROP TRIGGER IF EXISTS chat_project_key ON projects")
    op.execute("DROP FUNCTION IF EXISTS chat_entities_invalidated()")
    op.execute("DROP FUNCTION IF EXISTS chat_user_changed()")
    op.execute("DROP FUNCTION IF EXISTS chat_entity_changed()")
    op.execute("DROP FUNCTION IF EXISTS chat_membership_changed()")
    op.execute("DROP FUNCTION IF EXISTS chat_project_created()")
    op.execute("DROP FUNCTION IF EXISTS chat_emit(integer, text, jsonb)")
    op.execute("DROP TABLE chat_reactions")
    op.execute("DROP TABLE chat_message_mentions")
    op.execute("DROP TABLE chat_message_entities")
    op.execute("DROP TABLE chat_attachments")
    op.execute("DROP TABLE chat_read_states")
    op.execute("DROP TABLE chat_messages")
    op.execute("DROP TABLE chat_events")
    op.execute("DROP TABLE project_chats")
