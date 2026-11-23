"""추론 PC 사양: CPU, 메모리, GPU 유무, OS, 패키지 버전 → results/sysinfo.json (그리고 화면 출력)."""
import json
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psutil  # noqa: E402

from assist.paths import RESULTS  # noqa: E402

PACKAGES = ("mujoco", "numpy", "scipy", "pillow", "kiwipiepy", "kiwipiepy_model", "imageio", "imageio-ffmpeg",
            "psutil", "pytest")


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def collect():
    info = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "cpu": platform.processor(),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "memory_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "packages": {},
    }
    if sys.platform == "darwin":
        info["cpu"] = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or info["cpu"]
        info["model"] = _run(["sysctl", "-n", "hw.model"])
        info["macos"] = _run(["sw_vers", "-productVersion"])
        disp = _run(["system_profiler", "SPDisplaysDataType"])
        chip = [l.split(":", 1)[1].strip() for l in disp.splitlines() if "Chipset Model" in l]
        info["gpu"] = ("별도 GPU 없음. 칩 내장 GPU: " + ", ".join(chip)) if chip else "별도 GPU 없음"
    else:
        info["gpu"] = "확인 안 됨"
    info["gpu_use"] = ("해석·인식·IK 계산은 CPU(numpy·scipy)에서 한다. 카메라 영상 생성(MuJoCo 오프스크린 렌더링)은 "
                       "OS 기본 OpenGL 백엔드를 쓴다.")
    for p in PACKAGES:
        try:
            info["packages"][p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            info["packages"][p] = None
    return info


def main():
    info = collect()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "sysinfo.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
