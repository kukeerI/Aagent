# src/core/checkpoint.py
# 检查点管理系统 - 支持任务暂停、恢复和时光倒流
# 依赖：aiosqlite, json, os, uuid, asyncio, typing, datetime
# 注意事项：
#   - 使用 SQLite 数据库存储检查点数据
#   - 支持从检查点恢复任务执行
#   - 任务完成后自动清理检查点

import json
import os
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import aiosqlite


class Checkpoint:
    """检查点类

    表示任务执行过程中的一个状态快照，包含当前状态名称、上下文数据和时间戳。
    """

    def __init__(self, checkpoint_id: str, state_name: str, context: Dict[str, Any], timestamp: datetime):
        """初始化检查点

        Args:
            checkpoint_id: 检查点唯一标识
            state_name: 状态名称
            context: 上下文数据（任务状态）
            timestamp: 创建时间戳
        """
        self.checkpoint_id = checkpoint_id
        self.state_name = state_name
        self.context = context
        self.timestamp = timestamp


class CheckpointManager:
    """检查点管理器

    负责检查点的创建、获取、列表、删除和更新操作。
    使用 SQLite 数据库存储检查点数据，支持异步操作。
    """

    def __init__(self, db_path: str = "./checkpoints.db"):
        """初始化检查点管理器

        Args:
            db_path: 数据库文件路径，默认为 "./checkpoints.db"
        """
        self.db_path = db_path
        self._init_db()

    async def _init_db(self):
        """初始化数据库

        创建检查点表和索引，确保数据库结构正确。
        """
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    state_name TEXT NOT NULL,
                    context TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    trace_id TEXT
                )
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_checkpoints_trace_id 
                ON checkpoints (trace_id)
            ''')
            await conn.commit()

    async def create_checkpoint(self, state_name: str, context: Dict[str, Any]) -> Checkpoint:
        """创建检查点

        Args:
            state_name: 状态名称
            context: 上下文数据（任务状态）

        Returns:
            Checkpoint: 创建的检查点对象

        Raises:
            Exception: 数据库操作失败时抛出
        """
        checkpoint_id = str(uuid.uuid4())
        timestamp = datetime.now()

        # 确保 context 包含必要的字段
        if 'trace_id' not in context:
            context['trace_id'] = str(uuid.uuid4())
        if 'user_input' not in context:
            context['user_input'] = ''

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            state_name=state_name,
            context=context,
            timestamp=timestamp
        )

        # 保存检查点到数据库
        await self._save_checkpoint(checkpoint)

        return checkpoint

    async def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """获取检查点

        Args:
            checkpoint_id: 检查点唯一标识

        Returns:
            Optional[Checkpoint]: 检查点对象，如果不存在返回 None

        Raises:
            Exception: 数据库操作失败时抛出
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT checkpoint_id, state_name, context, timestamp FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None

            checkpoint_id, state_name, context_json, timestamp_str = row
            context = json.loads(context_json)
            timestamp = datetime.fromisoformat(timestamp_str)

            return Checkpoint(
                checkpoint_id=checkpoint_id,
                state_name=state_name,
                context=context,
                timestamp=timestamp
            )

    async def list_checkpoints(self, trace_id: str) -> List[Checkpoint]:
        """列出指定 trace_id 的所有检查点

        Args:
            trace_id: 追踪 ID

        Returns:
            List[Checkpoint]: 检查点列表

        Raises:
            Exception: 数据库操作失败时抛出
        """
        checkpoints = []

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT checkpoint_id, state_name, context, timestamp FROM checkpoints WHERE trace_id = ? ORDER BY timestamp",
                (trace_id,)
            )
            rows = await cursor.fetchall()

            for row in rows:
                checkpoint_id, state_name, context_json, timestamp_str = row
                context = json.loads(context_json)
                timestamp = datetime.fromisoformat(timestamp_str)

                checkpoint = Checkpoint(
                    checkpoint_id=checkpoint_id,
                    state_name=state_name,
                    context=context,
                    timestamp=timestamp
                )
                checkpoints.append(checkpoint)

        return checkpoints

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除检查点

        Args:
            checkpoint_id: 检查点唯一标识

        Returns:
            bool: 删除是否成功

        Raises:
            Exception: 数据库操作失败时抛出
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def delete_checkpoints_by_trace_id(self, trace_id: str) -> int:
        """删除指定 trace_id 的所有检查点

        Args:
            trace_id: 追踪 ID

        Returns:
            int: 删除的检查点数量

        Raises:
            Exception: 数据库操作失败时抛出
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM checkpoints WHERE trace_id = ?",
                (trace_id,)
            )
            await conn.commit()
            return cursor.rowcount

    async def _save_checkpoint(self, checkpoint: Checkpoint):
        """保存检查点到数据库

        Args:
            checkpoint: 检查点对象

        Raises:
            Exception: 数据库操作失败时抛出
        """
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO checkpoints (checkpoint_id, state_name, context, timestamp, trace_id) VALUES (?, ?, ?, ?, ?)",
                (
                    checkpoint.checkpoint_id,
                    checkpoint.state_name,
                    json.dumps(checkpoint.context, ensure_ascii=False),
                    checkpoint.timestamp.isoformat(),
                    checkpoint.context.get('trace_id')
                )
            )
            await conn.commit()

    async def update_checkpoint(self, checkpoint: Checkpoint):
        """更新检查点

        Args:
            checkpoint: 检查点对象

        Raises:
            Exception: 数据库操作失败时抛出
        """
        await self._save_checkpoint(checkpoint)
