"""관절 보간 이동, 직선 이동, 누르기 (계획서 부록 C).

팔은 ctrl(목표 관절각)로만 움직인다. 목표 궤적은 기구학(IK)만으로 만들고,
보간·직선 이동은 측정 관절각이 아니라 직전에 보낸 ctrl 목표에서 시작한다.
(측정값으로 계산한 IK 증분을 바로 적분하면 손끝이 진동·발산했다: 계획서 3절)
"""
import time

import mujoco
import numpy as np

from .ik import ARM_JOINTS, IK, Q_READY

CONTROL_DT = 0.02             # 제어 주기 (시뮬레이션 10스텝)
APPROACH_DIST = 0.08          # 버튼 앞 8 cm
TOOL_TIP = 0.012              # link6 캡슐 앞끝이 ee_site보다 12 mm 앞
PRESS_DEPTH = 0.025           # 라벨 면보다 25 mm 깊이까지 명령
T_TO_APPROACH = 2.0
T_APPROACH_WAIT = 0.2
PRESS_SPEED = 0.03
T_PRESS_HOLD = 0.4
RETREAT_SPEED = 0.06
T_TO_OBSERVE = 2.0
LINE_NFEV = 8
IK_TOL = 0.001                # 접근·누름 IK 위치 오차 허용치 1 mm


def quintic(s):
    """5차 보간 계수 (시작·끝 속도·가속도 0)."""
    return 10 * s**3 - 15 * s**4 + 6 * s**5


class Controller:
    """시뮬레이션 진행과 ctrl 명령을 맡는다. q_cmd는 마지막으로 보낸 팔 목표다."""

    def __init__(self, model, data, ik=None):
        self.model = model
        self.data = data
        self.ik = ik or IK(model)
        self.act = np.array([model.actuator(a).id for a in ARM_JOINTS])
        self.qadr = np.array([model.joint(j).qposadr[0] for j in ARM_JOINTS])
        self.n_sub = int(round(CONTROL_DT / model.opt.timestep))
        self.q_cmd = data.ctrl[self.act].copy()
        self.step_hooks = []      # mj_step마다 호출: f(model, data) (채점 신호 기록)
        self.tick_hooks = []      # 제어 주기마다 호출: f(model, data) (영상 프레임 등)

    def sync(self):
        """reset 뒤에 호출: 현재 ctrl을 마지막 목표로 삼는다."""
        self.q_cmd = self.data.ctrl[self.act].copy()

    def tick(self, q_target=None):
        """목표를 ctrl로 보내고 0.02초 진행한다."""
        if q_target is not None:
            self.q_cmd = np.asarray(q_target, dtype=float).copy()
            self.data.ctrl[self.act] = self.q_cmd
        for _ in range(self.n_sub):
            mujoco.mj_step(self.model, self.data)
            for h in self.step_hooks:
                h(self.model, self.data)
        for h in self.tick_hooks:
            h(self.model, self.data)

    def hold(self, duration):
        for _ in range(int(round(duration / CONTROL_DT))):
            self.tick()

    def move_joint(self, q_goal, duration):
        """직전 ctrl 목표에서 q_goal까지 관절 공간 5차 보간."""
        q0 = self.q_cmd.copy()
        q_goal = np.asarray(q_goal, dtype=float)
        n = max(1, int(round(duration / CONTROL_DT)))
        for k in range(1, n + 1):
            self.tick(q0 + (q_goal - q0) * quintic(k / n))

    def move_line(self, p_from, p_to, z_des, speed):
        """ee_site를 p_from → p_to 직선으로 옮긴다. 주기마다 직전 해에서 IK(max_nfev 8)."""
        p_from = np.asarray(p_from, dtype=float)
        p_to = np.asarray(p_to, dtype=float)
        n = max(1, int(np.ceil(np.linalg.norm(p_to - p_from) / speed / CONTROL_DT)))
        q = self.q_cmd.copy()
        for k in range(1, n + 1):
            q, _, _ = self.ik.solve(p_from + (p_to - p_from) * k / n, z_des, q, max_nfev=LINE_NFEV)
            self.tick(q)

    # ---- 누르기 ----
    def plan_press(self, center, normal):
        """움직이기 전에 접근·누름 IK를 푼다. center = 라벨 중심, normal = 패널 법선(바깥)."""
        c = np.asarray(center, dtype=float)
        n = np.asarray(normal, dtype=float)
        n = n / np.linalg.norm(n)
        z_des = -n
        p_app = c + (APPROACH_DIST + TOOL_TIP) * n
        p_press = c + (TOOL_TIP - PRESS_DEPTH) * n
        t0 = time.perf_counter()
        q_app, e_app, _ = self.ik.solve(p_app, z_des, Q_READY)
        t_ik_ms = (time.perf_counter() - t0) * 1000
        q_press, e_press, tilt = self.ik.solve(p_press, z_des, q_app)
        return {
            "ok": e_app <= IK_TOL and e_press <= IK_TOL,
            "q_app": q_app, "q_press": q_press, "p_app": p_app, "p_press": p_press, "z_des": z_des,
            "err_app": e_app, "err_press": e_press, "tilt_deg": tilt, "t_ik_ms": t_ik_ms,
        }

    def execute_press(self, plan, q_home):
        """계획대로 접근 → 직선 누름 → 유지 → 후퇴 → 대기 자세."""
        self.move_joint(plan["q_app"], T_TO_APPROACH)
        self.hold(T_APPROACH_WAIT)
        self.move_line(plan["p_app"], plan["p_press"], plan["z_des"], PRESS_SPEED)
        self.hold(T_PRESS_HOLD)
        self.move_line(plan["p_press"], plan["p_app"], plan["z_des"], RETREAT_SPEED)
        self.move_joint(q_home, T_TO_OBSERVE)

    def press(self, center, normal, q_home):
        """IK가 하나라도 1 mm를 넘으면 움직이지 않고 계획만 돌려준다."""
        plan = self.plan_press(center, normal)
        if plan["ok"]:
            self.execute_press(plan, q_home)
        return plan
