"""명령 → 판단 → 동작 → 결과.

흐름: 관찰 자세 → parse → (PRESS 아니면 멈춤) → 촬영·인식 → ground → (층 없으면 멈춤)
      → 접근·누름 IK 미리 풀기 → (1 mm 넘으면 멈춤) → 누르기 → 결과 출력 → 대기 자세.
판단과 동작에는 시뮬레이터 정답을 쓰지 않는다. 결과 메시지의 버튼 변위(slide)는 시뮬레이터의
버튼 신호이고 재시도 판단에는 쓰지 않는다(재시도 없음). slide·관절 변화 기록은 채점용이다.
"""
import time

import numpy as np

from . import nlu
from .camera import capture
from .motion import Controller
from .perception import detect, make_templates
from .scene import POSITIONS, Q_OBSERVE, BUTTON_Y, LABEL_OFFSET

STILL_HOLD_S = 1.0            # 움직이지 않는 판단 뒤에도 1초 진행해 정지 상태를 기록한다
# 고정 좌표 기준선: 기준 위치 패널 원점과 법선 (설계 상수, 시행별 정답이 아님)
BASELINE_PANEL = np.array([0.43, -0.87, 0.99])
BASELINE_NORMAL = np.array([0.0, 1.0, 0.0])


class Assistant:
    """장면 하나에 붙어 명령을 처리한다. mode: 'full' 또는 'baseline_fixed'."""

    def __init__(self, scene, mode="full", say=print):
        self.scene = scene
        self.mode = mode
        self.say = say
        self.ctl = Controller(scene.model, scene.data)
        self.templates = make_templates(scene.floors)   # 패널에 쓰인 숫자(설계 정보)
        nlu.get_kiwi()

    def _monitor(self):
        """채점·결과 출력용 신호 기록기: 버튼별 slide 최댓값, 처음 10 mm에 닿은 시각, 팔 관절 최대 변화."""
        sc, d = self.scene, self.scene.data
        rec = {"max_slide": {n: 0.0 for n in sc.floors}, "t_first_10mm": {}, "max_joint_motion": 0.0}
        q0 = sc.arm_q()
        t0 = d.time

        def on_step(_m, _d):
            for n, v in sc.slides().items():
                if v > rec["max_slide"][n]:
                    rec["max_slide"][n] = v
                if v >= 0.010 and n not in rec["t_first_10mm"]:
                    rec["t_first_10mm"][n] = d.time - t0
            dq = float(np.max(np.abs(sc.arm_q() - q0)))
            if dq > rec["max_joint_motion"]:
                rec["max_joint_motion"] = dq
        return rec, on_step, t0

    def _finish_still(self, out, message):
        self.say(message)
        out["messages"].append(message)
        self.ctl.hold(STILL_HOLD_S)
        return out

    def run(self, text):
        sc, d = self.scene, self.scene.data
        self.ctl.sync()
        rec, on_step, t0 = self._monitor()
        self.ctl.step_hooks = [on_step]
        out = rec
        out.update(text=text, mode=self.mode, messages=[], action=None, floor=None, parsed_intent=None,
                   parsed_floor=None, seen_floors=[], plan_ok=None, tilt_deg=None, t_parse_ms=None,
                   t_perception_ms=None, t_ik_ms=None, t_task=None, detections=[])

        # 1) 명령 해석
        t = time.perf_counter()
        parsed = nlu.parse(text)
        out["t_parse_ms"] = (time.perf_counter() - t) * 1000
        out["parsed_intent"], out["parsed_floor"] = parsed["intent"], parsed["floor"]
        out["parsed"] = {k: parsed[k] for k in ("scores", "events", "candidates")}
        if parsed["intent"] != "PRESS":
            out["action"] = parsed["intent"]
            msg = {"WAIT": "대기합니다", "CLARIFY": "몇 층 버튼을 누를까요?", "REJECT": "지원하지 않는 명령입니다"}
            return self._finish_still(out, msg[parsed["intent"]])

        # 2) 촬영과 인식 (기준선은 건너뛰고 고정 좌표 사용)
        if self.mode == "baseline_fixed":
            targets = {n: (BASELINE_PANEL + np.array([x, BUTTON_Y + LABEL_OFFSET, z]), BASELINE_NORMAL)
                       for n, (x, z) in POSITIONS.items()}
        else:
            t = time.perf_counter()
            frame = capture(sc.renderer, sc.model, d)
            dets = detect(frame, self.templates)
            out["t_perception_ms"] = (time.perf_counter() - t) * 1000
            targets = {r["floor"]: (r["center"], r["normal"]) for r in dets}
            out["detections"] = [{"floor": r["floor"], "score": r["score"], "margin": r["margin"],
                                  "center": r["center"].tolist()} for r in dets]
        out["seen_floors"] = sorted(targets)

        # 3) 층 확인
        g = nlu.ground(parsed, out["seen_floors"])
        out["action"], out["floor"] = g["action"], g["floor"]
        if g["action"] != "PRESS":
            return self._finish_still(out, f"{g['floor']}층 버튼이 보이지 않아 수행할 수 없습니다")
        n = g["floor"]
        center, normal = targets[n]

        # 4) 접근·누름 IK를 미리 푼다
        plan = self.ctl.plan_press(center, normal)
        out["plan_ok"], out["tilt_deg"], out["t_ik_ms"] = plan["ok"], plan["tilt_deg"], plan["t_ik_ms"]
        out["ik_err_mm"] = (plan["err_app"] * 1000, plan["err_press"] * 1000)
        if not plan["ok"]:
            out["action"] = "REJECT"
            return self._finish_still(out, f"{n}층 버튼에 팔이 닿지 않아 수행할 수 없습니다")

        # 5) 누르기 → 결과 → 대기 자세
        msg = f"{n}층 버튼을 누릅니다"
        self.say(msg)
        out["messages"].append(msg)
        self.ctl.execute_press(plan, Q_OBSERVE)
        out["t_task"] = d.time - t0
        peak = out["max_slide"][n] * 1000 if n in out["max_slide"] else 0.0
        msg = (f"{n}층 버튼 눌림 확인 ({peak:.1f} mm)" if peak >= 10.0
               else f"{n}층 버튼이 눌리지 않았습니다 ({peak:.1f} mm)")
        self.say(msg)
        out["messages"].append(msg)
        return out


