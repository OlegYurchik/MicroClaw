# План: Добавление поддержки вебхуков (Webhooks)

## Цель

Реализовать систему вебхуков в MicroClaw, работающую по аналогии с крон-задачами:
- Базовый класс `BaseWebhook`, от которого наследуются конкретные реализации.
- Возможность задавать вебхуки на уровне приложения (глобальные) и на уровне пользователя.
- Каждый вебхук идентифицируется уникальным UUID.
- При получении запроса на `POST /webhooks/{webhook_id}/call` вызывается соответствующая логика обработки.

## Разделение ответственности

1. **Управление вебхуками** — REST API в `microclaw/api/rest/webhooks/`. Авторизованные пользователи и админы создают, просматривают и удаляют вебхуки. Работает внутри `RESTAPIService`.
2. **Вызов вебхуков** — публичный POST-эндпоинт `/webhooks/{webhook_id}/call` в том же REST API (`microclaw/api/rest/webhooks/router.py`). **Не требует авторизации**. Хендлер напрямую работает с `DependencyResolver` и `users_storage`.

---

## Этап 1. DTO (`microclaw/dto.py`)

Добавить модель `Webhook`:

```python
class Webhook(BaseModel):
    id: uuid.UUID
    path: str           # Путь к классу обработчика, например microclaw.webhooks.tasks.gitlab.GitLabWebhook
    enabled: bool = True
    args: dict[str, Any] = Field(default_factory=dict)
```

---

## Этап 2. Базовый класс (`microclaw/webhooks/base.py`)

`BaseWebhook` — **не** наследуется от `facet.AsyncioServiceMixin`, не имеет `do_before`, не хранит реестр и не имеет `register`/`unregister`.

```python
ArgumentsType = TypeVar("ArgumentsType")
PayloadType = TypeVar("PayloadType", bound=BaseModel)

class BaseWebhook(Generic[ArgumentsType, PayloadType]):
    def __init__(
        self,
        arguments: ArgumentsType,
        resolver: "DependencyResolver",
    ):
        self._arguments = arguments
        self._resolver = resolver

    async def __call__(self, data: dict[str, Any]) -> None:
        payload_class = self.get_payload_class()
        payload = payload_class(**data)
        await self.handle(payload=payload)

    @classmethod
    def get_payload_class(cls) -> type[PayloadType]:
        <implement it>

    async def handle(self, payload: PayloadType) -> None:
        raise NotImplementedError
```

---

## Этап 3. Settings и Factory

### 3.1. Settings (`microclaw/webhooks/settings.py`)

```python
class WebhookSettings(BaseModel):
    path: str
    enabled: bool = True
    args: dict[str, Any] = Field(default_factory=dict)
```

### 3.2. Factory (`microclaw/webhooks/fabric.py`)

```python
async def get_webhook(
    settings: WebhookSettings,
    resolver: "DependencyResolver",
) -> BaseWebhook:
    module_path, class_name = settings.path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    webhook_class = getattr(module, class_name)
    if not issubclass(webhook_class, BaseWebhook):
        raise ValueError(f"Class {class_name} is not a subclass of BaseWebhook")
    return webhook_class(arguments=settings.args, resolver=resolver)
```

### 3.3. Package init (`microclaw/webhooks/__init__.py`)

Экспорт `BaseWebhook`, `WebhookSettings`, `get_webhook`.

---

## Этап 4. Интеграция в сервис и резолвер

### 4.1. MicroclawSettings (`microclaw/settings.py`)

Добавить поле:

```python
webhooks: dict[str, WebhookSettings] = Field(default_factory=dict)
```

### 4.2. DependencyResolver (`microclaw/resolver.py`)

Добавить `_global_webhooks: dict[uuid.UUID, BaseWebhook] | None = None`.

Метод `resolve_global_webhooks()`:

