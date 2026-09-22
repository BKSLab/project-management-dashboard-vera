"""Ограниченная рабочая память агента без дополнительных вызовов модели."""

import json
from copy import deepcopy


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def estimate_tokens(text: str) -> int:
    """Локальная консервативная оценка, не точный токенизатор провайдера.

    Считаем UTF-8 байты / 3, чтобы кириллица не получала английский бюджет
    «четыре символа на токен». Фактическое usage учитывается отдельно клиентом.
    """
    return (len(text.encode("utf-8")) + 2) // 3


def clip_text(text: str, tokens: int) -> str:
    """Обрезает по UTF-8 границе, не создавая повреждённого Unicode."""
    return text.encode("utf-8")[: max(0, tokens) * 3].decode("utf-8", errors="ignore")


def result_key(request: dict, result: dict) -> str:
    """Порядок аргументов и явное offset=0 не создают вторую копию страницы."""
    action = result.get("action")
    if isinstance(action, dict) and action.get("id") is not None:
        return f"action:{action['id']}"
    name = request["name"]
    if name in {"read_source", "get_document"} and result.get("source_id"):
        page = result.get("document", result)
        offset = page.get("offset", request.get("arguments", {}).get("offset", 0))
        return encode([name, result["source_id"], offset])
    return json.dumps(request, ensure_ascii=False, sort_keys=True, default=str)


def compact_action(action: dict) -> dict:
    """Квитанция сохраняет факт записи; большие параметры остаются в БД и UI."""
    result = {
        key: action[key] for key in ("id", "tool_name", "title", "status", "error") if key in action
    }
    result["result"] = compact_fields(action.get("result", {}))
    if action.get("status") == "pending":
        result["confirmation"] = "Параметры и решение доступны участнику в карточке действия."
    return result


def compact_fields(value):
    """Убирает тела из квитанций, оставляя ID, результаты и явную отметку сокращения."""
    if isinstance(value, dict):
        result = {}
        omitted = []
        for key, item in value.items():
            if key in {
                "content_md",
                "body_md",
                "description_md",
                "extracted_text",
                "arguments",
                "preview",
                "checklist",
            }:
                omitted.append(key)
            else:
                result[key] = compact_fields(item)
        if omitted:
            result["omitted_fields"] = omitted
        return result
    if isinstance(value, list):
        items = [compact_fields(item) for item in value[:20]]
        return items if len(value) <= 20 else {"items": items, "omitted_count": len(value) - 20}
    if isinstance(value, str) and len(value) > 800:
        return value[:800] + "… [сокращено; подробности доступны инструментом]"
    return value


