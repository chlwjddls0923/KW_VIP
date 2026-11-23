"""원본 모델이 계획서 3절의 구조 사실과 맞는지 확인한다.

(a)(b)는 계획서 단계 0의 통과 기준이다. 나머지는 3절의 모델 구조 항목
(크기, 범위, 위치, 충돌, 도구 축)을 같은 방식으로 확인한다.
"""
import itertools

import mujoco
import numpy as np
import pytest

from assist.paths import ORIGINAL_XML

ARM_JOINT_RANGES = {
    "joint1": (-2.618, 2.618),
    "joint2": (0.0, 3.14),
    "joint3": (-2.697, 0.0),
    "joint4": (-1.832, 1.832),
    "joint5": (-1.22, 1.22),
    "joint6": (-3.14, 3.14),
}


@pytest.fixture(scope="module")
def md():
    model = mujoco.MjModel.from_xml_path(str(ORIGINAL_XML))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


def _in_arm(model, body_id):
    """body가 base_link 아래(팔)에 있는지."""
    root = model.body("base_link").id
    while body_id != 0:
        if body_id == root:
            return True
        body_id = model.body_parentid[body_id]
    return False


def _box_extent_along(data, model, geom_id, origin, axis):
    """box geom의 꼭짓점 8개를 axis에 투영한 최댓값(origin 기준)."""
    c = data.geom_xpos[geom_id]
    r = data.geom_xmat[geom_id].reshape(3, 3)
    h = model.geom_size[geom_id]
    vals = [axis @ (c + r @ (np.array(s) * h) - origin) for s in itertools.product((-1, 1), repeat=3)]
    return max(vals)


# (a) 원본에서 충돌하는 팔 geom은 finger_pad 2개뿐이다
def test_a_arm_colliders_are_only_finger_pads(md):
    model, _ = md
    names = sorted(
        model.geom(i).name
        for i in range(model.ngeom)
        if _in_arm(model, model.geom_bodyid[i]) and (model.geom_contype[i] or model.geom_conaffinity[i])
    )
    assert names == ["finger_pad_left", "finger_pad_right"]


# (b) button_target은 버튼 앞면보다 0.025 m 앞이다
def test_b_button_target_25mm_in_front_of_button_face(md):
    model, data = md
    g = model.geom("button_3_geom").id
    axis = data.geom_xmat[g].reshape(3, 3)[:, 2]          # 원기둥 축(월드)
    normal = np.array([0.0, 1.0, 0.0])                     # 패널 법선 +y
    assert abs(abs(axis @ normal) - 1.0) < 1e-9
    face = data.geom_xpos[g] + normal * model.geom_size[g][1]   # 앞면 중심
    target = data.site_xpos[model.site("button_target").id]
    np.testing.assert_allclose(face[1], -0.79, atol=1e-9)
    np.testing.assert_allclose(target - face, normal * 0.025, atol=1e-9)


def test_model_size(md):
    model, _ = md
    assert (model.nq, model.nv, model.nu) == (16, 15, 7)
    assert model.opt.timestep == pytest.approx(0.002)
    # 위치 제어 액추에이터: bias가 affine(-kp*q - kv*qdot)인 position 액추에이터
    for i in range(model.nu):
        assert model.actuator_biastype[i] == mujoco.mjtBias.mjBIAS_AFFINE
        assert model.actuator_trntype[i] == mujoco.mjtTrn.mjTRN_JOINT


def test_arm_joint_ranges(md):
    model, _ = md
    for name, (lo, hi) in ARM_JOINT_RANGES.items():
        np.testing.assert_allclose(model.joint(name).range, [lo, hi], atol=1e-9)


def test_button_and_panel(md):
    model, data = md
    np.testing.assert_allclose(data.xpos[model.body("elevator_button_3").id], [0.43, -0.805, 0.99], atol=1e-9)
    np.testing.assert_allclose(data.xpos[model.body("elevator_panel").id], [0.43, -0.87, 0.99], atol=1e-9)
    assert model.geom("button_3_geom").size[0] == pytest.approx(0.045)
    j = model.joint("button_3_slide")
    np.testing.assert_allclose(j.axis, [0, -1, 0])
    np.testing.assert_allclose(j.range, [0, 0.015])
    assert model.jnt_stiffness[j.id] == pytest.approx(220)


def test_tool_axis_and_collision_offsets(md):
    model, data = md
    ee = model.site("ee_site").id
    pe = data.site_xpos[ee]
    z = data.site_xmat[ee].reshape(3, 3)[:, 2]       # 도구 축 = ee_site z

    # link6 캡슐 앞끝은 ee_site보다 12 mm 앞이다 (fromto 방향과 geom z축이 반대일 수 있어 양 끝을 본다)
    l6 = model.body("link6").id
    caps = [i for i in range(model.ngeom)
            if model.geom_bodyid[i] == l6 and model.geom_type[i] == mujoco.mjtGeom.mjGEOM_CAPSULE]
    assert len(caps) == 1
    c = data.geom_xpos[caps[0]]
    gz = data.geom_xmat[caps[0]].reshape(3, 3)[:, 2]
    rad, half = model.geom_size[caps[0]][:2]
    tip = max(z @ (c + s * gz * (half + rad) - pe) for s in (-1, 1))
    assert tip == pytest.approx(0.012, abs=5e-4)

    # finger_pad 앞면은 ee_site보다 약 5.6 cm 뒤다. 그리퍼(=ee_site z)는 패드 쪽에서 앞으로 향한다
    for name in ("finger_pad_left", "finger_pad_right"):
        front = _box_extent_along(data, model, model.geom(name).id, pe, z)
        assert front == pytest.approx(-0.056, abs=1e-3)
