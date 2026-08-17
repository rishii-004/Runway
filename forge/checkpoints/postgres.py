from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    RunnableConfig,
    get_checkpoint_id,
)
from sqlalchemy import select

from forge.storage.models import CheckpointRow
from forge.storage.session import async_session


def _make_config(configurable: dict, checkpoint_id: str | None) -> RunnableConfig:
    cfg = dict(configurable)
    if checkpoint_id:
        cfg["checkpoint_id"] = checkpoint_id
    return {"configurable": cfg}


class PostgresCheckpointSaver(BaseCheckpointSaver[dict]):
    def __init__(self, session_factory=None):
        super().__init__()
        self._session_factory = session_factory or async_session

    def _get_thread_id(self, config: RunnableConfig) -> str:
        configurable = config.get("configurable", {})
        return configurable.get("thread_id", "")

    def _new_session(self):
        return self._session_factory()

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = self._get_thread_id(config)
        checkpoint_id = get_checkpoint_id(config)

        session = self._new_session()
        try:
            if checkpoint_id:
                stmt = select(CheckpointRow).where(
                    CheckpointRow.thread_id == thread_id,
                    CheckpointRow.checkpoint_id == checkpoint_id,
                )
            else:
                stmt = (
                    select(CheckpointRow)
                    .where(CheckpointRow.thread_id == thread_id)
                    .order_by(CheckpointRow.created_at.desc())
                    .limit(1)
                )

            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row is None:
                return None

            checkpoint = row.checkpoint_data.get("checkpoint", {})
            metadata = row.checkpoint_data.get("metadata", {})
            pending_writes = row.pending_writes

            parent_config = None
            if row.parent_checkpoint_id:
                parent_config = _make_config(
                    config["configurable"],
                    row.parent_checkpoint_id,
                )

            return CheckpointTuple(
                config=_make_config(config["configurable"], row.checkpoint_id),
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=parent_config,
                pending_writes=pending_writes,
            )
        finally:
            await session.close()

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        if config is None:
            return

        thread_id = self._get_thread_id(config)
        session = self._new_session()
        try:
            stmt = (
                select(CheckpointRow)
                .where(CheckpointRow.thread_id == thread_id)
                .order_by(CheckpointRow.created_at.desc())
            )
            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            rows = result.scalars().all()

            for row in rows:
                checkpoint = row.checkpoint_data.get("checkpoint", {})
                metadata = row.checkpoint_data.get("metadata", {})
                pending_writes = row.pending_writes

                parent_config = None
                if row.parent_checkpoint_id:
                    parent_config = _make_config(
                        config["configurable"],
                        row.parent_checkpoint_id,
                    )

                yield CheckpointTuple(
                    config=_make_config(config["configurable"], row.checkpoint_id),
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config=parent_config,
                    pending_writes=pending_writes,
                )
        finally:
            await session.close()

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = self._get_thread_id(config)
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = get_checkpoint_id(config)

        session = self._new_session()
        try:
            existing = await session.execute(
                select(CheckpointRow).where(
                    CheckpointRow.thread_id == thread_id,
                    CheckpointRow.checkpoint_id == checkpoint_id,
                )
            )
            existing_row = existing.scalar_one_or_none()

            data = {
                "checkpoint": checkpoint,
                "metadata": metadata,
            }

            if existing_row:
                existing_row.checkpoint_data = data
            else:
                row = CheckpointRow(
                    id=uuid.uuid4(),
                    run_id=uuid.uuid4(),
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    parent_checkpoint_id=parent_checkpoint_id,
                    checkpoint_data=data,
                )
                session.add(row)

            await session.commit()
        finally:
            await session.close()

        return _make_config(config["configurable"], checkpoint_id)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: list[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = self._get_thread_id(config)
        checkpoint_id = get_checkpoint_id(config)

        if not checkpoint_id:
            return

        session = self._new_session()
        try:
            stmt = select(CheckpointRow).where(
                CheckpointRow.thread_id == thread_id,
                CheckpointRow.checkpoint_id == checkpoint_id,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row:
                existing_writes = row.pending_writes or []
                existing_writes.extend(
                    [
                        {"task_id": task_id, "task_path": task_path, "channel": ch, "value": val}
                        for ch, val in writes
                    ]
                )
                row.pending_writes = existing_writes
                await session.commit()
        finally:
            await session.close()

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        raise NotImplementedError("Use async version")

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        raise NotImplementedError("Use async version")

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        raise NotImplementedError("Use async version")

    def put_writes(
        self,
        config: RunnableConfig,
        writes: list[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        raise NotImplementedError("Use async version")
