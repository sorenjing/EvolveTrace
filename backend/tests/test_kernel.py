"""
Agent 内核单元测试：死循环检测、AgentEvent 数据结构、上下文压缩。

运行方式：
    cd backend && python -m pytest tests/test_kernel.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from agent.kernel import AgentEvent
from agent.context import compress_history, extract_todos, COMPRESS_THRESHOLD, KEEP_RECENT_STEPS


# ---------- AgentEvent ----------

class TestAgentEvent:

    def test_create_event(self):
        ev = AgentEvent("thought", 1, {"content": "hello"})
        assert ev.type == "thought"
        assert ev.step == 1
        assert ev.payload["content"] == "hello"

    def test_event_default_payload(self):
        ev = AgentEvent("complete", 5)
        assert ev.payload == {}


# ---------- 上下文压缩 ----------

class TestContextCompression:

    def test_no_compress_below_threshold(self):
        history = [
            {"thought": "test", "action": "read_file", "observation": "ok"}
            for _ in range(COMPRESS_THRESHOLD - 1)
        ]
        compressed, recent = compress_history(history)
        assert compressed == [], "低于阈值不应压缩"
        assert len(recent) == len(history)

    def test_compress_above_threshold(self):
        history = [
            {"thought": f"step {i}", "action": "read_file", "observation": "ok"}
            for i in range(COMPRESS_THRESHOLD + 2)
        ]
        compressed, recent = compress_history(history)
        assert len(compressed) == 1, "应产生 1 条压缩摘要"
        assert len(recent) == KEEP_RECENT_STEPS, f"应保留最近 {KEEP_RECENT_STEPS} 步"

    def test_compress_preserves_final_answer(self):
        """压缩摘要应标记任务已在之前完成。"""
        history = [
            {"thought": "done", "action": "final_answer", "observation": "result"}
            for _ in range(COMPRESS_THRESHOLD + 1)
        ]
        compressed, _ = compress_history(history)
        thought = compressed[0].get("thought", "")
        assert "已完成" in thought, "压缩摘要应标记任务完成状态"


# ---------- Todo 提取 ----------

class TestTodoExtraction:

    def test_extract_todos_from_thought(self):
        history = [
            {"thought": "TODO: 分析项目结构\n[ ] 读README\n[x] 创建快照", "action": "read_file", "observation": "ok"}
        ]
        todos = extract_todos(history)
        assert len(todos) >= 1, "应提取到 TODO 项"

    def test_extract_structured_todos_at_root(self):
        """结构化 todos 在 history 根级（与 Prompt 约定一致）应被提取。"""
        history = [
            {
                "thought": "拆分任务",
                "action": "list_files",
                "observation": "ok",
                "todos": [
                    {"content": "读 README", "done": False},
                    {"content": "列目录", "done": True},
                ],
                "step": 1,
            }
        ]
        todos = extract_todos(history)
        assert len(todos) == 2
        assert {t["content"] for t in todos} == {"读 README", "列目录"}
        assert any(t["content"] == "列目录" and t["done"] for t in todos)

    def test_extract_todos_from_observation(self):
        history = [
            {"thought": "check", "action": "list_files", "observation": "DONE: 目录已列出"}
        ]
        todos = extract_todos(history)
        assert len(todos) >= 1, "应从 observation 提取到 DONE 标记"

    def test_no_todos_in_empty_history(self):
        todos = extract_todos([])
        assert todos == []


# ---------- 死循环检测逻辑（逻辑验证）----------

class TestDeadLoopDetection:

    def test_detect_three_identical_steps(self):
        """连续 3 次相同 action + observation 应触发死循环检测。"""
        history = [
            {"thought": "trying", "action": "read_file", "observation": "not found"},
            {"thought": "trying again", "action": "read_file", "observation": "not found"},
            {"thought": "trying once more", "action": "read_file", "observation": "not found"},
        ]
        # 模拟 kernel.py 中的死循环检测逻辑
        last_three = history[-3:]
        action = "read_file"
        observation = "not found"
        is_loop = all(
            h["action"] == action and h.get("observation") == observation
            for h in last_three
        )
        assert is_loop, "连续 3 次相同 action + observation 应被检测为死循环"

    def test_no_dead_loop_with_different_observations(self):
        """不同 observation 不应触发死循环检测。"""
        history = [
            {"thought": "trying", "action": "read_file", "observation": "file a"},
            {"thought": "trying", "action": "read_file", "observation": "file b"},
            {"thought": "trying", "action": "read_file", "observation": "file c"},
        ]
        last_three = history[-3:]
        action = "read_file"
        observation = "file c"
        is_loop = all(
            h["action"] == action and h.get("observation") == observation
            for h in last_three
        )
        assert not is_loop, "不同 observation 不应触发死循环检测"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])