"""장면 생성, 초기화, 무작위화 적용, 채점용 정답 (계획서 부록 A).

원본 XML은 읽기만 하고, 수정한 장면을 build/scene.xml로 쓴다.
"""
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .paths import BUILD, ORIGINAL_XML

FLOORS = (1, 2, 3, 4, 5, 6)
# 패널 기준 위치 P1~P6 (x, z). x는 월드 x와 같은 방향이라 패널을 마주 보면 +x가 왼쪽
POSITIONS = {
    1: (0.07, -0.06), 2: (-0.07, -0.06),
    3: (0.07, 0.04), 4: (-0.07, 0.04),
    5: (0.07, 0.14), 6: (-0.07, 0.14),
}
DEFAULT_RADIUS = 0.035
BUTTON_Y = 0.065          # 패널 body 기준 버튼 body의 y
LABEL_OFFSET = 0.016      # 버튼 body에서 라벨 앞면까지 (법선 방향)
ARM_JOINTS = ("joint1", "joint2", "joint3", "joint4", "joint5", "joint6")
ARM_ACTUATORS = ARM_JOINTS
Q_OBSERVE = np.array([0.0, 0.0, -1.6, 0.0, 0.0, 0.0])   # 시작·대기 자세 = 관찰 자세
SETTLE_S = 0.5
DIGIT_PX = 128
DIGIT_BG = (245, 245, 240)
DIGIT_FG = (15, 15, 15)
# 전체 뷰 카메라: 휠체어 오른쪽 앞에서 팔과 패널을 함께 본다
OVERVIEW_POS = np.array([1.35, 0.35, 1.55])
OVERVIEW_TARGET = np.array([0.25, -0.50, 0.92])
OVERVIEW_FOVY = 55


def default_layout():
    """기본 숫자 배치: k층이 Pk."""
    return {n: POSITIONS[n] for n in FLOORS}


def shuffled_layout(shuffle_seed):
    """숫자 배치 섞기: perm = default_rng(seed).permutation(6), (perm[i]+1)층이 P(i+1)."""
    perm = np.random.default_rng(shuffle_seed).permutation(6)
    return {int(perm[i]) + 1: POSITIONS[i + 1] for i in range(6)}


def layout_string(layout):
    """위치 P1~P6에 놓인 층을 순서대로 적은 문자열. 비어 있는 위치는 '-'."""
    inv = {pos: n for n, pos in layout.items()}
    return "".join(str(inv[POSITIONS[i]]) if POSITIONS[i] in inv else "-" for i in range(1, 7))


def render_digit(n):
    """128x128 숫자 그림(밝은 바탕, 어두운 숫자). 글자 bbox를 그림 가운데에 맞춘다.

    인식 템플릿도 이 그림에서 만든다(부록 B 8번).
    """
    img = Image.new("RGB", (DIGIT_PX, DIGIT_PX), DIGIT_BG)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=102)
    text = str(n)
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    x = (DIGIT_PX - (r - l)) / 2 - l
    y = (DIGIT_PX - (b - t)) / 2 - t
    draw.text((x, y), text, font=font, fill=DIGIT_FG)
    return img


def _fmt(v):
    return f"{v:.6g}"


def _lookat_xyaxes(pos, target, up=(0.0, 0.0, 1.0)):
    """카메라가 target을 보도록 xyaxes(카메라 x축, y축)를 만든다. 카메라는 -z를 본다."""
    f = target - pos
    f = f / np.linalg.norm(f)
    x = np.cross(f, up)
    x = x / np.linalg.norm(x)
    y = np.cross(x, f)
    return np.concatenate([x, y])