```python
async def resolve_global_webhooks(self) -> dict[uuid.UUID, BaseWebhook]:
    if self._global_webhooks is None:
        self._global_webhooks = {}
        for name, webhook_settings in self._settings.webhooks.items():
            if not webhook_settings.enabled:
                continue
            webhook_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"microclaw.global.{name}")
            webhook = Webhook(
                id=webhook_id,
                path=webhook_settings.path,
                enabled=webhook_settings.enabled,
                args=webhook_settings.args,
            )
            self._global_webhooks[webhook_id] = await get_webhook(
                webhook=webhook, resolver=self
            )
    return self._global_webhooks
```

> **Важно:** `uuid.uuid5` — детерминированная хеш-функция. Для одного и того же `namespace` и `name` всегда возвращается один и тот же UUID. Это позволяет стабильно идентифицировать глобальные вебхуки по имени из конфигурации.

### 4.3. MicroclawService (`microclaw/service.py`)

```python
self._global_webhooks: dict[uuid.UUID, BaseWebhook] | None = None

async def run(self) -> None:
    self._channels = await self._resolver.resolve_channels()
    self._crons = await self._resolver.resolve_crons()
    self._global_webhooks = await self._resolver.resolve_global_webhooks()
    await super().run()
```

---

## Этап 5. Хранилища пользователей

### 5.1. Filters (`microclaw/users_storages/filters.py`)

Добавить:

```python
class WebhookFilter(BaseFilter):
    id: set[uuid.UUID]
    user_id: set[uuid.UUID]
    enabled: bool
```

### 5.2. Interface (`microclaw/users_storages/interfaces.py`)

Добавить `WebhooksMixin`, используя `Webhook` из `microclaw/dto.py`:

```python
class WebhooksMixin:
    async def get_webhooks(
        self,
        filter: WebhookFilter | None = None,
    ) -> AsyncGenerator[Webhook]:
        raise NotImplementedError

    async def create_webhook(self, user_id: uuid.UUID, webhook: Webhook) -> None:
        raise NotImplementedError

    async def remove_webhook(self, webhook_id: uuid.UUID) -> None:
        raise NotImplementedError
```

### 5.3. MemoryUsersStorage

- `self._user_webhooks: dict[uuid.UUID, list[Webhook]] = defaultdict(list)`
- Реализовать `get_webhooks(filter)`, `create_webhook`, `remove_webhook`.
- `get_webhooks` фильтрует по `id`, `user_id`, `enabled`.
- В `delete_user` — очистка списка вебхуков.

### 5.4. FilesystemUsersStorage

- **`dto.py`**: добавить `webhooks: list[Webhook]` в `UserData`.
- **`storage.py`**: реализовать CRUD, аналогично `crons`.

### 5.5. DatabaseUsersStorage

- **`tables.py`**: добавить `WebhookTable` (аналог `CronTable`).
  ```python
  class WebhookTable(BaseTable, table=True):
      __tablename__ = "user_webhooks"
      id: uuid.UUID = Field(primary_key=True)
      user_id: uuid.UUID = Field(foreign_key="users.id")
      path: str
      enabled: bool
      args: dict | None = Field(sa_column=Column(JSON))
  ```
- **`repositories.py`**: добавить `WebhooksRepository`.
- **`storage.py`**: реализовать `WebhooksMixin` через репозиторий.

---

## Этап 6. REST API

### 6.1. Router (`microclaw/api/rest/webhooks/router.py`)

```python
def get_router() -> fastapi.APIRouter:
    router = fastapi.APIRouter()

    # Управление (с авторизацией)
    router.get("", endpoint=handlers.list_webhooks)
    router.post("", endpoint=handlers.create_webhook)
    router.get("/{webhook_id}", endpoint=handlers.get_webhook)
    router.delete("/{webhook_id}", endpoint=handlers.delete_webhook)

    # Вызов (без авторизации)
    router.post("/{webhook_id}/call", endpoint=handlers.call_webhook)

    return router
```

