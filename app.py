import html
import re

import streamlit as st

from storage import MAX_NAME_LEN, MAX_QTY, MIN_QTY, load_items, make_item, update_items

st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")

# 최소한의 CSS. 색상은 고정하지 않고 opacity로 처리해 라이트/다크 테마 모두 대응.
st.markdown(
    """
<style>
/* 아이템 행: 모바일에서도 한 줄 유지, 버튼은 터치하기 좋은 44px */
[class*="st-key-row_"] [data-testid="stHorizontalBlock"],
.st-key-add_row [data-testid="stHorizontalBlock"],
.st-key-undo_bar [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.5rem !important;
    align-items: center;
}
[class*="st-key-row_"] [data-testid="stColumn"],
.st-key-add_row [data-testid="stColumn"],
.st-key-undo_bar [data-testid="stColumn"] {
    min-width: 0 !important;
    width: auto !important;
}
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(1) { flex: 0 0 2rem !important; }
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(2) { flex: 1 1 0 !important; }
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(3) { flex: 0 0 auto !important; }
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(4),
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(5) { flex: 0 0 2.75rem !important; }
[class*="st-key-row_"] {
    padding: 0.1rem 0.25rem;
    border-bottom: 1px solid rgba(128, 128, 128, 0.18);
}
[class*="st-key-row_"] p { margin: 0; }
/* Streamlit 기본 마크다운의 음수 하단 여백이 세로 정렬을 깨뜨려서 제거 */
[class*="st-key-row_"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
[class*="st-key-row_"] button {
    min-width: 2.75rem;
    min-height: 2.75rem;
    padding: 0;
    font-size: 1.15rem;
    justify-content: center;
}
/* 버튼 글자(스크린리더용 "OO 수정/삭제")는 숨기고 아이콘만 표시 */
[class*="st-key-row_"] button [data-testid="stMarkdownContainer"] {
    position: absolute !important;
    width: 1px; height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
}
[class*="st-key-row_"] [data-testid="stCheckbox"] label {
    min-height: 2.75rem;
    align-items: center;
}
.item-name {
    overflow-wrap: anywhere;
    word-break: break-word;
    line-height: 1.4;
}
.item-name.done, .item-qty.done {
    text-decoration: line-through;
    opacity: 0.45;
}
.item-qty {
    opacity: 0.65;
    font-size: 0.9rem;
    white-space: nowrap;
    text-align: right;
}
.st-key-add_row [data-testid="stColumn"]:nth-child(1) { flex: 1 1 0 !important; }
.st-key-add_row [data-testid="stColumn"]:nth-child(2) { flex: 0 0 6rem !important; }
.st-key-undo_bar [data-testid="stColumn"]:nth-child(1) { flex: 1 1 0 !important; }
.st-key-undo_bar [data-testid="stColumn"]:nth-child(2) { flex: 0 0 auto !important; }
@media (max-width: 480px) {
    h1 { font-size: 1.9rem !important; }
    [data-testid="stMainBlockContainer"] { padding-top: 2.5rem !important; }
}
</style>
""",
    unsafe_allow_html=True,
)

ss = st.session_state
for _k, _v in {"editing_id": None, "add_error": None, "edit_error": None,
               "notices": [], "undo": None, "new_name": "", "new_qty": 1}.items():
    ss.setdefault(_k, _v)


# --- 헬퍼 ---
def find(items: list[dict], item_id: str) -> dict | None:
    return next((it for it in items if it["id"] == item_id), None)


def mutate(fn) -> None:
    """최신 저장 파일 위에 변경을 적용하고 세션 목록을 갱신 (탭 간 덮어쓰기 방지)."""
    ss.shopping_items = update_items(fn)