def build_scene(layout=None, shuffle_seed=None, radius=DEFAULT_RADIUS, out_dir=BUILD):
    """원본을 읽어 수정 장면 XML과 숫자 PNG를 out_dir에 만든다. 반환: (xml 경로, 사용한 layout)."""
    if layout is not None and shuffle_seed is not None:
        raise ValueError("layout과 shuffle_seed는 함께 줄 수 없다")
    if layout is None:
        layout = shuffled_layout(shuffle_seed) if shuffle_seed is not None else default_layout()
    layout = {int(n): (float(x), float(z)) for n, (x, z) in layout.items()}
    out_dir.mkdir(parents=True, exist_ok=True)

    tree = ET.parse(ORIGINAL_XML)
    root = tree.getroot()

    # 1) 오프스크린 렌더 크기 1280x960
    visual = ET.Element("visual")
    ET.SubElement(visual, "global", offwidth="1280", offheight="960")
    root.insert(0, visual)

    # 2) link6의 시각 캡슐을 충돌하는 손목 캡슐로 교체
    link6 = root.find(".//body[@name='link6']")
    caps = [g for g in link6.findall("geom")
            if g.get("class") == "armvisual" and g.get("type") == "capsule"]
    assert len(caps) == 1, "link6 캡슐을 찾지 못함"
    cap = caps[0]
    idx = list(link6).index(cap)
    link6.remove(cap)
    link6.insert(idx, ET.Element("geom", {
        "name": "wrist_collider", "type": "capsule", "fromto": "0 0 0 0 0 .13503", "size": ".027",
        "material": "piper_gray", "contype": "1", "conaffinity": "1", "group": "2", "density": "0"}))

    # 3) 원본 버튼(button_target site 포함)을 층별 버튼으로 교체
    panel = root.find(".//body[@name='elevator_panel']")
    old = panel.find("body[@name='elevator_button_3']")
    panel.remove(old)
    half = 0.58 * radius
    for n in sorted(layout):
        x, z = layout[n]
        b = ET.SubElement(panel, "body", name=f"elevator_button_{n}", pos=f"{_fmt(x)} {_fmt(BUTTON_Y)} {_fmt(z)}")
        ET.SubElement(b, "joint", name=f"button_{n}_slide", type="slide", axis="0 -1 0", range="0 .015",
                      limited="true", stiffness="220", damping="3")
        ET.SubElement(b, "geom", name=f"button_{n}_geom", type="cylinder", size=f"{_fmt(radius)} .015",
                      quat=".7071068 .7071068 0 0", rgba=".29 .67 .98 1", mass=".025")
        ET.SubElement(b, "geom", name=f"label_{n}", type="box", size=f"{_fmt(half)} {_fmt(half)} .0004",
                      pos="0 .0156 0", quat="0 0 .7071068 .7071068", material=f"digit_{n}",
                      contype="0", conaffinity="0", mass="0")

    # 4) 숫자 텍스처와 재질
    asset = root.find("asset")
    for n in sorted(layout):
        render_digit(n).save(out_dir / f"digit_{n}.png")
        ET.SubElement(asset, "texture", name=f"digit_{n}", type="2d", file=f"digit_{n}.png")
        ET.SubElement(asset, "material", name=f"digit_{n}", texture=f"digit_{n}", specular="0", shininess="0")

    # 5) 녹화용 전체 뷰 카메라
    worldbody = root.find("worldbody")
    xy = _lookat_xyaxes(OVERVIEW_POS, OVERVIEW_TARGET)
    ET.SubElement(worldbody, "camera", name="overview", pos=" ".join(_fmt(v) for v in OVERVIEW_POS),
                  xyaxes=" ".join(_fmt(v) for v in xy), fovy=str(OVERVIEW_FOVY))

    path = out_dir / "scene.xml"
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path, layout


