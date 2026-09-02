# Формат eval-набора retrieval

Набор хранится в UTF-8 JSON с полем `examples`. Для `semantic` и `hybrid`
после утверждения владельцем проекта обязательны `gold_source_ids`; runner
считает по ним Recall@k и MRR. Для `structured` вместо retrieval-метрик задаются
`expected_facts` и `expected_tool` и проверяются отдельным сценарием.

```json
{
  "version": 1,
  "examples": [
    {
      "id": "semantic-001",
      "split": "dev",
      "kind": "semantic",
      "approval_status": "APPROVED",
      "question": "Что решили по авторизации?",
      "gold_source_ids": ["document:4", "comment:18"]
    },
    {
      "id": "structured-001",
      "split": "test",
      "kind": "structured",
      "approval_status": "APPROVED",
      "question": "Сколько задач просрочено?",
      "expected_tool": "get_project_statistics",
      "expected_facts": {"overdue": 3}
    }
  ]
}
```

Допустимые `split`: `dev`, `test`. Статус `APPROVED` назначает только владелец
проекта или доменный эксперт. `TEST_FIXTURE` разрешён исключительно синтетическим
данным unit-тестов runner-а. Файл `candidate_questions.json` не является ground
truth и намеренно не запускается runner-ом.

Предсказания передаются отдельным JSON:

```json
{"predictions": [{"id": "semantic-001", "source_ids": ["comment:18", "task:7"]}]}
```

Запуск:

```bash
python -m evals.knowledge_retrieval.runner --dataset approved.json --predictions run.json --k 1 5 10
```
