"""쇼핑 리스트 아이템 저장/불러오기.

저장소를 교체할 때(예: Google Sheets, Supabase)는 이 파일의
load_items / save_items / update_items 구현만 바꾸면 된다.
"""

import json
import os
import tempfile
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

DATA_PATH = Path(__file__).resolve().parent / "data.json"
MAX_NAME_LEN = 50
MIN_QTY, MAX_QTY = 1, 999

# Streamlit은 세션(탭)마다 스레드로 실행되므로 프로세스 단위 락으로
# "읽기 → 변경 → 쓰기"를 원자적으로 묶어 탭 간 덮어쓰기를 막는다.
_lock = threading.RLock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_item(name: str, quantity: int = 1) -> dict:
    """PRD 4.3 데이터 모델에 맞는 새 아이템을 만든다."""
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "quantity": quantity,
        "checked": False,
        "created_at": _now(),
    }


def _normalize(raw: object) -> dict | None:
    """저장된 아이템 하나를 검증·보정한다. 복구할 수 없으면 None."""
    if not isinstance(raw, dict):
        return None
    item_id = raw.get("id")
    name = raw.get("name")
    if not isinstance(item_id, str) or not item_id:
        return None
    if isinstance(name, (int, float)) and not isinstance(name, bool):
        name = str(name)
    if not isinstance(name, str) or not name.strip():
        return None
    try:
        qty = int(raw.get("quantity", 1))
    except (TypeError, ValueError):
        qty = 1
    created = raw.get("created_at")
    return {
        "id": item_id,
        "name": name.strip()[:MAX_NAME_LEN],
        "quantity": min(max(qty, MIN_QTY), MAX_QTY),
        "checked": raw.get("checked") is True,
        "created_at": created if isinstance(created, str) else _now(),
    }


def _backup_corrupt_file() -> Path:
    """손상된 파일을 옆으로 옮겨 다음 저장 때 덮어써지지 않게 한다."""
    backup = DATA_PATH.with_name(f"data.corrupt-{datetime.now():%Y%m%d-%H%M%S}.json")
    os.replace(DATA_PATH, backup)
    return backup


def load_items(on_warning: Callable[[str], None] | None = None) -> list[dict]:
    """data.json에서 아이템 목록을 읽는다.

    - 파일이 없으면 빈 리스트.
    - 파일이 손상됐으면 data.corrupt-*.json으로 백업한 뒤 빈 리스트 (on_warning으로 알림).
    - 형식이 잘못된 아이템은 보정하거나 건너뛴다 (on_warning으로 알림).
    """
    warn = on_warning or (lambda msg: None)
    with _lock:
        try:
            with DATA_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return []
        except (json.JSONDecodeError, UnicodeDecodeError):
            backup = _backup_corrupt_file()
            warn(f"저장 파일이 손상되어 백업 파일({backup.name})을 만들고 빈 리스트로 시작합니다.")
            return []
        except OSError as e:
            warn(f"저장 파일을 읽지 못했어요: {e}")
            return []

        if not isinstance(data, list):
            backup = _backup_corrupt_file()
            warn(f"저장 파일 형식이 올바르지 않아 백업 파일({backup.name})을 만들고 빈 리스트로 시작합니다.")
            return []

        items, seen = [], set()
        for raw in data:
            item = _normalize(raw)
            if item and item["id"] not in seen:
                seen.add(item["id"])
                items.append(item)
        if skipped := len(data) - len(items):
            warn(f"형식이 잘못된 아이템 {skipped}개를 건너뛰었어요.")
        return items


def save_items(items: list[dict]) -> None:
    """임시 파일에 쓴 뒤 교체해서, 저장 도중 중단돼도 기존 파일이 깨지지 않게 한다."""
    with _lock:
        fd, tmp = tempfile.mkstemp(dir=DATA_PATH.parent, prefix=".data-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            # Windows에서는 다른 프로세스가 파일을 읽는 중이면 교체가 잠시 실패할 수 있다.
            for attempt in range(5):
                try:
                    os.replace(tmp, DATA_PATH)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


def update_items(mutate: Callable[[list[dict]], None]) -> list[dict]:
    """최신 파일을 읽어 mutate로 변경하고 저장한 뒤 결과를 돌려준다.

    다른 탭/기기의 변경 사항 위에 반영되므로 서로 덮어쓰지 않는다.
    """
    with _lock:
        items = load_items()
        mutate(items)
        save_items(items)
        return items
