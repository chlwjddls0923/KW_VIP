"""단계 4 통과 기준: 명령 해석. 판정은 모두 ground(parse(text), {1..6})로 한다. holdout 파일은 열지 않는다."""
import time

import pytest

from assist import nlu
from assist.paths import DATA

SEEN = {1, 2, 3, 4, 5, 6}


def load_dev():
    rows = []
    with open(DATA / "commands_dev.tsv", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                text, action, floor = line.rstrip("\n").split("\t")
                rows.append((text, action, None if floor == "-" else int(floor)))
    return rows


def _correct(g, action, floor):
    return g["action"] == action and (action != "PRESS" or g["floor"] == floor)


def test_dev_all_pass_and_no_false_press():
    rows = load_dev()
    assert len(rows) == 78
    nlu.get_kiwi()                                    # 초기화는 시간에서 뺀다
    wrong, false_press, times = [], [], []
    for text, action, floor in rows:
        t0 = time.perf_counter()
        g = nlu.ground(nlu.parse(text), SEEN)
        times.append((time.perf_counter() - t0) * 1000)
        if not _correct(g, action, floor):
            wrong.append((text, action, floor, g))
        if action != "PRESS" and g["action"] == "PRESS":
            false_press.append(text)
    base = sum(_correct(nlu.ground(nlu.digits_only(t), SEEN), a, f) for t, a, f in rows)
    times.sort()
    print(f"\nnlu dev {len(rows) - len(wrong)}/{len(rows)}, false PRESS {len(false_press)}; "
          f"digits_only dev {base}/{len(rows)}")
    print(f"per-sentence ms: median {times[len(times) // 2]:.3f}, max {times[-1]:.3f}; "
          f"analyzer init {nlu.INIT_MS:.0f} ms")
    assert not wrong, wrong
    assert not false_press, false_press


@pytest.mark.parametrize("text,floor", [
    ("3층 눌러", 3), ("삼층 눌러", 3), ("십이층 눌러", 12), ("이십삼층 눌러", 23), ("3f 눌러", 3),
    ("3번째 층 눌러", 3), ("세 번째 층 눌러", 3), ("셋째 층 눌러", 3), ("지하 1층 눌러", -1), ("b1층 눌러", -1),
])
def test_floor_reading(text, floor):
    p = nlu.parse(text)
    assert p["intent"] == "PRESS" and p["floor"] == floor, p


def test_floor_count_is_not_floor():
    """'한 층', '세 층'은 층의 개수라 층으로 읽지 않는다."""
    assert nlu.parse("한 층 올라가줘")["floors"] == []
    assert nlu.parse("세 층 올라가줘")["floors"] == []


@pytest.mark.parametrize("text,intent,floor", [
    ("3층 눌러도 돼?", "PRESS", 3), ("3층 누를까?", "PRESS", 3),
    ("3층은 누를 일 없어", "PRESS", 3), ("3층 누르는 건 좀 그래", "PRESS", 3),
    ("3층입니다", "PRESS", 3), ("이 층 눌러줘", "PRESS", 2),
    ("문 열고 3층 눌러줘", "PRESS", 3), ("3층 누르고 문 닫아줘", "REJECT", None),
    ("3층이랑 4층 눌러줘", "CLARIFY", None),
])
def test_known_limits_reproduce(text, intent, floor):
    """부록 D의 알려진 한계: 고치지 않고 그대로 재현되는지 기록한다(docs/EXPLAIN.md에 적는다)."""
    p = nlu.parse(text)
    assert (p["intent"], p["floor"]) == (intent, floor), p


def test_ground_and_baseline():
    assert nlu.ground(nlu.parse("7층 눌러줘"), SEEN)["action"] == "REJECT"
    assert nlu.ground(nlu.parse("4층 눌러줘"), {3}) == {"action": "REJECT", "floor": 4, "reason": "not_visible"}
    assert nlu.ground(nlu.parse("3층 눌러줘"), {3})["action"] == "PRESS"
    assert nlu.digits_only("3층 누르지 마") == {"intent": "PRESS", "floor": 3}
    assert nlu.digits_only("3f 눌러줘") == {"intent": "REJECT", "floor": None}