### 6.2. Handlers (`microclaw/api/rest/webhooks/handlers.py`)

- `list_webhooks` — фильтрация по `user_id` (admin видит все, user — только свои). Получает список через `users_storage.get_webhooks(filter=WebhookFilter(user_id=...))`.
- `get_webhook` — получение одного вебхука по `webhook_id`. Проверка прав доступа (admin или владелец).
- `create_webhook` — генерация UUID, сохранение в хранилище.
- `delete_webhook` — удаление из хранилища.
- `call_webhook(webhook_id, request)` — хендлер сам реализует логику поиска вебхука: сначала проверяет глобальные вебхуки через `resolver.resolve_global_webhooks()`, затем ищет в `users_storage` через `get_webhooks(filter=WebhookFilter(id=webhook_id))`. Если не найден или не `enabled` — `404`. Валидирует payload через `get_payload_class()` и вызывает `handle()`.

```python
async def call_webhook(
    webhook_id: uuid.UUID,
    request: fastapi.Request,
    resolver: DependencyResolver = fastapi.Depends(resolver_dependency),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
):
    # Поиск в глобальных
    global_webhooks = await resolver.resolve_global_webhooks()
    webhook_instance = global_webhooks.get(webhook_id)

    # Поиск в пользовательских
    if webhook_instance is None:
        async for webhook in users_storage.get_webhooks(
            filter=WebhookFilter(id=webhook_id),
        ):
            if not webhook.enabled:
                raise HTTPNotFound()
            webhook_instance = await get_webhook(webhook=webhook, resolver=resolver)
            break

    if webhook_instance is None:
        raise HTTPNotFound()

    payload = await request.json()
    payload_model = webhook_instance.get_payload_class()
    validated = payload_model.model_validate(payload)
    result = await webhook_instance.handle(validated)
    return {"status": "ok", "result": result}
```

### 6.3. Schemas (`microclaw/api/rest/webhooks/schemas.py`)

- `WebhookCreateRequest` (`path`, `enabled`, `args`, `user_id` опционально).
- `WebhookResponse` (`id`, `path`, `enabled`, `args`).
- `WebhookListResponse`.

### 6.4. Подключение (`microclaw/api/rest/service.py`)

```python
app.include_router(webhooks.get_router(), prefix="/webhooks")
```

---

## Этап 7. Пример реализации обработчика

### 7.1. GitLabWebhook (`microclaw/webhooks/tasks/gitlab.py`)

```python
class GitLabWebhookPayload(BaseModel):
    object_kind: str | None = None
    project: dict[str, Any] | None = None
    object_attributes: dict[str, Any] | None = None
    ...

class GitLabWebhookSettings(BaseModel):
    channel: str | None = None
    channel_internal_id: str | None = None
    agent: str | AgentSettings | None = None
    create_new_session: bool = True

class GitLabWebhook(BaseWebhook[GitLabWebhookSettings, GitLabWebhookPayload]):
    async def handle(self, payload: GitLabWebhookPayload) -> str:
        # Формирует AgentMessage на основе события GitLab и вызывает agent.ask() / channel.start_conversation()
        ...
```

### 7.2. Пакет tasks (`microclaw/webhooks/tasks/__init__.py`)

---

## Этап 8. Тесты

### 8.1. Базовые тесты

- `tests/webhooks/test_base.py` — создание обработчика, валидация payload, вызов `handle()`.
- `tests/webhooks/test_fabric.py` — `get_webhook()` корректно инстанциирует класс.

### 8.2. API тесты

- `tests/api/rest/test_webhooks.py`:
  - Создание, список, получение по id, удаление через авторизованные запросы.
  - Права доступа (admin vs user).
  - Публичный вызов `POST /webhooks/{webhook_id}/call` с корректным/некорректным payload.
  - 404 для неизвестного webhook_id.

### 8.3. Хранилища

