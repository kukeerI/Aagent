# src/core/checkpoint.py
# 检查点管理系统 - 支持任务暂停、恢复和时光倒流

import json
import os
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

class Checkpoint:
    """检查点"""
    def __init__(self, checkpoint_id: str, state_name: str, context: Dict[str, Any], timestamp: datetime):
        self.checkpoint_id = checkpoint_id
        self.state_name = state_name
        self.context = context
        self.timestamp = timestamp

class CheckpointManager:
    """检查点管理器"""
    def __init__(self, storage_dir: str = "./checkpoints"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def create_checkpoint(self, state_name: str, context: Dict[str, Any]) -> Checkpoint:
        """创建检查点"""
        checkpoint_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        # 使用 StateDTO 验证和序列化上下文
        try:
            # 动态导入 StateDTO，避免循环导入
            from src.core.state import StateDTO
            
            # 确保 context 包含必要的字段
            if 'trace_id' not in context:
                context['trace_id'] = str(uuid.uuid4())
            if 'user_input' not in context:
                context['user_input'] = ''
            
            # 使用 StateDTO 验证和序列化
            state_dto = StateDTO(**context)
            validated_context = state_dto.model_dump()
        except Exception as e:
            print(f"[CheckpointManager] 验证上下文失败: {e}")
            # 如果验证失败，使用默认值
            validated_context = {
                'trace_id': context.get('trace_id', str(uuid.uuid4())),
                'user_input': context.get('user_input', ''),
                'final_answer': context.get('final_answer'),
                'error': context.get('error')
            }
        
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            state_name=state_name,
            context=validated_context,
            timestamp=timestamp
        )
        
        # 保存检查点到文件
        self._save_checkpoint(checkpoint)
        
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """获取检查点"""
        checkpoint_path = os.path.join(self.storage_dir, f"{checkpoint_id}.json")
        if not os.path.exists(checkpoint_path):
            return None
        
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return Checkpoint(
            checkpoint_id=data['checkpoint_id'],
            state_name=data['state_name'],
            context=data['context'],
            timestamp=datetime.fromisoformat(data['timestamp'])
        )

    def list_checkpoints(self, trace_id: str) -> List[Checkpoint]:
        """列出指定trace_id的所有检查点"""
        checkpoints = []
        
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                checkpoint_path = os.path.join(self.storage_dir, filename)
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data['context'].get('trace_id') == trace_id:
                    checkpoint = Checkpoint(
                        checkpoint_id=data['checkpoint_id'],
                        state_name=data['state_name'],
                        context=data['context'],
                        timestamp=datetime.fromisoformat(data['timestamp'])
                    )
                    checkpoints.append(checkpoint)
        
        # 按时间排序
        checkpoints.sort(key=lambda x: x.timestamp)
        return checkpoints

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除检查点"""
        checkpoint_path = os.path.join(self.storage_dir, f"{checkpoint_id}.json")
        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)
            return True
        return False

    def delete_checkpoints_by_trace_id(self, trace_id: str) -> int:
        """删除指定trace_id的所有检查点"""
        deleted = 0
        
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                checkpoint_path = os.path.join(self.storage_dir, filename)
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data['context'].get('trace_id') == trace_id:
                    os.remove(checkpoint_path)
                    deleted += 1
        
        return deleted

    def _save_checkpoint(self, checkpoint: Checkpoint):
        """保存检查点到文件"""
        checkpoint_path = os.path.join(self.storage_dir, f"{checkpoint.checkpoint_id}.json")
        
        data = {
            'checkpoint_id': checkpoint.checkpoint_id,
            'state_name': checkpoint.state_name,
            'context': checkpoint.context,
            'timestamp': checkpoint.timestamp.isoformat()
        }
        
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def update_checkpoint(self, checkpoint: Checkpoint):
        """更新检查点"""
        self._save_checkpoint(checkpoint)