"""특정 시행을 같은 조건으로 다시 실행하며 mp4로 저장한다 (results/video/).

  python scripts/record.py --trial V03       공식 (B01~B10, V01~V10, C01~C05)
  python scripts/record.py --trial FB03      고정 좌표 기준선 (FB/FV, 인식 없음)
  python scripts/record.py --trial SV024     추가 시험 (SB/SV, 공식 20회 밖)

녹화한 결과(success, failure_type, 목표 변위)가 평가 때의 trials.csv와 같은지 확인해 목록에 적는다.
공식 결과 파일은 건드리지 않는다.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from assist.paths import RESULTS  # noqa: E402
from assist.pipeline import Assistant  # noqa: E402
from assist.protocol import (FAILURE_KO, baseline_trials, dev_trials, judge, official_trials,  # noqa: E402
                             supplementary_trials)
from assist.record import Recorder  # noqa: E402
from assist.scene import Scene  # noqa: E402

VIDEO = RESULTS / "video"
INDEX = VIDEO / "videos.json"
SOURCE = {"basic": "official_run1", "variation": "official_run1", "check": "official_run1",
          "supp_basic": "supplementary", "supp_variation": "supplementary"}
SET_KO = {"basic": "공식 기본", "variation": "공식 변화", "check": "공식 명령 점검", "supp_basic": "추가 기본(공식 20회 밖)",
          "supp_variation": "추가 변화(공식 20회 밖)", "dev": "개발용"}


def find_trial(tid):
    for t in official_trials() + supplementary_trials() + dev_trials():
        if t.trial_id == tid:
            return t, "full"
    for t in baseline_trials():
        if t.trial_id == tid:
            return t, "baseline_fixed"
    sys.exit(f"시행 {tid}를 찾지 못함")


def original_row(trial, mode):
    src = "baseline_run1" if mode == "baseline_fixed" else SOURCE.get(trial.set)
    if not src or not (RESULTS / src / "trials.csv").exists():
        return None, None
    with open(RESULTS / src / "trials.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["trial_id"] == trial.trial_id:
                return r, src
    return None, src


def main():
    ap = argparse.ArgumentParser(description="시행 녹화")
    ap.add_argument("--trial", required=True)
    args = ap.parse_args()
    trial, mode = find_trial(args.trial)
    VIDEO.mkdir(parents=True, exist_ok=True)

    scene = Scene(layout=trial.layout)
    assistant = Assistant(scene, mode=mode, say=lambda m: print(f"[로봇] {m}"))
    scene.reset(trial.dpos, trial.yaw_deg, trial.light)
    truth = scene.truth()
    cond = (f"panel d=({trial.dpos[0] * 100:+.1f},{trial.dpos[1] * 100:+.1f},{trial.dpos[2] * 100:+.1f}) cm, "
            f"yaw {trial.yaw_deg:+.1f} deg, light x{trial.light:.2f}, layout {trial.layout_str}")
    header = f"Trial {trial.trial_id} (seed {trial.seed if trial.seed is not None else '-'}, {trial.set}) | {cond}"
    note = {"baseline_fixed": "BASELINE (no perception, fixed coordinates) - comparison only",
            "supp_basic": "Outside the official 20 trials (supplementary)",
            "supp_variation": "Outside the official 20 trials (supplementary)"}.get(
        "baseline_fixed" if mode == "baseline_fixed" else trial.set, "")
    rec_ = Recorder(assistant, header, note)
    rec = rec_.run(trial.text)
    ok, ftype = judge(trial, rec)
    n = trial.expected_floor
    tgt = rec["max_slide"].get(n, 0.0) * 1000 if n is not None else None
    outcome = "success" if ok else f"fail_{ftype}"
    kind = "baseline_" if mode == "baseline_fixed" else ""
    name = f"{trial.trial_id}_{kind}{outcome}_seed{trial.seed}.mp4" if trial.seed is not None \
        else f"{trial.trial_id}_{kind}{outcome}.mp4"
    nframes = rec_.save(VIDEO / name)
    scene.close()

    orig, src = original_row(trial, mode)
    match = None
    if orig is not None:
        match = (orig["success"] == str(int(ok)) and orig["failure_type"] == ftype
                 and (tgt is None or abs(float(orig["max_slide_target_mm"]) - tgt) < 1e-3))
    entry = {"file": name, "trial_id": trial.trial_id, "set": trial.set, "mode": mode, "seed": trial.seed,
             "text": trial.text, "expected": f"{trial.expected_action}" + (f"({n})" if n else ""),
             "action": rec["action"], "success": ok, "failure_type": ftype,
             "failure_ko": FAILURE_KO.get(ftype, ""), "target_mm": None if tgt is None else round(tgt, 3),
             "target_z": float(truth[n]["center"][2]) if n in truth else None,
             "panel_d_cm": [round(v * 100, 4) for v in trial.dpos], "yaw_deg": round(trial.yaw_deg, 4),
             "light": round(trial.light, 3), "layout": trial.layout_str, "frames": nframes,
             "seconds": round(nframes / 25, 2), "source_csv": src, "matches_source": match,
             "messages": rec["messages"]}
    index = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}
    index[trial.trial_id] = entry
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    write_index_md(index)
    print(f"저장: results/video/{name} ({nframes} 프레임), 평가 결과와 일치: {match}")


def write_index_md(index):
    lines = ["# 영상 목록", "", "`scripts/record.py --trial ID`로 평가 시행을 같은 시드·조건으로 다시 실행하며 녹화했다. "
             "'평가와 일치'는 녹화 때의 success·실패 유형·목표 변위가 해당 `trials.csv`와 같은지다.", "",
             "| 파일 | 시행 | 구분 | 시드 | 조건 (패널 이동 cm, 회전, 조명, 숫자 배치) | 명령 | 결과 | 실패 유형 | 목표 변위 | 평가와 일치 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for e in sorted(index.values(), key=lambda e: e["file"]):
        d = e["panel_d_cm"]
        tmm = "-" if e["target_mm"] is None else f"{e['target_mm']:.1f} mm"
        kind ="기준선(인식 없음)" if e["mode"] == "baseline_fixed" else SET_KO.get(e["set"], e["set"])
        lines.append(f"| `{e['file']}` | {e['trial_id']} | {kind} | {e['seed'] if e['seed'] is not None else '-'} | "
                     f"({d[0]:+.1f}, {d[1]:+.1f}, {d[2]:+.1f}), {e['yaw_deg']:+.1f}°, {e['light']:.2f}배, {e['layout']} | "
                     f"{e['text']} | {'성공' if e['success'] else '실패'} ({e['action']}) | {e['failure_ko'] or '-'} | "
                     f"{tmm} | "
                     f"{'-' if e['matches_source'] is None else ('예' if e['matches_source'] else '아니오')} ({e['source_csv']}) |")
    (VIDEO / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