def escape_md(text: str) -> str:
    """사용자 입력이 마크다운 문법으로 해석되지 않도록 이스케이프."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|~<>])", r"\\\1", text)


def validate(name: str, qty) -> tuple[str | None, str | None]:
    """(정리된 이름, 오류 메시지). 50자 초과는 잘라서 저장하고 알림."""
    name = (name or "").strip()
    if not name:
        return None, "아이템 이름을 입력해 주세요."
    if qty is None or not (MIN_QTY <= qty <= MAX_QTY):
        return None, f"수량은 {MIN_QTY}~{MAX_QTY} 사이로 입력해 주세요."
    if len(name) > MAX_NAME_LEN:
        ss.notices.append(f"이름이 {MAX_NAME_LEN}자를 넘어서 앞 {MAX_NAME_LEN}자만 저장했어요.")
        name = name[:MAX_NAME_LEN]
    return name, None


def missing_notice() -> None:
    ss.notices.append("다른 화면에서 이미 삭제된 아이템이에요.")


# --- 콜백 (위젯 렌더링 전에 실행되므로 순회 중 리스트 변경 문제가 없음) ---
def on_add() -> None:
    name, err = validate(ss.new_name, ss.new_qty)
    ss.add_error = err
    if err:
        return  # 입력값은 그대로 남겨서 고칠 수 있게
    new = make_item(name, int(ss.new_qty))
    mutate(lambda items: items.append(new))
    ss.new_name, ss.new_qty = "", 1
    ss.undo = None


def on_toggle(item_id: str) -> None:
    want = ss[f"chk_{item_id}"]
    found = []

    def fn(items):
        if item := find(items, item_id):
            item["checked"] = want
            found.append(True)

    mutate(fn)
    if not found:
        missing_notice()
    ss.undo = None


def on_start_edit(item_id: str) -> None:
    item = find(ss.shopping_items, item_id)
    if item is None:
        return
    ss.editing_id = item_id
    ss.edit_error = None
    ss[f"edit_name_{item_id}"] = item["name"]
    ss[f"edit_qty_{item_id}"] = item["quantity"]


def on_save_edit(item_id: str) -> None:
    name, err = validate(ss[f"edit_name_{item_id}"], ss[f"edit_qty_{item_id}"])
    ss.edit_error = err
    if err:
        return
    qty = int(ss[f"edit_qty_{item_id}"])
    found = []

    def fn(items):
        if item := find(items, item_id):
            item["name"], item["quantity"] = name, qty
            found.append(True)

    mutate(fn)
    if not found:
        missing_notice()
    ss.editing_id = None
    ss.undo = None


def on_cancel_edit() -> None:
    ss.editing_id = None
    ss.edit_error = None


def _remove(pred) -> list[tuple[int, dict]]:
    removed = []

    def fn(items):
        keep = []
        # 주의: 한 줄 조건식을 문장으로 쓰면 Streamlit 매직이 결과(None)를 화면에 출력함
        for i, it in enumerate(items):
            if pred(it):
                removed.append((i, it))
            else:
                keep.append(it)
        items[:] = keep

    mutate(fn)
    if ss.editing_id and any(it["id"] == ss.editing_id for _, it in removed):
        on_cancel_edit()
    return removed


def on_delete(item_id: str) -> None:
    removed = _remove(lambda it: it["id"] == item_id)
    if removed:
        ss.undo = {"items": removed, "label": f"'{removed[0][1]['name']}' 삭제됨"}
    else:
        missing_notice()


def on_delete_checked() -> None:
    removed = _remove(lambda it: it["checked"])
    if removed:
        ss.undo = {"items": removed, "label": f"체크된 항목 {len(removed)}개 삭제됨"}


def on_undo() -> None:
    restore = (ss.undo or {}).get("items", [])

    def fn(items):
        ids = {it["id"] for it in items}
        for idx, it in sorted(restore, key=lambda x: x[0]):
            if it["id"] not in ids:
                items.insert(min(idx, len(items)), it)

    mutate(fn)
    ss.undo = None


# --- 데이터 불러오기: 매 실행마다 최신 파일을 읽어 다른 탭/기기의 변경도 반영 ---
load_warnings: list[str] = []
ss.shopping_items = load_items(load_warnings.append)
items = ss.shopping_items
if ss.editing_id and not find(items, ss.editing_id):
    on_cancel_edit()

# --- 제목 / 진행률 ---
st.title("🛒 쇼핑 리스트")
for w in load_warnings:
    st.warning(w, icon="⚠️")
for n in ss.notices:
    st.toast(n, icon="ℹ️")
ss.notices = []

total = len(items)
done = sum(1 for it in items if it["checked"])
st.progress(done / total if total else 0.0, text=f"{done} / {total} 완료")
if total and done == total:
    st.caption("🎉 모두 담았어요!")

# --- 입력 영역 (F-01) ---
with st.form("add_form", clear_on_submit=False, border=True):
    st.text_input("아이템 이름", key="new_name", placeholder=f"예: 우유 (최대 {MAX_NAME_LEN}자)")
    with st.container(key="add_row"):
        c_qty, c_btn = st.columns(2, vertical_alignment="bottom")
        c_qty.number_input("수량", key="new_qty", step=1)
        c_btn.form_submit_button("추가", type="primary", on_click=on_add, width="stretch")
if ss.add_error:
    st.warning(ss.add_error, icon="⚠️")

# --- 리스트 영역 (F-02, F-03, F-04) ---
if ss.undo:
    with st.container(key="undo_bar", border=True):
        c_msg, c_btn = st.columns(2, vertical_alignment="center")
        c_msg.markdown(f"🗑️ {escape_md(ss.undo['label'])}")
        c_btn.button("되돌리기", key="undo_btn", on_click=on_undo)

if not items:
    st.info("아직 아이템이 없어요. 위에서 추가해 보세요!", icon="📝")

# 화면에는 미체크 → 체크 순으로 표시 (저장 순서는 그대로)
for item in sorted(items, key=lambda it: it["checked"]):
    item_id = item["id"]
    plain = escape_md(item["name"])  # 위젯 레이블용 (마크다운 해석 방지)

    if ss.editing_id == item_id:
        with st.container(key=f"edit_{item_id}_box"):
            # form이라 이름 입력 중 Enter로도 저장됨
            with st.form(f"edit_form_{item_id}", border=True):
                c_name, c_qty = st.columns([3, 1], vertical_alignment="bottom")
                c_name.text_input("이름", key=f"edit_name_{item_id}")
                c_qty.number_input("수량", key=f"edit_qty_{item_id}", step=1)
                if ss.edit_error:
                    st.warning(ss.edit_error, icon="⚠️")
                c_save, c_cancel, _ = st.columns([1, 1, 3])
                c_save.form_submit_button("저장", type="primary", on_click=on_save_edit,
                                          args=(item_id,), width="stretch")
                c_cancel.form_submit_button("취소", on_click=on_cancel_edit, width="stretch")
        continue

    # 다른 탭에서 바뀐 체크 상태를 위젯에 반영 (value= 대신 세션 상태로 동기화)
    ss[f"chk_{item_id}"] = item["checked"]
    done_cls = " done" if item["checked"] else ""
    with st.container(key=f"row_{item_id}"):
        c_chk, c_name, c_qty, c_edit, c_del = st.columns(5, vertical_alignment="center")
        c_chk.checkbox(f"{plain} 구매 완료", key=f"chk_{item_id}", on_change=on_toggle,
                       args=(item_id,), label_visibility="collapsed")
        # html.escape로 HTML 주입 방지 + escape_md로 마크다운 해석 방지
        # quote=False: 따옴표가 &#x27;로 바뀌면 escape_md가 #을 이스케이프해 엔티티가 깨짐
        safe_name = escape_md(html.escape(item["name"], quote=False))
        c_name.markdown(f'<span class="item-name{done_cls}">{safe_name}</span>',
                        unsafe_allow_html=True)
        c_qty.markdown(f'<div class="item-qty{done_cls}">x{int(item["quantity"])}</div>',
                       unsafe_allow_html=True)
        # 편집 중에는 다른 아이템 수정 버튼을 막아 입력 중인 내용이 사라지지 않게 함
        c_edit.button(f"{plain} 수정", key=f"edit_{item_id}", icon="✏️", type="tertiary",
                      on_click=on_start_edit, args=(item_id,), help="수정",
                      disabled=ss.editing_id is not None)
        c_del.button(f"{plain} 삭제", key=f"del_{item_id}", icon="🗑️", type="tertiary",
                     on_click=on_delete, args=(item_id,), help="삭제")

# --- 하단 버튼 영역 (F-03 일괄 삭제) ---
st.write("")
st.button(f"🧹 체크된 항목 모두 삭제 ({done})", on_click=on_delete_checked,
          disabled=done == 0, width="stretch")
