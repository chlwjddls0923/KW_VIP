"""4단계 adv_test: 동결 상태(44f25b5)의 step4.py를 고치지 않고 adv_test만 한 번 실행한다 (사용자 지시 2026-11-24).

  .venv-llm/bin/python experiments/llm/step4_adv_test.py freeze   동결 파일 sha256 확인 + adv_test sha256 기록
                                                                   → results/exp_llm/step4_adv_test_freeze.json (커밋한 뒤 run)
  .venv-llm/bin/python experiments/llm/step4_adv_test.py run      adv_test에 모델 한 번 → results/exp_llm/step4_adv_test/
  .venv-llm/bin/python experiments/llm/step4_adv_test.py report   저장한 출력으로 결합·채점 → step4_adv_test/step4.md, step4_decisions.csv
                                                                   (이 내용을 results/exp_llm/step4.md의 adv_test 절에 옮긴다)

step4.py의 run은 holdout 원시 출력이 있으면 멈추므로, 출력 폴더(OUT)와 세트 목록(SETS)만 바꿔 step4의 함수를 그대로 부른다.
채점·결합·게이트·프롬프트는 step4.py와 같다.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import step4  # noqa: E402

ROOT, OUT0 = step4.ROOT, step4.OUT
FREEZE = OUT0 / "step4_freeze.json"
ADV_FREEZE = OUT0 / "step4_adv_test_freeze.json"
ADV_OUT = OUT0 / "step4_adv_test"
ADV_FILE = step4.DATA / step4.SETS["adv_test"]
COLUMNS = ["text", "expected_action", "expected_floor", "type", "debatable"]


def check_frozen(with_model=True):
    """step4_freeze.json에 적힌 sha256과 지금 파일이 같은지. 다르면 목록을 돌려준다."""
    fz = json.loads(FREEZE.read_text(encoding="utf-8"))
    bad = {f: "변경" for f, h in fz["files_sha256"].items() if step4.sha(ROOT / f) != h}
    if with_model and step4.sha(step4.path(step4.KEY)) != fz["model_sha256_local"]:
        bad["model"] = "변경"
    return fz, bad


def cmd_freeze():
    if not ADV_FILE.exists():
        sys.exit("data/commands_adv_test.tsv 없음 → 미실시")
    header = ADV_FILE.read_text(encoding="utf-8").splitlines()[0].split("\t")
    if header != COLUMNS:
        sys.exit(f"열이 adv_dev와 다름: {header}")
    fz, bad = check_frozen()
    if bad:
        sys.exit(f"동결 파일이 바뀌었다. 실행하지 않는다: {bad}")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = step4.load_set("adv_test")
    out = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "head": head, "frozen_commit_of_step4": "44f25b5",
           "step4_freeze_check": "동결 파일·모델 sha256 모두 같음", "adv_test_file": os.path.relpath(ADV_FILE, ROOT),
           "adv_test_sha256": step4.sha(ADV_FILE), "adv_test_rows": len(rows)}
    ADV_FREEZE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


def patch():
    af = json.loads(ADV_FREEZE.read_text(encoding="utf-8"))
    if step4.sha(ADV_FILE) != af["adv_test_sha256"]:
        sys.exit("adv_test 파일이 동결 뒤에 바뀌었다. 실행하지 않는다.")
    _, bad = check_frozen(with_model=False)
    if bad:
        sys.exit(f"동결 파일이 바뀌었다. 실행하지 않는다: {bad}")
    ADV_OUT.mkdir(exist_ok=True)
    step4.OUT = ADV_OUT
    step4.SETS = {"adv_test": step4.SETS["adv_test"]}


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "freeze":
        cmd_freeze()
    else:
        patch()
        {"run": step4.cmd_run, "report": step4.cmd_report}[cmd]()
