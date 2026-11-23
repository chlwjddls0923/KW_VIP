"""영상 저장: 전체 뷰(overview)와 head 카메라(검출 결과 표시)를 나란히 두고 글자를 넣는다.

판단·동작 코드(pipeline·perception·nlu)는 고치지 않는다. Assistant의 say 콜백, 제어 주기 콜백(tick_hooks),
그리고 녹화하는 동안만 pipeline 모듈의 detect·parse를 감싸 판단 결과를 화면에 옮긴다.
렌더링은 물리 상태를 바꾸지 않으므로 같은 시드·조건이면 평가 시행과 같은 결과가 나온다.
글자는 영문이다(한글 글꼴 파일이 프로젝트 폴더 밖에 있어 쓰지 않는다).
"""
import re

import imageio.v2 as imageio
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import pipeline as P
from .camera import Frame

VW, VH = 640, 480           # 카메라 한 칸 크기
BAND = 152                  # 아래 글자 영역 높이
FPS = 25
TICKS_PER_FRAME = 2         # 제어 주기 0.02 s × 2 = 0.04 s
PRE_S, POST_S = 1.0, 1.0
INSET_W, INSET_H = 300, 240     # 확대 화면 크기(1280x960 원본 픽셀)    # 앞뒤 정지 화면 (물리 진행 없이 같은 프레임을 반복)

# 문장 틀·점검 문장의 영문 풀이 (영상 글자용)
GLOSS = [
    (r"^(\d+)층 버튼을 눌러줘$", "Press the floor {0} button"),
    (r"^엘리베이터 (\d+)층을 선택해 줘$", "Select floor {0} on the elevator"),
    (r"^(\d+)층으로 가자$", "Let's go to floor {0}"),
    (r"^(\d+)층 좀 눌러 줄래\?$", "Could you press floor {0}?"),
    (r"^(\d+)층 가고 싶어$", "I want to go to floor {0}"),
    (r"^버튼은 누르지 말고 대기해$", "Don't press the button, just wait"),
    (r"^(\d+)층 누르지 마$", "Don't press floor {0}"),
    (r"^현재 장면에 없는 (\d+)층 버튼을 눌러줘$", "Press the floor {0} button that is not in the scene"),
    (r"^(\d+)층 눌러줘$", "Press floor {0}"),
]
MSG_EN = [
    (r"^(\d+)층 버튼을 누릅니다$", "Pressing the floor {0} button"),
    (r"^(\d+)층 버튼 눌림 확인 \(([\d.]+) mm\)$", "Floor {0} button pressed ({1} mm)"),
    (r"^(\d+)층 버튼이 눌리지 않았습니다 \(([\d.]+) mm\)$", "Floor {0} button NOT pressed ({1} mm)"),
    (r"^대기합니다$", "Waiting (no motion)"),
    (r"^(-?\d+)층 버튼이 보이지 않아 수행할 수 없습니다$", "Floor {0} button not visible - cannot do it (no motion)"),
    (r"^(\d+)층 버튼에 팔이 닿지 않아 수행할 수 없습니다$", "Floor {0} button out of reach - cannot do it (no motion)"),
    (r"^몇 층 버튼을 누를까요\?$", "Which floor should I press? (no motion)"),
    (r"^지원하지 않는 명령입니다$", "Unsupported command (no motion)"),
]


def _translate(text, table, default):
    for pat, out in table:
        m = re.match(pat, text)
        if m:
            return out.format(*m.groups())
    return default


def gloss(text):
    return _translate(text, GLOSS, "(Korean command - see docs)")