# ---- 시행 실행 (테스트·평가 공용) ----
CSV_COLUMNS = ("trial_id", "set", "seed", "text", "expected_action", "expected_floor", "parsed_intent",
               "parsed_floor", "seen_floors", "action", "success", "failure_type", "max_slide_target_mm",
               "max_slide_other_mm", "t_press_s", "t_task_s", "t_parse_ms", "t_perception_ms", "t_ik_ms",
               "tilt_deg", "panel_dx", "panel_dy", "panel_dz", "yaw_deg", "light", "layout", "target_z",
               "max_joint_motion_rad")


class SceneCache:
    """숫자 배치가 같은 시행끼리 장면을 재사용한다. 장면을 바꿀 때 이전 렌더러를 닫는다."""

    def __init__(self, mode="full", say=lambda m: None):
        self.mode, self.say = mode, say
        self.key = None
        self.scene = None
        self.assistant = None

    def get(self, trial):
        from .scene import Scene
        if trial.layout_str != self.key:
            self.close()
            self.scene = Scene(layout=trial.layout)
            self.assistant = Assistant(self.scene, mode=self.mode, say=self.say)
            self.key = trial.layout_str
        return self.scene, self.assistant

    def close(self):
        if self.scene is not None:
            self.scene.close()
        self.scene = self.assistant = self.key = None


def _fmt(v, nd=3):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def run_trial(trial, cache):
    """조건대로 reset → 명령 실행 → 판정. 반환: (trials.csv 한 줄 dict, 원 기록)."""
    import traceback

    from .protocol import judge

    scene, assistant = cache.get(trial)
    scene.reset(trial.dpos, trial.yaw_deg, trial.light)
    truth = scene.truth()
    try:
        rec = assistant.run(trial.text)
    except Exception:                                   # 실패를 빼지 않고 '실행 예외'로 남긴다
        rec = {"exception": traceback.format_exc(), "max_slide": scene.slides(), "t_first_10mm": {},
               "max_joint_motion": float("nan"), "parsed_intent": None, "parsed_floor": None,
               "seen_floors": [], "action": "EXCEPTION", "plan_ok": None}
    ok, ftype = judge(trial, rec)
    n = trial.expected_floor
    slides = rec["max_slide"]
    if trial.expected_action == "PRESS":
        tgt = slides.get(n, 0.0) * 1000
        other = max((v for k, v in slides.items() if k != n), default=0.0) * 1000
    else:
        tgt = None
        other = max(slides.values()) * 1000
    t_press = rec["t_first_10mm"].get(n) if n is not None else None
    row = {
        "trial_id": trial.trial_id, "set": trial.set, "seed": trial.seed, "text": trial.text,
        "expected_action": trial.expected_action, "expected_floor": n,
        "parsed_intent": rec.get("parsed_intent"), "parsed_floor": rec.get("parsed_floor"),
        "seen_floors": "".join(str(f) for f in rec.get("seen_floors", [])),
        "action": rec.get("action"), "success": int(ok), "failure_type": ftype,
        "max_slide_target_mm": tgt, "max_slide_other_mm": other,
        "t_press_s": t_press, "t_task_s": rec.get("t_task"),
        "t_parse_ms": rec.get("t_parse_ms"), "t_perception_ms": rec.get("t_perception_ms"),
        "t_ik_ms": rec.get("t_ik_ms"), "tilt_deg": rec.get("tilt_deg"),
        "panel_dx": trial.dpos[0], "panel_dy": trial.dpos[1], "panel_dz": trial.dpos[2],
        "yaw_deg": trial.yaw_deg, "light": trial.light, "layout": trial.layout_str,
        "target_z": float(truth[n]["center"][2]) if n in truth else None,
        "max_joint_motion_rad": rec.get("max_joint_motion"),
    }
    return {k: _fmt(row[k], 4 if k.startswith("panel") else 3) for k in CSV_COLUMNS}, rec
