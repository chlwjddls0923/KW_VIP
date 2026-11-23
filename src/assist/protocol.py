"""평가 프로토콜: 시행 조건 추출, 판정, 실패 유형 분류 (계획서 부록 E).

조건 값은 시드에서 정해진 순서로 뽑는다. 판정은 시뮬레이터 신호(slide, 관절각)를 쓰며 채점 전용이다.
"""
from dataclasses import asdict, dataclass, field

import numpy as np

from .scene import POSITIONS, layout_from_perm, layout_string

SUCCESS_SLIDE = 0.010         # 성공 기준 변위 10 mm
OTHER_LIMIT = 0.010           # 누르기 시행: 다른 버튼은 모두 < 10 mm
STILL_SLIDE = 0.001           # 움직이면 안 되는 시행: 모든 버튼 < 1 mm
STILL_JOINT = 0.02            # 움직이면 안 되는 시행: 팔 관절 최대 변화 < 0.02 rad
TIME_LIMIT = 30.0             # 시뮬레이션 30초

TEMPLATES = ("{n}층 버튼을 눌러줘", "엘리베이터 {n}층을 선택해 줘", "{n}층으로 가자", "{n}층 좀 눌러 줄래?", "{n}층 가고 싶어")
CHECKS = (
    ("C01", "3층 버튼을 눌러줘", "PRESS", 3),
    ("C02", "엘리베이터 3층을 선택해 줘", "PRESS", 3),
    ("C03", "버튼은 누르지 말고 대기해", "WAIT", None),
    ("C04", "3층 누르지 마", "WAIT", None),
    ("C05", "현재 장면에 없는 7층 버튼을 눌러줘", "REJECT", None),
)
# 실패 유형 (위에서부터 먼저 해당하는 것)
PRESS_FAILURES = ("exception", "nlu", "not_detected", "wrong_button", "ik_unreachable", "under_10mm", "timeout")
STILL_FAILURES = ("nlu", "moved")
FAILURE_KO = {"exception": "실행 예외", "nlu": "명령 해석", "not_detected": "인식 미검출", "wrong_button": "다른 버튼 누름",
              "ik_unreachable": "IK 도달 불가", "under_10mm": "접촉 10 mm 미달", "timeout": "시간 초과",
              "moved": "움직임 발생"}


@dataclass
class Trial:
    trial_id: str
    set: str                   # basic / variation / check / supp_basic / supp_variation / dev
    seed: int | None
    text: str
    expected_action: str
    expected_floor: int | None
    dpos: tuple = (0.0, 0.0, 0.0)
    yaw_deg: float = 0.0
    light: float = 1.0
    perm: tuple | None = None  # None이면 기본 숫자 배치
    template: int | None = None

    @property
    def layout(self):
        return layout_from_perm(self.perm) if self.perm is not None else {n: POSITIONS[n] for n in POSITIONS}

    @property
    def layout_str(self):
        return layout_string(self.layout)

    def to_dict(self):
        d = asdict(self)
        d["layout"] = self.layout_str
        return d


def basic_trial(trial_id, seed, set_name="basic"):
    """기본: dx, dy, dz(각 ±0.03) → 목표 층 → 문장 틀 번호."""
    rng = np.random.default_rng(seed)
    dpos = tuple(float(rng.uniform(-0.03, 0.03)) for _ in range(3))
    floor = int(rng.integers(1, 7))
    tmpl = int(rng.integers(0, 5))
    return Trial(trial_id, set_name, seed, TEMPLATES[tmpl].format(n=floor), "PRESS", floor,
                 dpos=dpos, template=tmpl)


def variation_trial(trial_id, seed, set_name="variation"):
    """변화: dx(±0.10), dy(±0.05), dz(±0.10) → 회전(±10°) → 조명(0.6~1.2) → 숫자 배치 → 목표 층 → 문장 틀 번호."""
    rng = np.random.default_rng(seed)
    dx = float(rng.uniform(-0.10, 0.10))
    dy = float(rng.uniform(-0.05, 0.05))
    dz = float(rng.uniform(-0.10, 0.10))
    yaw = float(rng.uniform(-10.0, 10.0))
    light = float(rng.uniform(0.6, 1.2))
    perm = tuple(int(p) for p in rng.permutation(6))
    floor = int(rng.integers(1, 7))
    tmpl = int(rng.integers(0, 5))
    return Trial(trial_id, set_name, seed, TEMPLATES[tmpl].format(n=floor), "PRESS", floor,
                 dpos=(dx, dy, dz), yaw_deg=yaw, light=light, perm=perm, template=tmpl)


def check_trials():
    return [Trial(cid, "check", None, text, act, floor) for cid, text, act, floor in CHECKS]


def official_trials():
    return ([basic_trial(f"B{i:02d}", 1000 + i) for i in range(1, 11)]
            + [variation_trial(f"V{i:02d}", 2000 + i) for i in range(1, 11)]
            + check_trials())


def baseline_trials():
    """고정 좌표 기준선: 공식 20회와 같은 조건, ID만 FB/FV."""
    out = []
    for t in official_trials()[:20]:
        d = dict(t.__dict__)
        d["trial_id"] = "F" + t.trial_id
        out.append(Trial(**d))
    return out


def supplementary_trials():
    return ([basic_trial(f"SB{i:03d}", 3000 + i, "supp_basic") for i in range(1, 101)]
            + [variation_trial(f"SV{i:03d}", 4000 + i, "supp_variation") for i in range(1, 101)])


def dev_trials():
    return [variation_trial(f"D{i:02d}", 5000 + i, "dev") for i in range(1, 21)]


def judge(trial, rec):
    """반환: (성공 여부, 실패 유형 또는 '').  rec는 pipeline.run 결과 + exception 키."""
    if trial.expected_action == "PRESS":
        n = trial.expected_floor
        if rec.get("exception"):
            return False, "exception"
        if rec["parsed_intent"] != "PRESS" or rec["parsed_floor"] != n:
            return False, "nlu"
        if n not in rec["seen_floors"]:
            return False, "not_detected"
        slides = rec["max_slide"]
        if any(v >= OTHER_LIMIT for k, v in slides.items() if k != n):
            return False, "wrong_button"
        if not rec["plan_ok"]:
            return False, "ik_unreachable"
        if slides.get(n, 0.0) < SUCCESS_SLIDE:
            return False, "under_10mm"
        t = rec["t_first_10mm"].get(n)
        if t is None or t > TIME_LIMIT:
            return False, "timeout"
        return True, ""
    # 움직이면 안 되는 시행
    if rec.get("exception") or rec["action"] != trial.expected_action:
        return False, "nlu"
    if rec["max_joint_motion"] >= STILL_JOINT or max(rec["max_slide"].values()) >= STILL_SLIDE:
        return False, "moved"
    return True, ""


def wilson(k, n, z=1.96):
    """Wilson 95% 구간."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return (max(0.0, c - h), min(1.0, c + h))