class Scene:
    """수정 장면 하나. reset으로 패널 위치·회전·조명을 바꾸고 팔을 관찰 자세로 둔다."""

    def __init__(self, layout=None, shuffle_seed=None, radius=DEFAULT_RADIUS, out_dir=BUILD):
        self.xml_path, self.layout = build_scene(layout, shuffle_seed, radius, out_dir)
        self.radius = radius
        self.model = mujoco.MjModel.from_xml_path(str(self.xml_path))
        self.data = mujoco.MjData(self.model)
        m = self.model
        self.floors = tuple(sorted(self.layout))
        self.panel_id = m.body("elevator_panel").id
        self.arm_qadr = np.array([m.joint(j).qposadr[0] for j in ARM_JOINTS])
        self.arm_dadr = np.array([m.joint(j).dofadr[0] for j in ARM_JOINTS])
        self.arm_act = np.array([m.actuator(a).id for a in ARM_ACTUATORS])
        self.grip_act = m.actuator("gripper").id
        self.slide_qadr = {n: m.joint(f"button_{n}_slide").qposadr[0] for n in self.floors}
        # 무작위화 전의 값을 보관한다 (reset마다 여기서 다시 계산)
        self._panel_pos0 = m.body_pos[self.panel_id].copy()
        self._panel_quat0 = m.body_quat[self.panel_id].copy()
        self._light0 = m.light_diffuse.copy()
        self._head_diffuse0 = m.vis.headlight.diffuse.copy()
        self._head_ambient0 = m.vis.headlight.ambient.copy()
        self.conditions = {}
        self._renderer = None

    # ---- 렌더러 (장면마다 하나, 다시 만들 때 close) ----
    @property
    def renderer(self):
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.model, height=960, width=1280)
        return self._renderer

    def close(self):
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None

    # ---- 초기화 ----
    def reset(self, dpos=(0.0, 0.0, 0.0), yaw_deg=0.0, light=1.0):
        """패널 이동(m)·회전(도, 월드 +z 기준 반시계 +)·조명 배율을 적용하고 관찰 자세에서 0.5초 안정화."""
        m, d = self.model, self.data
        m.body_pos[self.panel_id] = self._panel_pos0 + np.asarray(dpos, dtype=float)
        qyaw = np.zeros(4)
        mujoco.mju_axisAngle2Quat(qyaw, np.array([0.0, 0.0, 1.0]), np.radians(yaw_deg))
        q = np.zeros(4)
        mujoco.mju_mulQuat(q, qyaw, self._panel_quat0)
        m.body_quat[self.panel_id] = q
        # 조명: 광원과 headlight에 같은 배율 (패널 밝기 대부분이 headlight에서 온다)
        m.light_diffuse[:] = self._light0 * light
        m.vis.headlight.diffuse[:] = self._head_diffuse0 * light
        m.vis.headlight.ambient[:] = self._head_ambient0 * light

        mujoco.mj_resetData(m, d)
        d.qpos[self.arm_qadr] = Q_OBSERVE
        d.ctrl[self.arm_act] = Q_OBSERVE
        d.ctrl[self.grip_act] = 0.0
        mujoco.mj_forward(m, d)
        for _ in range(int(round(SETTLE_S / m.opt.timestep))):
            mujoco.mj_step(m, d)
        self.conditions = {"dpos": tuple(float(v) for v in dpos), "yaw_deg": float(yaw_deg), "light": float(light)}

    # ---- 상태 읽기 ----
    def arm_q(self):
        return self.data.qpos[self.arm_qadr].copy()

    def slides(self):
        """층별 slide 변위(m). 채점 전용."""
        return {n: float(self.data.qpos[a]) for n, a in self.slide_qadr.items()}

    def truth(self):
        """층별 라벨 중심(slide 0 기준), 법선, 현재 slide 값. 채점과 테스트 전용."""
        p = self.data.xpos[self.panel_id]
        r = self.data.xmat[self.panel_id].reshape(3, 3)
        normal = r[:, 1].copy()                     # 패널 법선 = 패널 +y
        out = {}
        for n, (x, z) in self.layout.items():
            center = p + r @ np.array([x, BUTTON_Y + LABEL_OFFSET, z])
            out[n] = {"center": center, "normal": normal,
                      "slide": float(self.data.qpos[self.slide_qadr[n]])}
        return out