class Recorder:
    """Assistant 하나에 붙어 run 한 번을 mp4로 저장한다."""

    def __init__(self, assistant, header, note=""):
        self.a = assistant
        self.sc = assistant.scene
        self.header = header
        self.note = note
        self.r = mujoco.Renderer(self.sc.model, height=VH, width=VW)
        self.font = ImageFont.load_default(size=17)
        self.font_small = ImageFont.load_default(size=14)
        self.frames = []
        self.state = {"text": "", "parse": "", "action": "", "msg": "", "dets": [], "t0": 0.0, "target": None}
        self._tick = 0

    # ---- 판단 결과를 화면으로 옮기는 감싸기 ----
    def _wrap(self):
        orig_parse, orig_detect, orig_say = P.nlu.parse, P.detect, self.a.say
        st = self.state

        def parse(text):
            p = orig_parse(text)
            st["parse"] = f"{p['intent']}" + (f"({p['floor']})" if p["floor"] is not None else "")
            st["target"] = p["floor"]
            return p

        def detect(frame, templates, debug=None):
            res = orig_detect(frame, templates, debug)
            st["dets"] = res
            return res

        def say(msg):
            st["msg"] = _translate(msg, MSG_EN, msg)
            orig_say(msg)

        P.nlu.parse, P.detect, self.a.say = parse, detect, say
        return orig_parse, orig_detect, orig_say

    def _unwrap(self, saved):
        P.nlu.parse, P.detect, self.a.say = saved

    # ---- 프레임 ----
    def _head_overlay(self, img):
        """head 카메라 영상에 검출 결과를 그린다. 오른쪽 위에 패널 주변 확대 화면(1280x960 원본에서 자름)을 붙인다."""
        d, m = self.sc.data, self.sc.model
        cid = m.camera("head_rgb").id
        cam = dict(fovy=float(m.cam_fovy[cid]), cam_xpos=d.cam_xpos[cid].copy(),
                   cam_xmat=d.cam_xmat[cid].reshape(3, 3).copy())
        small = Frame(rgb=None, depth=np.zeros((VH, VW)), **cam)
        big = Frame(rgb=None, depth=np.zeros((960, 1280)), **cam)
        dets, target = self.state["dets"], self.state["target"]
        draw = ImageDraw.Draw(img)
        for r in dets:
            u, v = small.project(np.asarray(r["center"]))
            color = (255, 220, 0) if r["floor"] == target else (0, 255, 0)
            draw.ellipse([u - 7, v - 7, u + 7, v + 7], outline=color, width=2)
        # 확대 화면: 검출이 있으면 검출 중심들의 평균, 없으면 기준 위치 패널 부근
        hr = self.sc.renderer
        hr.update_scene(d, camera="head_rgb")
        hi = Image.fromarray(hr.render().copy())
        if dets:
            uv = np.array([big.project(np.asarray(r["center"])) for r in dets])
            self._crop_c = uv.mean(axis=0)
        cu, cv = getattr(self, "_crop_c", (615.0, 600.0))
        cw, ch = INSET_W, INSET_H
        x0 = int(np.clip(cu - cw / 2, 0, 1280 - cw))
        y0 = int(np.clip(cv - ch / 2, 0, 960 - ch))
        inset = hi.crop((x0, y0, x0 + cw, y0 + ch))
        di = ImageDraw.Draw(inset)
        for r in dets:
            u, v = big.project(np.asarray(r["center"]))
            u, v = u - x0, v - y0
            u2, _ = big.project(np.asarray(r["center"]) + np.cross([0, 0, 1.0], r["normal"]) * 0.03)
            rad = max(8, abs(u2 - x0 - u))
            color = (255, 220, 0) if r["floor"] == target else (0, 255, 0)
            di.ellipse([u - rad, v - rad, u + rad, v + rad], outline=color, width=2)
            di.text((u + rad + 2, v - rad - 2), str(r["floor"]), fill=color, font=self.font)
        di.rectangle([0, 0, cw - 1, ch - 1], outline=(200, 200, 200), width=1)
        img.paste(inset, (VW - cw - 6, 6))
        draw.text((8, 6), "head_rgb (perception)", fill=(255, 255, 255), font=self.font_small)
        txt = "detected: " + (" ".join(f"{r['floor']}({r['score']:.2f})" for r in dets) if dets else "-")
        draw.text((8, VH - 22), txt, fill=(255, 255, 255), font=self.font_small)
        draw.text((VW - cw - 6, ch + 10), "zoom x2 (yellow = target)", fill=(255, 255, 255), font=self.font_small)

    def _frame(self):
        d = self.sc.data
        self.r.update_scene(d, camera="overview")
        left = Image.fromarray(self.r.render().copy())
        ImageDraw.Draw(left).text((8, 6), "overview", fill=(255, 255, 255), font=self.font_small)
        self.r.update_scene(d, camera="head_rgb")
        right = Image.fromarray(self.r.render().copy())
        self._head_overlay(right)
        canvas = Image.new("RGB", (2 * VW, VH + BAND), (20, 22, 26))
        canvas.paste(left, (0, 0))
        canvas.paste(right, (VW, 0))
        st = self.state
        slides = self.sc.slides()
        n = st["target"]
        if n in slides:
            disp = f"Target floor {n} button displacement: {slides[n] * 1000:5.1f} mm   (success >= 10 mm)"
        else:
            disp = "Target button displacement: -   max of all buttons: " \
                   f"{max(slides.values()) * 1000:.1f} mm"
        lines = [self.header,
                 f"Command: {st['text_en']}",
                 f"Decision: parse {st['parse'] or '-'}   |   robot: {st['msg'] or '-'}",
                 disp,
                 f"Elapsed (simulation time): {d.time - st['t0']:5.2f} s" + (f"   |   {self.note}" if self.note else "")]
        draw = ImageDraw.Draw(canvas)
        for i, line in enumerate(lines):
            draw.text((12, VH + 8 + i * 28), line, fill=(235, 235, 235), font=self.font)
        return np.asarray(canvas)

    def _on_tick(self, _m, _d):
        self._tick += 1
        if self._tick % TICKS_PER_FRAME == 0:
            self.frames.append(self._frame())

    def run(self, text):
        """명령 한 번을 실행하며 녹화한다. 반환: Assistant.run의 기록."""
        st = self.state
        st.update(text=text, text_en=gloss(text), t0=self.sc.data.time)
        first = self._frame()
        self.frames += [first] * int(PRE_S * FPS)
        saved = self._wrap()
        self.a.ctl.tick_hooks = [self._on_tick]
        try:
            rec = self.a.run(text)
        finally:
            self.a.ctl.tick_hooks = []
            self._unwrap(saved)
        last = self._frame()
        self.frames += [last] * int(POST_S * FPS)
        return rec

    def save(self, path):
        with imageio.get_writer(str(path), fps=FPS, codec="libx264", quality=7, macro_block_size=8) as w:
            for f in self.frames:
                w.append_data(f)
        self.r.close()
        return len(self.frames)
