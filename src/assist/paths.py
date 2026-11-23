"""프로젝트 경로 상수. 모든 모듈이 같은 위치를 쓰도록 한 곳에 모은다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
ORIGINAL_XML = ASSETS / "wheelchair_piper_lite.xml"  # 원본, 수정 금지
BUILD = ROOT / "build"
OUT = ROOT / "out"
DATA = ROOT / "data"
RESULTS = ROOT / "results"
