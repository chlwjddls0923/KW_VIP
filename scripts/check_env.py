"""단계 0 환경 점검.

버전 출력 → 원본 XML 로드 → nq/nv/nu 출력 → head_rgb 640x480 저장 → kiwipiepy 토큰 출력.
렌더링은 OS 기본 백엔드를 쓴다(macOS는 MUJOCO_GL을 설정하지 않는다).
"""
import os
import platform
import sys
import time
from pathlib import Path

# scripts/에서 실행해도 src의 패키지를 찾도록 경로를 넣는다
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import mujoco
import numpy
import scipy
import kiwipiepy
from PIL import Image

from assist.paths import ORIGINAL_XML, OUT


def main():
    print(f"python     {platform.python_version()} ({sys.executable})")
    print(f"platform   {platform.platform()}")
    print(f"mujoco     {mujoco.__version__}")
    print(f"numpy      {numpy.__version__}")
    print(f"scipy      {scipy.__version__}")
    print(f"kiwipiepy  {kiwipiepy.__version__}")
    print(f"MUJOCO_GL  {os.environ.get('MUJOCO_GL', '(설정 안 됨: OS 기본 백엔드)')}")

    # 원본 모델 로드 (읽기만 한다)
    model = mujoco.MjModel.from_xml_path(str(ORIGINAL_XML))
    data = mujoco.MjData(model)
    print(f"model      nq={model.nq} nv={model.nv} nu={model.nu} timestep={model.opt.timestep}")

    # head_rgb 카메라로 화면 없이 한 장 렌더링한다
    mujoco.mj_forward(model, data)
    OUT.mkdir(exist_ok=True)
    renderer = mujoco.Renderer(model, height=480, width=640)
    try:
        renderer.update_scene(data, camera="head_rgb")
        rgb = renderer.render().copy()
    finally:
        renderer.close()
    path = OUT / "check_head.png"
    Image.fromarray(rgb).save(path)
    print(f"render     {path.relative_to(OUT.parent)} {rgb.shape} mean={rgb.mean():.1f}")

    # 형태소 분석기: 첫 생성은 모델을 읽느라 오래 걸리므로 시간을 따로 잰다
    t0 = time.perf_counter()
    kiwi = kiwipiepy.Kiwi()
    t_init = time.perf_counter() - t0
    text = "3층 버튼을 눌러줘"
    t0 = time.perf_counter()
    tokens = kiwi.tokenize(text)
    t_tok = time.perf_counter() - t0
    print(f"kiwi init  {t_init * 1000:.0f} ms, tokenize {t_tok * 1000:.2f} ms")
    print(f"tokens     {text!r}: " + " ".join(f"{t.form}/{t.tag}" for t in tokens))
    print("check_env OK")


if __name__ == "__main__":
    main()
