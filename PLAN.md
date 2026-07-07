# План: Durable Execution через `interrupt()` в тулзах

## Принцип: не использовать данные из checkpointer

Состояние диалога, подтверждений и всего остального хранится **только в syncer и sessions_storage**. Checkpointer нужен только для того, чтобы LangGraph мог сохранить checkpoint и остановиться при `interrupt()`. Для восстановления мы не читаем состояние графа, а используем `Command(resume=...)` с известным `session_id`.

## Сделано

- `SyncerCheckpointer` — адаптер поверх `Syncer` (pickle + base64, TTL, `adelete_thread`).
- `DecisionEnum` (dto.py) — `APPROVE` / `REJECT`.
- `_disable_parallel_tool_calls` — middleware `@wrap_model_call` для последовательных вызовов тулз.
- Базовая обработка `__interrupt__` в `Agent.ask()` — yield `AgentMessage(role="request_confirmation", text=json.dumps([...]))`.
- `Agent.handle_confirmation()` — восстановление графа через `Command(resume=decision.value)`.
- `Agent._create_agent()` + `Agent._process_events()` — структура методов.
- `thread_id = session_id` — `ask()` использует `session_id`, `handle_confirmation()` тоже.
- Очистка checkpoint перед `ask()` — `await self._checkpointer.adelete_thread(str(session_id))`.
- `InterruptEntry` (dto.py) — `{id, value, description, session_id}`.
- `session_id` проставляется в `InterruptEntry` при формировании entries в `_process_events`.

## Осталось

### Этап 1 — Рефакторинг каналов и ConfirmationMixin

**Цель:** перейти от блокирующего `wait_for_confirmation()` к асинхронной обработке interrupts через `agent.handle_confirmation()`.

#### 1.1 ConfirmationMixin — рефакторинг методов

- **`wait_for_confirmation()`** — **удалить**. Блокирующий polling ломает durable execution (нода висит и не сохраняет checkpoint).
- **`request_confirmation()`** — пометить **deprecated**. Тулзы больше не вызывают его напрямую; канал сам реагирует на `role="request_confirmation"` из потока.
- **`resolve_confirmation()`** — адаптировать: вместо `syncer.set("confirm:{session_id}:{id}", approved)` вызывать `agent.handle_confirmation(session_id, decision)`.
- **`reject_all_pending_confirmations(session_id)`** — изменить логику:
  - Загрузить из syncer все записи по паттерну `confirmation:{session_id}:*`.
  - Для каждой со `status="pending"` вызвать `agent.handle_confirmation(session_id, DecisionEnum.REJECT)`.
  - Обновить статус на `"rejected"`.

#### 1.2 Обработка `role="request_confirmation"` в потоке

При получении `AgentMessage(role="request_confirmation", text="[...]")` из `agent.ask()`:

- `AgentMessageSaver` — **не сохранять** в историю чата (чтобы не засорять контекст LLM).
- Парсим `text` как JSON → `list[InterruptEntry]`.
- Для каждого entry отправляем отдельное сообщение с кнопками:
  - **Telegram / VK** — inline-кнопки (Подтвердить / Отклонить) + текст `description`.
  - **CLI** — существующий TUI-диалог подтверждения.
- Сохраняем в syncer: `syncer.set(f"confirmation:{session_id}:{confirmation_id}", {...})`.
  - Структура: `{session_id, interrupt_id, status="pending", created_at}`.
  - `session_id` — ключевое поле, используется при вызове `agent.handle_confirmation()`.

#### 1.3 Callback / ввод пользователя

- **Telegram / VK** — callback с `confirmation_id` и `approved`.
- **CLI** — реакция на TUI-диалог.
- По `confirmation_id` достаём из syncer `session_id`.
- Устанавливаем `request_id` через `set_current_request_id()` (как при `ask()`).
- Вызываем `agent.handle_confirmation(session_id, decision=DecisionEnum.APPROVE | REJECT)`.
- Результат стримим в `AgentMessagePrinter`.
- Обновляем статус записи на `"resolved"` или удаляем ключ.