- Проверить, что `MemoryUsersStorage`, `FilesystemUsersStorage`, `DatabaseUsersStorage` корректно сохраняют и возвращают `Webhook`, включая фильтрацию через `WebhookFilter`.

---

## Этап 9. CLI (опционально)

Если нужен отдельный режим запуска только вебхуков:

- `microclaw/webhooks/cli.py` — `get_cli()` с командой `run`.
- Регистрация в `microclaw/cli.py`.

---

## Список новых и изменённых файлов

### Новые файлы

| Файл | Назначение |
|------|------------|
| `microclaw/webhooks/__init__.py` | Экспорт `BaseWebhook`, `WebhookSettings`, `get_webhook` |
| `microclaw/webhooks/base.py` | `BaseWebhook[ArgumentsType, PayloadType]` |
| `microclaw/webhooks/settings.py` | `WebhookSettings` |
| `microclaw/webhooks/fabric.py` | `get_webhook()` |
| `microclaw/webhooks/tasks/__init__.py` | Пакет примеров |
| `microclaw/webhooks/tasks/gitlab.py` | `GitLabWebhook` |
| `microclaw/api/rest/webhooks/__init__.py` | Экспорт роутера |
| `microclaw/api/rest/webhooks/router.py` | CRUD + `/{webhook_id}/call` |
| `microclaw/api/rest/webhooks/handlers.py` | CRUD + `call_webhook` хендлеры |
| `microclaw/api/rest/webhooks/schemas.py` | Pydantic-схемы |
| `tests/webhooks/test_base.py` | Юнит-тесты базового класса |
| `tests/webhooks/test_fabric.py` | Юнит-тесты фабрики |
| `tests/api/rest/test_webhooks.py` | Интеграционные API-тесты |

### Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `microclaw/dto.py` | Добавить `Webhook` |
| `microclaw/settings.py` | `webhooks: dict[str, WebhookSettings]` |
| `microclaw/resolver.py` | `resolve_global_webhooks()` |
| `microclaw/service.py` | Инициализация `_global_webhooks` в `run()` |
| `microclaw/users_storages/filters.py` | Добавить `WebhookFilter` |
| `microclaw/users_storages/interfaces.py` | `WebhooksMixin` с `get_webhooks(filter)` |
| `microclaw/users_storages/memory/storage.py` | Реализация `WebhooksMixin` |
| `microclaw/users_storages/filesystem/dto.py` | `webhooks` в `UserData` |
| `microclaw/users_storages/filesystem/storage.py` | Реализация `WebhooksMixin` |
| `microclaw/users_storages/database/tables.py` | `WebhookTable` |
| `microclaw/users_storages/database/repositories.py` | `WebhooksRepository` |
| `microclaw/users_storages/database/storage.py` | Реализация `WebhooksMixin` |
| `microclaw/api/rest/service.py` | Подключить `webhooks` роутер |
| `AGENTS.md` | Обновить документацию |

---

## Архитектурные замечания

1. **Нет реестра в `BaseWebhook`** — глобальные вебхуки хранятся в `DependencyResolver._global_webhooks`. Пользовательские достаются из `users_storage` по UUID при вызове.
2. **`BaseWebhook` простой** — без `AsyncioServiceMixin`, `do_before`, `register`/`unregister`. Логика только в `handle()`.
3. **UUID как секрет** — внешний сервис знает только UUID. URL вида `https://host/webhooks/{uuid}/call`.
4. **PayloadType** — валидация входящего JSON через Pydantic-модель конкретного обработчика.
5. **Нет отдельного сервиса** — вызов вебхуков прямо в REST API хендлере. Хендлер сам ищет вебхук в глобальных (через `resolver.resolve_global_webhooks()`) и пользовательских (через `users_storage.get_webhooks(filter=...)`) хранилищах.
6. **`uuid.uuid5` детерминирован** — для одного `namespace` и `name` всегда один и тот же UUID, что позволяет стабильно идентифицировать глобальные вебхуки по имени из конфига.
