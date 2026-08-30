import asyncio
import builtins
from collections.abc import AsyncIterator, Iterator, Sequence
import time
from typing import Any

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    RunnableConfig,
)

from microclaw.syncers.interfaces import SyncerInterface


class SyncerCheckpointer(BaseCheckpointSaver[str]):
    def __init__(self, syncer: SyncerInterface, ttl: int | None = None):
        super().__init__()
        self._syncer = syncer
        self._ttl = ttl

    def get_next_version(self, current: str | None, channel: None) -> str:
        if current is None:
            current_v = 0
        else:
            current_v = int(current.split(".")[0])
        next_v = current_v + 1
        next_h = time.time_ns()
        return f"{next_v:032}.{next_h:016}"

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return self._run_sync(self.aput(config, checkpoint, metadata, new_versions))

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        return self._run_sync(self.aput_writes(config, writes, task_id, task_path))

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return self._run_sync(self.aget_tuple(config))

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        return iter(
            self._run_sync(
                self._collect_alist(config, filter=filter, before=before, limit=limit)
            )
        )

    async def _collect_alist(self, config, **kwargs):
        result = []
        async for item in self.alist(config, **kwargs):
            result.append(item)
        return result

    def delete_thread(self, thread_id: str) -> None:
        return self._run_sync(self.adelete_thread(thread_id))

    def delete_for_runs(self, run_ids: Sequence[str]) -> None:
        return self._run_sync(self.adelete_for_runs(run_ids))

    def copy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        return self._run_sync(self.acopy_thread(source_thread_id, target_thread_id))

    def prune(
        self,
        thread_ids: Sequence[str],
        *,
        strategy: str = "keep_latest",
    ) -> None:
        return self._run_sync(self.aprune(thread_ids, strategy=strategy))

    @staticmethod
    def _run_sync(coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        import nest_asyncio

        nest_asyncio.apply()
        return loop.run_until_complete(coro)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        key = self._get_key(thread_id, checkpoint_ns, checkpoint_id)

        data = {
            "checkpoint": checkpoint,
            "metadata": metadata,
            "new_versions": new_versions,
            "parent_config": config["configurable"].get("checkpoint_id"),
        }
        await self._syncer.set(key, self.serde.dumps_typed(data), ttl=self._ttl)
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")
        key = self._get_writes_key(thread_id, checkpoint_ns, checkpoint_id, task_id)
        raw = await self._syncer.get(key)
        if raw is None:
            record: dict[str, Any] = {"task_path": task_path, "writes": list(writes)}
        else:
            record = self.serde.loads_typed(raw)
            record["task_path"] = task_path
            record["writes"].extend(writes)
        await self._syncer.set(key, self.serde.dumps_typed(record), ttl=self._ttl)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        if checkpoint_id is None:
            keys = await self._syncer.scan_keys(
                self._get_thread_prefix(thread_id, checkpoint_ns)
            )
            if not keys:
                return None
            keys.sort()
            key = keys[-1]
            checkpoint_id = key.split(":")[-1]
        else:
            key = self._get_key(thread_id, checkpoint_ns, checkpoint_id)

        raw = await self._syncer.get(key)
        if raw is None:
            return None

        data = self.serde.loads_typed(raw)
        checkpoint = data["checkpoint"]
        metadata = data["metadata"]

        parent_checkpoint_id = data.get("parent_config")
        parent_config = None
        if parent_checkpoint_id:
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_checkpoint_id,
                }
            }

        resolved_config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

        pending_writes = await self._load_pending_writes(
            thread_id, checkpoint_ns, checkpoint_id
        )

        return CheckpointTuple(
            config=resolved_config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        if config is None:
            raise ValueError("config is required for alist")
        if filter is not None:
            raise NotImplementedError("metadata filtering is not supported")

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        keys = await self._syncer.scan_keys(
            self._get_thread_prefix(thread_id, checkpoint_ns)
        )
        keys.sort()

        if before:
            before_id = before["configurable"].get("checkpoint_id")
            if before_id:
                keys = [k for k in keys if k.split(":")[-1] < before_id]

        count = 0
        for key in keys:
            if limit is not None and count >= limit:
                break
            raw = await self._syncer.get(key)
            if raw is None:
                continue
            data = self.serde.loads_typed(raw)
            checkpoint = data["checkpoint"]
            metadata = data["metadata"]

            checkpoint_id = key.split(":")[-1]
            item_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            }

            parent_checkpoint_id = data.get("parent_config")
            parent_config = None
            if parent_checkpoint_id:
                parent_config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_checkpoint_id,
                    }
                }

            pending_writes = await self._load_pending_writes(
                thread_id, checkpoint_ns, checkpoint_id
            )

            yield CheckpointTuple(
                config=item_config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=parent_config,
                pending_writes=pending_writes,
            )
            count += 1

    async def adelete_thread(self, thread_id: str) -> None:
        keys = await self._syncer.scan_keys(f"checkpoint:{thread_id}:*")
        for key in keys:
            await self._syncer.delete(key)
        write_keys = await self._syncer.scan_keys(f"checkpoint_writes:{thread_id}:*")
        for key in write_keys:
            await self._syncer.delete(key)

    async def _load_pending_writes(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> builtins.list[tuple[str, str, Any]]:
        prefix = f"checkpoint_writes:{thread_id}:{checkpoint_ns}:{checkpoint_id}:"
        keys = await self._syncer.scan_keys(prefix + "*")
        pending_writes: list[tuple[str, str, Any]] = []
        for key in keys:
            if not key.startswith(prefix):
                continue
            task_id = key[len(prefix) :]
            raw = await self._syncer.get(key)
            if raw is None:
                continue
            record = self.serde.loads_typed(raw)
            for channel, value in record["writes"]:
                pending_writes.append((task_id, channel, value))
        return pending_writes

    async def adelete_for_runs(self, run_ids: Sequence[str]) -> None:
        raise NotImplementedError("delete_for_runs is not supported")

    async def acopy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        cp_keys = await self._syncer.scan_keys(f"checkpoint:{source_thread_id}:*")
        for key in cp_keys:
            value = await self._syncer.get(key)
            if value is not None:
                new_key = self._swap_thread_id_in_key(key, target_thread_id)
                await self._syncer.set(new_key, value, ttl=self._ttl)
        write_keys = await self._syncer.scan_keys(
            f"checkpoint_writes:{source_thread_id}:*"
        )
        for key in write_keys:
            value = await self._syncer.get(key)
            if value is not None:
                new_key = self._swap_thread_id_in_key(key, target_thread_id)
                await self._syncer.set(new_key, value, ttl=self._ttl)

    async def aprune(
        self,
        thread_ids: Sequence[str],
        *,
        strategy: str = "keep_latest",
    ) -> None:
        raise NotImplementedError("prune is not supported")

    @staticmethod
    def _get_key(thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"checkpoint:{thread_id}:{checkpoint_ns}:{checkpoint_id}"

    @staticmethod
    def _get_writes_key(
        thread_id: str, checkpoint_ns: str, checkpoint_id: str, task_id: str
    ) -> str:
        return (
            f"checkpoint_writes:{thread_id}:{checkpoint_ns}:{checkpoint_id}:{task_id}"
        )

    @staticmethod
    def _get_thread_prefix(thread_id: str, checkpoint_ns: str = "") -> str:
        return f"checkpoint:{thread_id}:{checkpoint_ns}:*"

    @staticmethod
    def _swap_thread_id_in_key(key: str, target_thread_id: str) -> str:
        parts = key.split(":")
        # Expected formats:
        #   checkpoint:<thread_id>:<ns>:<id>
        #   checkpoint_writes:<thread_id>:<ns>:<id>:<task_id>
        if len(parts) < 2:
            return key
        parts[1] = target_thread_id
        return ":".join(parts)
