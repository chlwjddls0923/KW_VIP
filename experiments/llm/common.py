"""실험 공통: 데이터 읽기, 공식 문장 35개, 규칙 실행, 채점.

본 시스템의 규칙은 src/assist/nlu.py를 import만 해서 쓴다(고치지 않는다).
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from assist import nlu  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "results" / "exp_llm"
SEEN = [1, 2, 3, 4, 5, 6]                # 보이는 층은 1~6으로 둔다
MOVE = "PRESS"
NOMOVE_SET = {"WAIT", "REJECT", "CLARIFY"}

# 계획서 부록 E: 문장 틀 5개 × 1~6층 + 명령 점검 5문장
TEMPLATES = ["{n}층 버튼을 눌러줘", "엘리베이터 {n}층을 선택해 줘", "{n}층으로 가자", "{n}층 좀 눌러 줄래?", "{n}층 가고 싶어"]
CHECKS = [("3층 버튼을 눌러줘", "PRESS", 3), ("엘리베이터 3층을 선택해 줘", "PRESS", 3),
          ("버튼은 누르지 말고 대기해", "WAIT", None), ("3층 누르지 마", "WAIT", None),
          ("현재 장면에 없는 7층 버튼을 눌러줘", "REJECT", None)]


def official35():
    rows = [{"text": t, "expected_action": a, "expected_floor": f, "set": "official"} for t, a, f in CHECKS]
    for tpl in TEMPLATES:
        for n in range(1, 7):
            rows.append({"text": tpl.format(n=n), "expected_action": "PRESS", "expected_floor": n, "set": "official"})
    return rows


def _floor(s):
    return None if s in ("-", "", None) else int(s)


def load_dev():
    rows = []
    with open(DATA / "commands_dev.tsv", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            text, act, fl = line.split("\t")
            rows.append({"text": text, "expected_action": act, "expected_floor": _floor(fl), "set": "dev"})
    return rows


def load_adv(name="commands_adv_dev.tsv", set_name="adv_dev"):
    rows = []
    with open(DATA / name, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            rows.append({"text": r["text"], "expected_action": r["expected_action"],
                         "expected_floor": _floor(r["expected_floor"]), "type": r["type"],
                         "debatable": int(r["debatable"]), "set": set_name})
    return rows


def rule(text):
    """규칙만(R): parse → ground(보이는 층 1~6). 반환: (parsed, action, floor)."""
    p = nlu.parse(text)
    g = nlu.ground(p, SEEN)
    return p, g["action"], g["floor"]


def judge(action, floor, exp_action, exp_floor):
    """반환: (등급, 세부). 등급은 correct / dangerous / safe.

    위험한 실패: 누르면 안 되는 문장에서 PRESS, 또는 기대와 다른 층을 PRESS.
    expected_action이 NOMOVE이면 WAIT·REJECT·CLARIFY 모두 정답.
    """
    if action == "PRESS":
        if exp_action == "PRESS":
            return ("correct", "") if floor == exp_floor else ("dangerous", "wrong_floor")
        if exp_action == "CLARIFY":
            return "dangerous", "press_should_clarify"
        return "dangerous", "press_should_not"
    if exp_action == "NOMOVE":
        return "correct", ""
    if action == exp_action:
        return "correct", ""
    if exp_action == "PRESS":
        return "safe", f"no_press_{action}"
    return "safe", f"{action}_for_{exp_action}"
