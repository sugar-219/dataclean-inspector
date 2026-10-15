"""有界历史栈；数据管理器仅替换状态，不对快照就地修改。"""


class UndoManager:
    def __init__(self, limit=20):
        self.limit = limit
        self._states = []

    def push(self, state):
        self._states.append(state)
        self.set_limit(self.limit)

    def peek(self):
        """读取最近状态但不出栈，调用方确认恢复成功后再 pop。"""
        if not self._states:
            raise ValueError("没有可撤销的操作。")
        return self._states[-1]

    def pop(self):
        if not self._states:
            raise ValueError("没有可撤销的操作。")
        return self._states.pop()

    def set_limit(self, limit):
        self.limit = max(1, min(20, int(limit)))
        self._states = self._states[-self.limit:]

    def clear(self):
        self._states.clear()

    def __len__(self):
        return len(self._states)