#### 1.4 Восстановление при старте канала `restore_pending_confirmations()`

- Загружаем из syncer все записи по паттерну `confirmation:{session_id}:*`.
- Для каждой со `status="pending"` перерисовываем кнопки / TUI-диалог.
- Если запись висит слишком долго — можно отклонить автоматически (опционально).

#### 1.5 Принтеры

- VK- и CLI-принтеры сейчас фильтруют только `role="assistant"` — добавить обработку `request_confirmation` (отображать запрос пользователю).

### Этап 2 — Рефакторинг тулз

**Цель:** заменить `BaseToolKit.request_confirmation()` на `langgraph.types.interrupt()`.

**Правила:**
- Side-effect только **после** `interrupt()` при `decision == "approve"`.
- Код **до** `interrupt()` — readonly / идempotentный (нода replay-ится).
- **Не ловить** `GraphInterrupt` в `try/except`.

**Шаблон:**
```python
from langgraph.types import interrupt

@tool
async def delete_messages(self, uids: list[str], folder: str = "") -> str:
    # readonly / идempotentный код до interrupt
    headers = await self._load_headers(uids, folder)
    text = f"Удалить письма?\n" + "\n".join(f"• {h}" for h in headers)

    decision = interrupt({"description": text, "action": "delete_messages"})

    if decision == "approve":
        for uid in uids:
            await client.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
        return "Удалено"
    return "Отменено"
```

**Тулзы для рефакторинга:**
- `EmailToolKit.delete_messages`, `.send_email`
- `WebDAVToolKit` (delete/move с запросом)
- `FilesystemToolKit` (операции с запросом)
- `TaskToolKit`
- `CronToolKit`
- `CommandToolKit`
- `CalDAVToolKit`
- `CardDAVToolKit`
- `AudioTagsToolKit`
- Любая тулза с `PermissionModeEnum.REQUEST`

**Затем:**
- Удалить `PermissionModeEnum.REQUEST` из runtime-логики (`ALLOW`/`DENY` можно оставить).
- Пометить `BaseToolKit.request_confirmation()` как deprecated.

### Этап 3 — Тесты

- happy path: interrupt → approve → side-effect выполнен.
- reject recovery: interrupt → reject → side-effect НЕ выполнен.
- процесс падает после interrupt → рестарт → `restore_pending_confirmations()` → кнопки перерисованы → handle_confirmation продолжает.
- parallel interrupts: несколько тулз одновременно → один `__interrupt__` с массивом entries.
- новый ask() после handle_confirmation(): old checkpoint удалён, граф стартует с чистого листа.

### Этап 4 — Рефакторинг логгирования

Вся дополнительная информация типа `request_id`, `session_id` должна быть в `extra`:

```python
# Было
logger.info("[%s] Agent ask started messages_count=%s", request_id, len(messages))

# Стало
logger.info("Agent ask started", extra={"request_id": request_id, "session_id": session_id, "messages_count": len(messages)})
```

- Переписать логи в `Agent` (`ask`, `handle_confirmation`, `_process_events`).
- При необходимости добавить `loguru` bind/context для прокидывания `request_id` / `session_id` на весь вызов.

## Критичные детали

- `thread_id = session_id`.
- Перед каждым новым `ask()` — удалять старый checkpoint через `checkpointer.adelete_thread()`.
- `handle_confirmation()` — checkpoint НЕ очищать, он нужен для `Command(resume=...)`.
- **Источник truth о pending confirmations — syncer**, не checkpointer. Мы не читаем состояние графа через `aget_state()`.
- `wait_for_confirmation()` — блокирующий polling, **должен быть удалён**, иначе durable execution не работает.
- `reject_all_pending_confirmations()` — через syncer + `agent.handle_confirmation(REJECT)`, не через checkpointer.
- TTL на `confirmation:*` ключи в syncer (например, 24 ч).