class AgentContextBudget:
    def __init__(self, *, system_prompt: str, max_tokens: int, history_tokens: int):
        self.system_tokens = estimate_tokens(system_prompt) + 32
        self.max_tokens = max_tokens
        self.history_tokens = history_tokens

    def tokens(self, content: dict) -> int:
        return self.system_tokens + estimate_tokens(encode(content))

    def prepare(self, content: dict) -> None:
        """Ограничивает историю по объёму, а не только по числу сообщений."""
        history = content.get("dialog_history", [])
        kept = []
        remaining = self.history_tokens
        for message in reversed(history):
            cost = estimate_tokens(encode(message))
            if cost > remaining:
                if not kept and remaining > 80:
                    # Ссылки на показанные карточки находятся в конце реплики.
                    # Сохраняем оба края, чтобы не потерять ID для уточняющего вопроса.
                    edge_bytes = max(0, (remaining - 40) * 3 // 2)
                    raw = message["content"].encode("utf-8")
                    message = {
                        **message,
                        "content": raw[:edge_bytes].decode("utf-8", errors="ignore")
                        + "… [середина реплики сокращена] …"
                        + raw[-edge_bytes:].decode("utf-8", errors="ignore"),
                    }
                    kept.append(message)
                break
            kept.append(message)
            remaining -= cost
        content["dialog_history"] = list(reversed(kept))
        if len(kept) < len(history):
            content["dialog_history_omitted"] = len(history) - len(kept)
        memory = content.get("dialog_memory", "")
        if estimate_tokens(memory) > self.history_tokens // 2:
            content["dialog_memory"] = (
                clip_text(memory, self.history_tokens // 2) + "… [память сокращена]"
            )
        actions = content.get("previous_actions", [])
        content["previous_actions"] = [compact_action(item) for item in actions[-20:]]
        if len(actions) > 20:
            content["previous_actions_omitted"] = len(actions) - 20
        content["context_policy"] = (
            "Описания нужны для отбора. Точные условия проверяй read_source/get_document. "
            "omitted/compacted означают сокращение, а не отсутствие данных. "
            "Читай только нужные объекты и страницы; используй next_offset."
        )

    @staticmethod
    def add_result(content: dict, *, request: dict, result: dict) -> None:
        """Повтор той же страницы заменяет её; разные страницы сохраняются отдельно."""
        result = deepcopy(result)
        if isinstance(result.get("action"), dict):
            result["action"] = compact_action(result["action"])
            # Тексты поручения уже есть в вопросе и сохранённом журнале действий.
            request = {
                "name": request["name"],
                "arguments": compact_fields(request.get("arguments", {})),
            }
        signature = result_key(request, result)
        entries = content["read_results"]
        entries[:] = [
            item for item in entries if result_key(item["request"], item["result"]) != signature
        ]
        entries.append({"request": request, "result": result})
        # После дочитывания не передаём ещё и стартовую копию того же объекта.
        seen = set()

        def collect(value):
            if isinstance(value, dict):
                source_id = value.get("source_id")
                if isinstance(source_id, str):
                    seen.add(source_id)
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(result)
        content["retrieval_context"] = [
            item
            for item in content.get("retrieval_context", [])
            if item.get("source_id") not in seen
        ]

    def fit(self, content: dict) -> str:
        """Применяется перед КАЖДЫМ раундом, включая накопленные ответы инструментов."""
        while self.tokens(content) > self.max_tokens:
            if self._shrink_lists(content):
                continue
            # Отработанные большие чтения уступают место последнему результату.
            compacted = False
            for entry in content.get("read_results", [])[:-1]:
                result = entry["result"]
                if (
                    "action" not in result
                    and not result.get("context_compacted")
                    and estimate_tokens(encode(result)) > 160
                ):
                    entry["result"] = self._receipt(result)
                    compacted = True
                    break
            if compacted:
                continue
            receipts = [
                entry["result"]["action"]
                for entry in content.get("read_results", [])
                if "action" in entry["result"]
            ]
            receipts += content.get("previous_actions", [])
            for action in receipts:
                if (
                    not action.get("result_compacted")
                    and estimate_tokens(encode(action.get("result", {}))) > 160
                ):
                    references = []

                    def collect_references(value, collected=references):
                        if isinstance(value, dict):
                            if isinstance(value.get("source_id"), str):
                                collected.append(
                                    {
                                        key: value[key]
                                        for key in ("source_id", "source_handle")
                                        if key in value
                                    }
                                )
                            for item in value.values():
                                collect_references(item, collected)
                        elif isinstance(value, list):
                            for item in value:
                                collect_references(item, collected)

                    collect_references(action["result"])
                    action["result"] = {
                        "sources": references[:10],
                        "notice": "Полный результат сохранён в карточке действия.",
                    }
                    action["result_compacted"] = True
                    compacted = True
                    break
            if compacted:
                continue
            actions = content.get("previous_actions", [])
            if len(actions) > 1:
                actions.pop(0)
                content["previous_actions_omitted"] = content.get("previous_actions_omitted", 0) + 1
                continue
            if self._shrink_text(content):
                continue
            # Схемы аргументов не обрезаем: агент может запросить их заново по имени.
            tools = content.get("available_tools", [])
            if any("description" in item for item in tools):
                for item in tools:
                    item.pop("description", None)
                content["tool_descriptions_omitted"] = True
                continue
            reads = content.get("read_results", [])
            disposable = next((entry for entry in reads if "action" not in entry["result"]), None)
            if disposable is not None:
                reads.remove(disposable)
                content["read_results_omitted"] = content.get("read_results_omitted", 0) + 1
                continue
            raise ValueError(
                "Обязательный контекст превышает бюджет. Уточните вопрос или сократите список действий."
            )
        return encode(content)

    @staticmethod
    def _receipt(result: dict) -> dict:
        keys = {
            "source_id",
            "source_handle",
            "title",
            "entity_type",
            "offset",
            "next_offset",
            "total",
            "total_chars",
            "error",
        }
        return {
            **{key: value for key, value in result.items() if key in keys},
            "context_compacted": True,
            "notice": "Текст прежнего чтения убран из контекста; при необходимости повтори нужную страницу.",
        }

    @staticmethod
    def _shrink_lists(content: dict) -> bool:
        candidates = []

        def visit(value, path=()):
            if not isinstance(value, dict):
                return
            for key, item in list(value.items()):
                if key in {
                    "available_tools",
                    "tools",
                    "properties",
                    "arguments",
                    "previous_actions",
                }:
                    continue
                if isinstance(item, list):
                    if key != "read_results" and len(item) > 1:
                        candidates.append((len(encode(item)), value, key, path))
                    for child in item:
                        visit(child, (*path, key))
                elif isinstance(item, dict) and key != "action":
                    visit(item, (*path, key))

        visit(content)
        if not candidates:
            return False
        _, parent, key, _ = max(candidates, key=lambda item: item[0])
        items = parent[key]
        keep = max(1, len(items) // 2)
        parent[key] = items[-keep:] if key == "dialog_history" else items[:keep]
        parent[f"{key}_omitted"] = parent.get(f"{key}_omitted", 0) + len(items) - keep
        if key == "items" and "next_offset" in parent:
            # Старт страницы добавляется источником, не вычисляется по общей длине.
            parent["next_offset"] = parent.get("offset", 0) + keep
        return True

    @staticmethod
    def _shrink_text(content: dict) -> bool:
        candidates = []

        def visit(value):
            if isinstance(value, dict):
                for key, item in list(value.items()):
                    if key in {
                        "question",
                        "current_participant",
                        "available_tools",
                        "tools",
                        "arguments",
                        "action",
                    }:
                        continue
                    if isinstance(item, str) and len(item) > 400:
                        candidates.append((len(item.encode("utf-8")), value, key))
                    elif isinstance(item, (list, dict)):
                        visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        visit(content)
        if not candidates:
            return False
        _, parent, key = max(candidates, key=lambda item: item[0])
        text = parent[key]
        parent[key] = text[: max(200, len(text) // 2)]
        parent[f"{key}_truncated"] = True
        if key in {"text", "content_md"} and "offset" in parent:
            parent["next_offset"] = parent["offset"] + len(parent[key])
        return True
