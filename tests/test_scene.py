"""단계 1 통과 기준: 장면 생성기."""
import mujoco
import numpy as np
import pytest
from PIL import Image

from assist.paths import OUT
from assist.scene import FLOORS, POSITIONS, Q_OBSERVE, Scene, layout_string, shuffled_layout


@pytest.fixture(scope="module")
def scene():
    s = Scene()
    s.reset()
    yield s
    s.close()


def test_loads_with_six_slides(scene):
    m = scene.model
    for n in FLOORS:
        assert m.joint(f"button_{n}_slide").type == mujoco.mjtJoint.mjJNT_SLIDE
    # 원본의 button_target site는 없어야 한다
    assert mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SITE, "button_target") == -1
    # 손목 캡슐이 충돌하도록 바뀌었다
    g = m.geom("wrist_collider")
    assert g.contype[0] == 1 and g.conaffinity[0] == 1
    assert m.camera("overview").id >= 0
    assert (m.vis.global_.offwidth, m.vis.global_.offheight) == (1280, 960)


def test_head_image_saved(scene):
    """관찰 자세에서 head_rgb 1280x960을 사람이 볼 용도로 저장한다."""
    np.testing.assert_allclose(scene.arm_q(), Q_OBSERVE, atol=0.01)
    r = scene.renderer
    r.update_scene(scene.data, camera="head_rgb")
    rgb = r.render().copy()
    assert rgb.shape == (960, 1280, 3)
    OUT.mkdir(exist_ok=True)
    Image.fromarray(rgb).save(OUT / "scene_head.png")
    r.update_scene(scene.data, camera="overview")
    Image.fromarray(r.render().copy()).save(OUT / "scene_overview.png")


def test_idle_hold_1p2s(scene):
    """명령 없이 1.2초: 모든 버튼 slide < 0.5 mm, 팔 관절 변화 < 0.01 rad."""
    scene.reset()
    q0 = scene.arm_q()
    max_slide = 0.0
    max_dq = 0.0
    for _ in range(int(round(1.2 / scene.model.opt.timestep))):
        mujoco.mj_step(scene.model, scene.data)
        max_slide = max(max_slide, max(abs(v) for v in scene.slides().values()))
        max_dq = max(max_dq, float(np.max(np.abs(scene.arm_q() - q0))))
    print(f"idle 1.2s: max slide {max_slide * 1000:.3e} mm, max joint change {max_dq:.3e} rad")
    assert max_slide < 0.0005
    assert max_dq < 0.01


def test_truth_at_reference(scene):
    """기준 위치에서 라벨 중심 = 패널 + (x, 0.081, z), 법선 +y."""
    scene.reset()
    t = scene.truth()
    for n in FLOORS:
        x, z = POSITIONS[n]
        np.testing.assert_allclose(t[n]["center"], [0.43 + x, -0.87 + 0.081, 0.99 + z], atol=1e-6)
        np.testing.assert_allclose(t[n]["normal"], [0, 1, 0], atol=1e-9)


def test_reset_moves_and_rotates_panel(scene):
    """패널 이동·회전이 truth에 반영된다. +회전은 위에서 보아 반시계."""
    scene.reset(dpos=(0.05, -0.02, 0.03), yaw_deg=10.0, light=0.7)
    t = scene.truth()
    yaw = np.radians(10.0)
    np.testing.assert_allclose(t[3]["normal"], [-np.sin(yaw), np.cos(yaw), 0], atol=1e-9)
    p = np.array([0.43 + 0.05, -0.87 - 0.02, 0.99 + 0.03])
    x, z = POSITIONS[3]
    rz = np.array([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
    np.testing.assert_allclose(t[3]["center"], p + rz @ [x, 0.081, z], atol=1e-6)
    np.testing.assert_allclose(scene.model.vis.headlight.diffuse, [0.28] * 3, atol=1e-6)
    scene.reset()
    np.testing.assert_allclose(scene.model.vis.headlight.diffuse, [0.4] * 3, atol=1e-6)


def test_layouts(tmp_path):
    """숫자 배치 섞기와 버튼 1개 장면."""
    lay = shuffled_layout(7001)
    perm = np.random.default_rng(7001).permutation(6)
    assert layout_string(lay) == "".join(str(p + 1) for p in perm)
    one = Scene(layout={3: (0.0, 0.0)}, radius=0.045, out_dir=tmp_path)
    one.reset()
    assert one.floors == (3,)
    np.testing.assert_allclose(one.truth()[3]["center"], [0.43, -0.789, 0.99], atol=1e-6)
    assert one.model.geom("button_3_geom").size[0] == pytest.approx(0.045)
    one.close()
