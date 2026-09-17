"""Память об уже показанных лотах — переживает перезапуск программы.

Раньше список виденного жил только в оперативке, поэтому после рестарта
бот заново присылал те же лоты. Теперь ключи лежат на диске.
"""
import json
import time
from pathlib import Path

MAX_ITEMS = 200_000        # сколько ключей держим максимум
TTL_DAYS = 30              # и как долго


class SeenStore:
    """Множество ключей (gift_id, num) с отметкой времени и сохранением в файл."""

    def __init__(self, path: Path, max_items: int = MAX_ITEMS, ttl_days: int = TTL_DAYS):
        self.path = Path(path)
        self.max_items = max_items
        self.ttl = ttl_days * 86400
        self._data: dict[str, float] = {}
        self._dirty = False
        self._saved_at = 0.0

    # --- поведение множества, чтобы вызывающий код не менялся ---

    def __contains__(self, key) -> bool:
        return self._k(key) in self._data

    def __len__(self) -> int:
        return len(self._data)

    def add(self, key) -> None:
        self._data[self._k(key)] = time.time()
        self._dirty = True

    def clear(self) -> None:
        self._data.clear()
        self._dirty = True
        self.save(force=True)

    @staticmethod
    def _k(key) -> str:
        gift_id, num = key
        return f"{gift_id}:{num}"

    # --- диск ---

    def load(self) -> int:
        if not self.path.exists():
            return 0
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            return 0
        if isinstance(raw, dict):
            edge = time.time() - self.ttl
            self._data = {k: v for k, v in raw.items()
                          if isinstance(v, (int, float)) and v > edge}
        return len(self._data)

    def save(self, force: bool = False) -> None:
        """Пишем не чаще раза в 10 секунд, чтобы не трепать диск."""
        if not self._dirty:
            return
        if not force and time.time() - self._saved_at < 10:
            return

        if len(self._data) > self.max_items:      # оставляем самые свежие
            keep = sorted(self._data.items(), key=lambda kv: kv[1], reverse=True)
            self._data = dict(keep[:self.max_items])

        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self._data), "utf-8")
            tmp.replace(self.path)                # атомарная замена
            self._saved_at = time.time()
            self._dirty = False
        except OSError:
            pass
