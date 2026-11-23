"""관절 한계를 bounds로 넣은 최소자승 IK (계획서 부록 C).

위치를 우선하고(1 mm가 잔차 0.1), 도구 방향(ee_site z축)은 약하게, 시작 자세 근처 유지는 더 약하게 건다.
방향을 강하게 맞추면 joint5가 한계에 걸려 위치가 수 cm 어긋나므로 방향은 '되는 만큼'만 맞춘다.
"""
import mujoco
import numpy as np
from scipy.optimize import least_squares

ARM_JOINTS = ("joint1", "joint2", "joint3", "joint4", "joint5", "joint6")
Q_READY = np.array([-0.318, 2.018, -1.166, -1.783, 1.073, 0.0])   # 접근 자세 IK의 시작점
W_POS = 100.0      # 위치 잔차 가중치: 1 mm → 0.1
W_DIR = 0.05       # 방향 잔차 가중치
W_REG = 0.002      # 시작 자세 유지
BOUND_MARGIN = 0.03


def _skew(v):
    return np.array([[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]])


class IK:
    """기구학 전용 MjData를 따로 두고 ee_site의 위치·z축을 맞춘다. 시뮬레이션 상태는 건드리지 않는다."""

    def __init__(self, model, site="ee_site"):
        self.model = model
        self.data = mujoco.MjData(model)          # FK 전용 (시뮬레이션 data와 분리)
        self.site = model.site(site).id
        self.qadr = np.array([model.joint(j).qposadr[0] for j in ARM_JOINTS])
        self.dadr = np.array([model.joint(j).dofadr[0] for j in ARM_JOINTS])
        rng = np.array([model.joint(j).range for j in ARM_JOINTS])
        self.lo = rng[:, 0] + BOUND_MARGIN
        self.hi = rng[:, 1] - BOUND_MARGIN
        self._jacp = np.zeros((3, model.nv))
        self._jacr = np.zeros((3, model.nv))

    def fk(self, q):
        """관절 6개 → (ee_site 위치, ee_site z축)."""
        d = self.data
        d.qpos[self.qadr] = q
        mujoco.mj_kinematics(self.model, d)
        mujoco.mj_comPos(self.model, d)            # mj_jacSite에 필요한 cdof 계산
        return d.site_xpos[self.site].copy(), d.site_xmat[self.site].reshape(3, 3)[:, 2].copy()

    def _jac_site(self, q):
        self.fk(q)
        mujoco.mj_jacSite(self.model, self.data, self._jacp, self._jacr, self.site)
        return self._jacp[:, self.dadr], self._jacr[:, self.dadr]

    def solve(self, p_des, z_des, q_seed, max_nfev=200):
        """반환: (q, 위치 오차[m], 방향 오차[도])."""
        p_des = np.asarray(p_des, dtype=float)
        z_des = np.asarray(z_des, dtype=float)
        z_des = z_des / np.linalg.norm(z_des)
        q_seed = np.clip(np.asarray(q_seed, dtype=float), self.lo + 1e-9, self.hi - 1e-9)

        def residual(q):
            p, z = self.fk(q)
            return np.concatenate([(p - p_des) * W_POS, W_DIR * (z - z_des), W_REG * (q - q_seed)])

        def jac(q):
            jp, jr = self._jac_site(q)
            z = self.data.site_xmat[self.site].reshape(3, 3)[:, 2]
            # dz/dq = ω × z = -[z]x · jacr
            return np.vstack([jp * W_POS, W_DIR * (-_skew(z) @ jr), W_REG * np.eye(6)])

        sol = least_squares(residual, q_seed, jac=jac, bounds=(self.lo, self.hi), max_nfev=max_nfev)
        q = sol.x
        p, z = self.fk(q)
        pos_err = float(np.linalg.norm(p - p_des))
        dir_err = float(np.degrees(np.arccos(np.clip(z @ z_des, -1.0, 1.0))))
        return q, pos_err, dir_err
