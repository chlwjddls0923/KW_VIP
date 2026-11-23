"""단계 2 통과 기준: IK와 누르기. 제어만 검증하므로 목표 좌표는 truth()에서 가져온다(채점·시험 전용)."""
import mujoco
import numpy as np
import pytest

from assist.ik import IK, Q_READY
from assist.motion import Controller
from assist.paths import ORIGINAL_XML
from assist.scene import FLOORS, Q_OBSERVE, SETTLE_S, Scene

ARM_LINKS = ("link2", "link3", "link4", "link5", "link6", "link7", "link8")


@pytest.fixture(scope="module")
def scene():
    s = Scene()
    yield s
    s.close()


def _variation(seed):
    """변화 범위: 패널 x·z ±10 cm, y ±5 cm, 회전 ±10°."""
    rng = np.random.default_rng(seed)
    dx = rng.uniform(-0.10, 0.10)
    dy = rng.uniform(-0.05, 0.05)
    dz = rng.uniform(-0.10, 0.10)
    yaw = rng.uniform(-10.0, 10.0)
    return (dx, dy, dz), yaw


def test_ik_variation_100_layouts(scene):
    """시드 8001~8100 × 버튼 6개: 접근·누름 자세 위치 오차 모두 < 1 mm."""
    ctl = Controller(scene.model, scene.data)
    errs, tilts, times, bad = [], [], [], []
    for seed in range(8001, 8101):
        dpos, yaw = _variation(seed)
        scene.reset(dpos, yaw)
        for n, t in scene.truth().items():
            plan = ctl.plan_press(t["center"], t["normal"])
            errs += [plan["err_app"], plan["err_press"]]
            tilts.append(plan["tilt_deg"])
            times.append(plan["t_ik_ms"])
            if not plan["ok"]:
                bad.append((seed, n, plan["err_app"], plan["err_press"]))
    errs = np.array(errs) * 1000
    print(f"\nIK {len(tilts)} buttons: pos err median {np.median(errs):.4f} mm, max {errs.max():.4f} mm; "
          f"tilt median {np.median(tilts):.1f} deg, max {np.max(tilts):.1f} deg; "
          f"approach IK {np.min(times):.1f}~{np.max(times):.1f} ms (median {np.median(times):.1f})")
    assert not bad, bad[:5]


def _env_geoms(model, exclude_body):
    """팔(base_link 아래)이 아닌 geom. 목표 버튼 body의 geom은 뺀다."""
    root = model.body("base_link").id
    out = []
    for g in range(model.ngeom):
        b = model.geom_bodyid[g]
        if b == exclude_body:
            continue
        x = b
        while x not in (0, root):
            x = model.body_parentid[x]
        if x != root:
            out.append(g)
    return out


def _geom_label(model, g):
    name = model.geom(g).name
    if name:
        return name
    return f"{model.body(model.geom_bodyid[g]).name}#geom{g}"


def test_press_20(scene):
    """시드 6001~6020, 패널 ±3 cm, 층 무작위: 목표 ≥ 10 mm, 다른 버튼 < 1 mm, 팔 링크-환경 최소 거리 > 0."""
    m, d = scene.model, scene.data
    ctl = Controller(m, d)
    arm_geoms = [g for g in range(m.ngeom) if m.body(m.geom_bodyid[g]).name in ARM_LINKS]
    has_dist = hasattr(mujoco, "mj_geomDistance")
    fromto = np.zeros(6)
    rows, fails = [], []
    min_by_env = {}

    for seed in range(6001, 6021):
        rng = np.random.default_rng(seed)
        dpos = rng.uniform(-0.03, 0.03, size=3)
        floor = int(rng.integers(1, 7))
        scene.reset(dpos)
        ctl.sync()
        target_body = m.body(f"elevator_button_{floor}").id
        env = _env_geoms(m, target_body)
        peak = {n: 0.0 for n in FLOORS}

        def on_step(_m, _d):
            for n, v in scene.slides().items():
                if v > peak[n]:
                    peak[n] = v

        def on_tick(_m, _d):
            for e in env:
                for a in arm_geoms:
                    dist = mujoco.mj_geomDistance(m, d, a, e, 0.2, fromto)
                    if dist < min_by_env.get(e, (np.inf,))[0]:
                        min_by_env[e] = (dist, seed, _geom_label(m, a))

        ctl.step_hooks = [on_step]
        ctl.tick_hooks = [on_tick] if has_dist else []
        t = scene.truth()[floor]
        plan = ctl.press(t["center"], t["normal"], Q_OBSERVE)
        other = max(v for n, v in peak.items() if n != floor)
        ok = plan["ok"] and peak[floor] >= 0.010 and other < 0.001
        rows.append((seed, floor, peak[floor] * 1000, other * 1000, plan["tilt_deg"]))
        if not ok:
            fails.append(rows[-1])

    print("\nseed floor target_mm other_mm tilt_deg")
    for r in rows:
        print(f"{r[0]} {r[1]} {r[2]:.2f} {r[3]:.3f} {r[4]:.1f}")
    print(f"press success {20 - len(fails)}/20")
    if has_dist:
        worst = sorted(min_by_env.items(), key=lambda kv: kv[1][0])[:8]
        print("closest env geoms (dist mm, seed, arm geom):")
        for e, (dist, seed, a) in worst:
            print(f"  {_geom_label(m, e)}: {dist * 1000:.1f} mm (seed {seed}, {a})")
        for e, (dist, seed, a) in min_by_env.items():
            if _geom_label(m, e) in ("right_armrest", "left_armrest", "backrest", "arm_mount_plate", "seat"):
                print(f"  {_geom_label(m, e)}: {dist * 1000:.1f} mm (seed {seed}, {a})")
        overall = min(v[0] for v in min_by_env.values())
        assert overall > 0.0, f"arm link touched environment: {overall}"
    else:
        print("mj_geomDistance 없음: 거리 시험 생략")
    assert not fails, fails


def test_original_button_target_gives_zero_press():
    """원본 XML에서 ee_site를 button_target으로 보내고(z_des=(0,-1,0)) 1초 유지 → button_3_slide < 0.5 mm."""
    m = mujoco.MjModel.from_xml_path(str(ORIGINAL_XML))
    d = mujoco.MjData(m)
    ctl = Controller(m, d, IK(m))
    d.qpos[ctl.qadr] = Q_OBSERVE
    d.ctrl[ctl.act] = Q_OBSERVE
    mujoco.mj_forward(m, d)
    for _ in range(int(round(SETTLE_S / m.opt.timestep))):
        mujoco.mj_step(m, d)
    ctl.sync()
    target = d.site_xpos[m.site("button_target").id].copy()
    q, err, tilt = ctl.ik.solve(target, [0.0, -1.0, 0.0], Q_READY)
    assert err < 0.001
    slide_adr = m.joint("button_3_slide").qposadr[0]
    peak = [0.0]
    ctl.step_hooks = [lambda _m, _d: peak.__setitem__(0, max(peak[0], d.qpos[slide_adr]))]
    ctl.move_joint(q, 2.0)
    ctl.hold(1.0)
    ee = d.site_xpos[m.site("ee_site").id]
    print(f"\noriginal: IK err {err * 1000:.3f} mm, tilt {tilt:.1f} deg, ee-target {np.linalg.norm(ee - target) * 1000:.2f} mm, "
          f"button_3_slide max {peak[0] * 1000:.3f} mm")
    assert peak[0] < 0.0005
