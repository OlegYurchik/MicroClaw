# План: Durable Execution через `interrupt()` в тулзах

## Принцип: не использовать данные из checkpointer

Состояние диалога, подтверждений и всего остального хранится **только в syncer и sessions_storage**. Checkpointer нужен только для того, чтобы LangGraph мог сохранить checkpoint и остановиться при `interrupt()`. Для восстановления мы не читаем состояние графа, а используем `Command(resume=...)` с известным `session_id`.

## Сделано

- `SyncerCheckpointer` — адаптер поверх `Syncer` (pickle + base64, TTL, `adelete_thread`).
- `DecisionEnum` (dto.py) — `APPROVE` / `REJECT`.
- `_disable_parallel_tool_calls` — middleware `@wrap_model_call` для последовательных вызовов тулз.
- `Agent.ask()` — `thread_id = session_id`, очистка checkpoint перед запуском, yield `AgentMessage(role="request_confirmation", text=json.dumps([...]))`.
- `Agent.handle_confirmation()` — восстановление графа через `Command(resume=decision.value)`.
- `Agent._create_agent()` + `Agent._process_events()` — структура методов.
- `InterruptEntry` (dto.py) — `{id, value, description, session_id}`.
- `session_id` проставляется в `InterruptEntry` при формировании entries в `_process_events`.

### Каналы (Этап 1):

- **ConfirmationMixin** (`base.py`):
  - `wait_for_confirmation()` — **удалён**, бросает `NotImplementedError`.
  - `request_confirmation()` / `resolve_confirmation()` — помечены `DeprecationWarning`.
  - `reject_all_pending_confirmations()` — новая логика через syncer + `agent.handle_confirmation(REJECT)`.
- **AgentMessageSaver** (`utils.py`) — skip `request_confirmation`, не сохраняет в историю чата.
- **Telegram** (`base.py`):
  - `_generate_and_send_answer` — обработка `request_confirmation` в потоке, отправка inline-кнопок, сохранение в syncer.
  - `handle_confirmation_callback` — загрузка из syncer, вызов `agent.handle_confirmation()`, стриминг результата в printer/saver.
- **VK** (`base.py`) — аналогично Telegram.
- **CLI** (`channel.py`, `messages.py`):
  - Обработка `request_confirmation` в `_generate_and_send_answer`.
  - `_handle_confirmation_callback` — вызов `agent.handle_confirmation()` с printer/saver.
  - `messages.py` — callback через `_handle_confirmation_callback` вместо `resolve_confirmation`.

## Осталось

### Этап 1 — Восстановление при старте канала `restore_pending_confirmations()`

- Загружаем из syncer все записи по паттерну `confirmation:{session_id}:*`.
- Для каждой со `status="pending"` перерисовываем кнопки / TUI-диалог.
- Требуется mapping `session_id → chat_id/peer_id` для повторной отправки UI.

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
