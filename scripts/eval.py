"""평가 실행 (계획서 단계 6, 부록 E).

  python scripts/eval.py protocol                 data/eval_protocol.json 작성 (이미 있으면 내용 확인만)
  python scripts/eval.py official [--out DIR]     공식 25회      → results/official_run1/
  python scripts/eval.py baseline [--out DIR]     고정 좌표 기준선 → results/baseline_run1/
  python scripts/eval.py supplementary [--out DIR] 추가 200회     → results/supplementary/
  python scripts/eval.py nlu                      해석 정확도     → results/nlu/ (holdout은 한 번만)
  python scripts/eval.py summary                  results/summary.json, results/summary.md

결과 폴더가 이미 있으면 덮어쓰지 않고 멈춘다. official·baseline은 커밋된 eval_protocol.json과
조건 값이 같은지 확인한 뒤에만 실행한다.
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from assist import nlu  # noqa: E402
from assist.paths import DATA, RESULTS, ROOT  # noqa: E402
from assist.pipeline import CSV_COLUMNS, SceneCache, run_trial  # noqa: E402
from assist.protocol import (CHECKS, FAILURE_KO, OTHER_LIMIT, STILL_JOINT, STILL_SLIDE, SUCCESS_SLIDE,  # noqa: E402
                             TEMPLATES, TIME_LIMIT, baseline_trials, official_trials, supplementary_trials,
                             wilson)
from assist.pipeline import STILL_HOLD_S  # noqa: E402

PROTOCOL = DATA / "eval_protocol.json"
SEEN_ALL = [1, 2, 3, 4, 5, 6]
DEFAULT_OUT = {"official": RESULTS / "official_run1", "baseline": RESULTS / "baseline_run1",
               "supplementary": RESULTS / "supplementary"}


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


# ---------------- 프로토콜 ----------------
def _trial_conditions(tr):
    return {"trial_id": tr.trial_id, "set": tr.set, "seed": tr.seed, "panel_dx": tr.dpos[0],
            "panel_dy": tr.dpos[1], "panel_dz": tr.dpos[2], "yaw_deg": tr.yaw_deg, "light": tr.light,
            "layout": tr.layout_str, "target_floor": tr.expected_floor, "template": tr.template,
            "text": tr.text, "expected_action": tr.expected_action}


def build_protocol():
    return {
        "description": "공식 평가 조건. 실행 전에 커밋한다(계획서 4절). 값은 numpy.random.default_rng(seed)에서 부록 E 순서로 뽑았다.",
        "success_criteria": {
            "press": f"제한 시간(시뮬레이션 {TIME_LIMIT:.0f}초) 안에 목표 버튼 slide 최댓값 >= {SUCCESS_SLIDE} m 이고 "
                     f"다른 버튼은 모두 < {OTHER_LIMIT} m",
            "still": f"팔 관절 최대 변화 < {STILL_JOINT} rad, 모든 버튼 slide < {STILL_SLIDE} m, 행동 분류가 기대와 같음",
            "success_slide_m": SUCCESS_SLIDE, "other_limit_m": OTHER_LIMIT, "still_slide_m": STILL_SLIDE,
            "still_joint_rad": STILL_JOINT, "time_limit_s": TIME_LIMIT,
            "still_hold_s": STILL_HOLD_S,
        },
        "sampling": {
            "basic": "dx, dy, dz 각 uniform(-0.03, 0.03) -> 목표 층 int(rng.integers(1, 7)) -> 문장 틀 int(rng.integers(0, 5)). "
                     "회전 0, 조명 1.0, 기본 숫자 배치",
            "variation": "dx uniform(-0.10, 0.10), dy uniform(-0.05, 0.05), dz uniform(-0.10, 0.10) -> 회전 uniform(-10, 10) 도 "
                         "-> 조명 uniform(0.6, 1.2) -> rng.permutation(6) -> 목표 층 -> 문장 틀",
            "layout": "P1~P6에 놓인 층을 순서대로 적은 문자열. (perm[i]+1)층이 P(i+1)",
            "templates": list(TEMPLATES),
        },
        "official": [_trial_conditions(t) for t in official_trials()],
        "baseline_fixed": {"ids": [t.trial_id for t in baseline_trials()],
                           "conditions": "공식 기본·변화 20회와 같은 조건",
                           "method": "명령 해석은 그대로, 인식 없이 1~6층이 모두 있다고 보고 라벨 중심 = (0.43, -0.87, 0.99) + (x, 0.081, z), "
                                     "법선 (0, 1, 0)인 설계 상수로 누른다"},
        "supplementary": {"basic_seeds": [3001, 3100], "variation_seeds": [4001, 4100], "ids": "SB001~SB100, SV001~SV100"},
        "nlu": {"dev": "data/commands_dev.tsv", "holdout": "data/commands_holdout.tsv (사용자 제공, 한 번만 실행)",
                "team": "data/commands_team.tsv (없음)", "seen_floors": SEEN_ALL,
                "judge": "ground(parse(text), {1..6})가 기대 행동(PRESS면 층까지)과 같으면 정답. digits_only도 같은 ground를 거친다"},
        "checks": [{"trial_id": c[0], "text": c[1], "expected_action": c[2], "expected_floor": c[3]} for c in CHECKS],
    }


def cmd_protocol(_args):
    proto = build_protocol()
    if PROTOCOL.exists():
        old = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        print("eval_protocol.json 이미 있음:", "내용 같음" if old == json.loads(json.dumps(proto)) else "내용 다름 (덮어쓰지 않음)")
        return
    PROTOCOL.write_text(json.dumps(proto, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"작성: {PROTOCOL.relative_to(ROOT)} (커밋한 뒤 official/baseline을 실행한다)")


def _check_protocol(trials):
    """커밋된 eval_protocol.json의 조건과 지금 뽑은 조건이 같은지 확인."""
    if not PROTOCOL.exists():
        sys.exit("data/eval_protocol.json이 없다. 먼저 `eval.py protocol` 후 커밋한다.")
    rel = str(PROTOCOL.relative_to(ROOT))
    if _git("ls-files", rel) != rel or _git("status", "--porcelain", rel):
        sys.exit("data/eval_protocol.json이 커밋되지 않았거나 수정되었다. 커밋한 뒤 실행한다.")
    saved = {d["trial_id"]: d for d in json.loads(PROTOCOL.read_text(encoding="utf-8"))["official"]}
    for tr in trials:
        key = tr.trial_id[1:] if tr.trial_id.startswith("F") else tr.trial_id
        want = dict(saved[key])
        got = _trial_conditions(tr)
        got["trial_id"], got["set"] = want["trial_id"], want["set"]
        if json.loads(json.dumps(got)) != want:
            sys.exit(f"조건 불일치: {tr.trial_id}")


# ---------------- 실행 ----------------
def _run_set(trials, out_dir, mode):
    if out_dir.exists():
        sys.exit(f"{out_dir.relative_to(ROOT)} 이미 있음: 덮어쓰지 않고 멈춘다.")
    out_dir.mkdir(parents=True)
    t0 = time.perf_counter()
    started = datetime.now().isoformat(timespec="seconds")
    cache = SceneCache(mode=mode)
    nlu.get_kiwi()
    rows = []
    with open(out_dir / "trials.csv", "w", encoding="utf-8", newline="") as fc, \
            open(out_dir / "details.jsonl", "w", encoding="utf-8") as fd:
        w = csv.DictWriter(fc, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for tr in trials:
            row, rec = run_trial(tr, cache)
            w.writerow(row)
            fc.flush()
            rows.append(row)
            keep = {k: rec.get(k) for k in ("messages", "detections", "parsed", "exception", "ik_err_mm",
                                             "t_first_10mm")}
            keep["max_slide_mm"] = {str(k): v * 1000 for k, v in rec["max_slide"].items()}
            fd.write(json.dumps({"trial_id": tr.trial_id, **keep}, ensure_ascii=False, default=str) + "\n")
            print(f"{tr.trial_id:6s} {tr.text:28s} -> {row['action']:8s} success={row['success']} "
                  f"{row['failure_type']:14s} target={row['max_slide_target_mm']:>7s} mm z={row['target_z']}")
    cache.close()
    info = {"mode": mode, "started": started, "wall_s": round(time.perf_counter() - t0, 1),
            "git_commit": _git("rev-parse", "--short", "HEAD"), "n_trials": len(rows),
            "nlu_init_ms": nlu.INIT_MS, "argv": sys.argv}
    (out_dir / "run_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(r["success"] == "1" for r in rows)
    print(f"{out_dir.relative_to(ROOT)}: {ok}/{len(rows)} 성공, {info['wall_s']} s")


def cmd_official(args):
    trials = official_trials()
    _check_protocol(trials)
    _run_set(trials, Path(args.out).resolve() if args.out else DEFAULT_OUT["official"], "full")


def cmd_baseline(args):
    trials = baseline_trials()
    _check_protocol(trials)
    _run_set(trials, Path(args.out).resolve() if args.out else DEFAULT_OUT["baseline"], "baseline_fixed")


def cmd_supplementary(args):
    _run_set(supplementary_trials(), Path(args.out).resolve() if args.out else DEFAULT_OUT["supplementary"], "full")


# ---------------- 해석 평가 ----------------
def _load_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                text, action, floor = line.rstrip("\n").split("\t")
                rows.append((text, action.strip(), None if floor.strip() == "-" else int(floor)))
    return rows


def _eval_sentences(rows):
    out = []
    for text, action, floor in rows:
        t = time.perf_counter()
        p = nlu.parse(text)
        ms = (time.perf_counter() - t) * 1000
        g = nlu.ground(p, SEEN_ALL)
        b = nlu.ground(nlu.digits_only(text), SEEN_ALL)
        ok = g["action"] == action and (action != "PRESS" or g["floor"] == floor)
        bok = b["action"] == action and (action != "PRESS" or b["floor"] == floor)
        out.append({"text": text, "expected_action": action, "expected_floor": "" if floor is None else floor,
                    "action": g["action"], "floor": "" if g["floor"] is None else g["floor"],
                    "correct": int(ok), "false_press": int(action != "PRESS" and g["action"] == "PRESS"),
                    "baseline_action": b["action"], "baseline_floor": "" if b["floor"] is None else b["floor"],
                    "baseline_correct": int(bok),
                    "baseline_false_press": int(action != "PRESS" and b["action"] == "PRESS"),
                    "parse_ms": round(ms, 4), "intent": p["intent"],
                    "scores": json.dumps({k: round(v, 3) for k, v in p["scores"].items()}),
                    "events": json.dumps(p["events"], ensure_ascii=False)})
    return out


def _write_rows(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _acc(rows):
    n = len(rows)
    return {"n": n, "correct": sum(r["correct"] for r in rows), "false_press": sum(r["false_press"] for r in rows),
            "baseline_correct": sum(r["baseline_correct"] for r in rows),
            "baseline_false_press": sum(r["baseline_false_press"] for r in rows),
            "parse_ms_median": float(np.median([r["parse_ms"] for r in rows]))}


def cmd_nlu(_args):
    out = RESULTS / "nlu"
    out.mkdir(parents=True, exist_ok=True)
    nlu.get_kiwi()
    summary = {"nlu_init_ms": nlu.INIT_MS, "date": datetime.now().isoformat(timespec="seconds"),
               "git_commit": _git("rev-parse", "--short", "HEAD")}
    dev = _eval_sentences(_load_tsv(DATA / "commands_dev.tsv"))
    _write_rows(out / "dev.csv", dev)
    summary["dev"] = _acc(dev)
    for name in ("holdout", "team"):
        src, dst = DATA / f"commands_{name}.tsv", out / f"{name}.csv"
        if dst.exists():                                   # 한 번만 실행: 기존 결과를 그대로 쓴다
            with open(dst, encoding="utf-8") as f:
                rows = [{k: (int(v) if k in ("correct", "false_press", "baseline_correct", "baseline_false_press")
                             else float(v) if k == "parse_ms" else v) for k, v in r.items()} for r in csv.DictReader(f)]
            summary[name] = {**_acc(rows), "note": "기존 결과 재사용(다시 실행하지 않음)"}
        elif src.exists():
            rows = _eval_sentences(_load_tsv(src))
            _write_rows(dst, rows)
            summary[name] = {**_acc(rows), "note": "1회 실행"}
        else:
            summary[name] = "미실시"
    (out / "nlu_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for name in ("holdout", "team"):
        if isinstance(summary[name], dict) and summary[name]["false_press"]:
            print(f"주의: {name}에서 눌러선 안 되는 문장이 PRESS로 나왔다 ({summary[name]['false_press']}건). 보고한다.")


# ---------------- 요약 ----------------
def _read_trials(d):
    p = d / "trials.csv"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _rate(rows):
    k, n = sum(r["success"] == "1" for r in rows), len(rows)
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": k / n if n else float("nan"), "ci95": [lo, hi]}


def _pct(x):
    """백분율: 정수가 아니면 소수 한 자리 (예: 199/200 = 99.5%)."""
    v = x * 100
    return f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.1f}"


def _rate_str(r):
    return f"{r['k']}/{r['n']} ({_pct(r['rate'])}%, 95% 구간 {_pct(r['ci95'][0])}~{_pct(r['ci95'][1])}%)"


def _med(vals):
    vals = [float(v) for v in vals if v not in ("", None)]
    return float(np.median(vals)) if vals else None


def _cause(r):
    """실패마다 사실만 적은 원인 한 줄."""
    parts = [f"목표 {r['expected_floor']}층" if r["expected_floor"] else "", ]
    if r["target_z"]:
        parts.append(f"목표 버튼 높이 {float(r['target_z']):.2f} m")
    if r["failure_type"] == "not_detected":
        parts.append(f"미검출(보인 층 {r['seen_floors'] or '없음'})")
    elif r["failure_type"] == "nlu":
        parts.append(f"해석 {r['parsed_intent']}({r['parsed_floor']}), 기대 {r['expected_action']}")
    elif r["failure_type"] == "under_10mm":
        parts.append(f"목표 변위 {r['max_slide_target_mm']} mm")
    elif r["failure_type"] == "wrong_button":
        parts.append(f"다른 버튼 최대 변위 {r['max_slide_other_mm']} mm")
    elif r["failure_type"] == "ik_unreachable":
        parts.append("접근·누름 IK 위치 오차 1 mm 초과")
    elif r["failure_type"] == "moved":
        parts.append(f"관절 최대 변화 {r['max_joint_motion_rad']} rad, 버튼 최대 {r['max_slide_other_mm']} mm")
    elif r["failure_type"] == "exception":
        parts.append("실행 예외(details.jsonl 참고)")
    elif r["failure_type"] == "timeout":
        parts.append(f"10 mm 도달 시각 {r['t_press_s']} s")
    if r["panel_dz"]:
        parts.append(f"패널 이동 (dx {float(r['panel_dx']) * 100:+.1f}, dy {float(r['panel_dy']) * 100:+.1f}, "
                     f"dz {float(r['panel_dz']) * 100:+.1f}) cm, 회전 {float(r['yaw_deg']):+.1f}°")
    return ", ".join(p for p in parts if p)


def _failure_table(rows):
    fails = [r for r in rows if r["success"] != "1"]
    lines = ["| 실패 유형 | 횟수 | 시행 ID |", "|---|---|---|"]
    by = {}
    for r in fails:
        by.setdefault(r["failure_type"], []).append(r["trial_id"])
    if not by:
        lines.append("| (없음) | 0 | |")
    for k, ids in by.items():
        lines.append(f"| {FAILURE_KO.get(k, k)} | {len(ids)} | {', '.join(ids)} |")
    detail = [f"- {r['trial_id']}: {_cause(r)}" for r in fails]
    return lines, detail, fails


def _section_run(title, rows):
    basic = [r for r in rows if r["set"] in ("basic", "supp_basic")]
    var = [r for r in rows if r["set"] in ("variation", "supp_variation")]
    allp = basic + var
    rb, rv, ra = _rate(basic), _rate(var), _rate(allp)
    return {"title": title, "all": ra, "basic": rb, "variation": rv,
            "gap_pp": (rb["rate"] - rv["rate"]) * 100}


def cmd_summary(_args):
    off_dirs = sorted(d for d in RESULTS.glob("official_run*") if (d / "trials.csv").exists())
    if not off_dirs:
        sys.exit("공식 결과가 없다.")
    sysinfo = json.loads((RESULTS / "sysinfo.json").read_text(encoding="utf-8")) if (RESULTS / "sysinfo.json").exists() else {}
    nlu_sum = json.loads((RESULTS / "nlu" / "nlu_summary.json").read_text(encoding="utf-8")) \
        if (RESULTS / "nlu" / "nlu_summary.json").exists() else {}
    base_rows = _read_trials(RESULTS / "baseline_run1")
    supp_rows = _read_trials(RESULTS / "supplementary")
    rerun_rows = _read_trials(RESULTS / "rerun")

    S = {"runs": {}, "sysinfo": sysinfo, "nlu": nlu_sum}
    md = ["# 평가 결과 요약", "",
          f"생성: {datetime.now().isoformat(timespec='seconds')} (`scripts/eval.py summary`). 모든 수치는 이 저장소에서 실행한 결과다.", ""]

    # 평가 방법
    md += ["## 평가 방법", "",
           "- 조건: `data/eval_protocol.json`에 공식 20회의 시드와 조건 값(패널 이동·회전·조명·숫자 배치·목표 층·문장)을 먼저 적고 커밋한 뒤 실행했다. "
           "기본 B01~B10(시드 1001~1010), 변화 V01~V10(시드 2001~2010), 명령 점검 C01~C05(기준 위치, 고정 문장).",
           f"- 누르기 시행 성공: 시뮬레이션 {TIME_LIMIT:.0f}초 안에 목표 버튼 slide 최댓값 ≥ {SUCCESS_SLIDE * 1000:.0f} mm이고 다른 버튼은 모두 < {OTHER_LIMIT * 1000:.0f} mm.",
           f"- 움직이면 안 되는 시행 성공: 팔 관절 최대 변화 < {STILL_JOINT} rad, 모든 버튼 slide < {STILL_SLIDE * 1000:.0f} mm, 행동 분류가 기대와 같음.",
           f"- 움직이지 않는 판단(WAIT·CLARIFY·REJECT·층 없음·IK 도달 불가) 뒤에도 시뮬레이션을 {STILL_HOLD_S:.0f}초 더 진행해 기록한다. "
           "판단 직후 바로 끝내면 위 정지 판정(관절 변화·버튼 변위)이 측정 시간 0으로 이루어지므로, 실제로 정지해 있는지 1초 동안 기록해 판정 근거로 삼았다.",
           "- 실패한 시행을 빼지 않았다. 모든 시행이 각 폴더의 `trials.csv`에 있다.",
           "- 시간 t_press·t_task는 시뮬레이션 시간이고 계산 시간은 들어가지 않는다. 계산 시간은 추론 지연으로 따로 적는다.", ""]

    # 공식 결과 (run별)
    for d in off_dirs:
        rows = _read_trials(d)
        press = [r for r in rows if r["set"] in ("basic", "variation")]
        checks = [r for r in rows if r["set"] == "check"]
        sec = _section_run(d.name, press)
        sec["checks"] = {"k": sum(r["success"] == "1" for r in checks), "n": len(checks)}
        ok_press = [r for r in press if r["success"] == "1"]
        sec["t_press_median"] = _med(r["t_press_s"] for r in ok_press)
        sec["t_task_median"] = _med(r["t_task_s"] for r in ok_press)
        sec["latency_ms"] = {"parse": _med(r["t_parse_ms"] for r in rows),
                             "perception": _med(r["t_perception_ms"] for r in rows),
                             "ik_approach": _med(r["t_ik_ms"] for r in rows)}
        info = json.loads((d / "run_info.json").read_text(encoding="utf-8"))
        sec["nlu_init_ms"] = info.get("nlu_init_ms")
        sec["git_commit"] = info.get("git_commit")
        S["runs"][d.name] = sec
        lines, detail, fails = _failure_table(rows)
        md += [f"## 공식 결과 `{d.name}` (커밋 {info.get('git_commit')}, {info.get('started')})", "",
               "### 성공률", "", "| 구분 | 성공 |", "|---|---|",
               f"| 전체 (20회) | {_rate_str(sec['all'])} |", f"| 기본 (10회) | {_rate_str(sec['basic'])} |",
               f"| 변화 (10회) | {_rate_str(sec['variation'])} |",
               f"| 일반화 격차 (기본 − 변화) | {sec['gap_pp']:+.0f}%p |", "",
               "### 명령 적합성", "",
               f"- 명령 점검 5회 중 {sec['checks']['k']}회 맞음: " +
               ", ".join(f"{r['trial_id']} {'O' if r['success'] == '1' else 'X'}({r['action']})" for r in checks),
               "- 점검 5문장과 기본·변화 시행의 문장 틀 5개는 dev 문장과 겹친다. 해석의 일반화는 아래 holdout 결과로 본다.", "",
               "### 작업 시간 (시뮬레이션 시간)", "",
               f"- 성공 시행 {len(ok_press)}회: t_press 중앙값 "
               f"{sec['t_press_median']:.2f} s, t_task 중앙값 {sec['t_task_median']:.2f} s" if ok_press else "- 성공 시행 없음",
               f"- 실패 시행: {', '.join(r['trial_id'] for r in press if r['success'] != '1') or '없음'}. "
               f"시간 초과: {', '.join(r['trial_id'] for r in press if r['failure_type'] == 'timeout') or '없음'}", "",
               "### 실패 유형", ""] + lines + [""] + (detail or ["- 실패 없음"]) + [""]
        md += ["### 추론 지연 (계산 시간, 중앙값)", "", "| 항목 | 값 |", "|---|---|",
               f"| 명령 해석 (분석기 초기화 제외) | {sec['latency_ms']['parse']:.3f} ms |",
               f"| 분석기 초기화 (첫 명령 1회) | {sec['nlu_init_ms']:.0f} ms |",
               f"| 인식 (촬영 포함) | {sec['latency_ms']['perception']:.0f} ms |",
               f"| 접근 IK 1회 | {sec['latency_ms']['ik_approach']:.1f} ms |", ""]

    run1 = S["runs"][off_dirs[0].name]
    if len(off_dirs) > 1:
        base_ok = {r["trial_id"]: r["success"] for r in _read_trials(off_dirs[0])}
        md += [f"## {off_dirs[0].name}과 이후 실행 비교", "",
               "공식 결과를 본 뒤 고친 내용과 이유는 `results/CHANGELOG.md`에 있다. 위에 모든 run을 그대로 적었다.", "",
               f"| run | 커밋 | 전체 | 기본 | 변화 | 명령 점검 | {off_dirs[0].name}과 success 열 |", "|---|---|---|---|---|---|---|"]
        S["run_compare"] = {}
        for d in off_dirs:
            sec = S["runs"][d.name]
            ok = {r["trial_id"]: r["success"] for r in _read_trials(d)}
            diff = [k for k in base_ok if base_ok.get(k) != ok.get(k)] + [k for k in ok if k not in base_ok]
            S["run_compare"][d.name] = {"success_equal": not diff, "diff_ids": diff}
            same = f"같음 ({len(base_ok)}/{len(base_ok)} 일치)" if not diff else f"다름: {', '.join(diff)}"
            md.append(f"| {d.name} | {sec['git_commit']} | {sec['all']['k']}/{sec['all']['n']} | {sec['basic']['k']}/{sec['basic']['n']} | "
                      f"{sec['variation']['k']}/{sec['variation']['n']} | {sec['checks']['k']}/{sec['checks']['n']} | "
                      f"{'기준' if d == off_dirs[0] else same} |")
        md += [""]

    # 재현 확인
    if rerun_rows is not None:
        r1 = {r["trial_id"]: r["success"] for r in _read_trials(off_dirs[0])}
        rr = {r["trial_id"]: r["success"] for r in rerun_rows}
        same = r1 == rr
        S["rerun_success_equal"] = same
        md += ["## 재현 확인", "",
               f"- `eval.py official --out results/rerun`의 success 열이 `{off_dirs[0].name}`과 "
               + ("같다 (25/25 일치)." if same else f"다르다: {[k for k in r1 if r1.get(k) != rr.get(k)]}"), ""]

    # PC 사양
    if sysinfo:
        md += ["## 추론 PC 사양", "", "| 항목 | 값 |", "|---|---|",
               f"| 기기 | {sysinfo.get('model', '')} |", f"| CPU | {sysinfo.get('cpu')} ({sysinfo.get('cpu_cores_physical')}코어) |",
               f"| 메모리 | {sysinfo.get('memory_gb')} GB |", f"| GPU | {sysinfo.get('gpu')} |",
               f"| GPU 사용 | {sysinfo.get('gpu_use')} |",
               f"| OS | macOS {sysinfo.get('macos', '')} ({sysinfo.get('os')}) |", f"| Python | {sysinfo.get('python')} |",
               "| 패키지 | " + ", ".join(f"{k} {v}" for k, v in sysinfo.get("packages", {}).items()) + " |", ""]

    # 기준선 대비
    md += ["## 기준선 대비 개선량", ""]
    if base_rows is not None:
        bsec = _section_run("baseline_run1", base_rows)
        S["baseline"] = bsec
        md += ["### 고정 좌표 기준선 (`baseline_fixed`, 인식 없이 기준 위치 좌표로 누름)", "",
               "| 구분 | 기준선 | 본 방법 (run1) | 차이 |", "|---|---|---|---|"]
        for key, name in (("all", "전체"), ("basic", "기본"), ("variation", "변화")):
            md.append(f"| {name} | {_rate_str(bsec[key])} | {_rate_str(run1[key])} | "
                      f"{(run1[key]['rate'] - bsec[key]['rate']) * 100:+.0f}%p |")
        lines, detail, _ = _failure_table(base_rows)
        md += ["", "기준선 실패 유형:", ""] + lines + [""] + detail + [""]
    else:
        md += ["- 고정 좌표 기준선: 미실시", ""]
    md += ["### 명령 해석 기준선 (`digits_only`: 정규식 `(\\d+)\\s*층`의 첫 일치)", "",
           "| 문장 집합 | 본 해석 | digits_only | 차이 | 눌러선 안 되는 문장의 PRESS (본 해석 / digits_only) |", "|---|---|---|---|---|"]
    for name, label in (("dev", "dev"), ("holdout", "holdout"), ("team", "team")):
        v = nlu_sum.get(name)
        if isinstance(v, dict):
            md.append(f"| {label} ({v['n']}문장) | {v['correct']}/{v['n']} | {v['baseline_correct']}/{v['n']} | "
                      f"{(v['correct'] - v['baseline_correct']) / v['n'] * 100:+.0f}%p | {v['false_press']} / {v['baseline_false_press']} |")
        else:
            md.append(f"| {label} | 미실시 | 미실시 | | |")
    hold = nlu_sum.get("holdout")
    md += ["", "- dev 문장은 해석 규칙을 맞추는 데 쓴 문장이다.",
           ("- holdout은 '구현 단계에서 보지 않은 문장'이다. 이 문장들은 계획서를 만들 때 시제품 점검에 쓰였으므로 "
            "규칙 설계와 무관한 문장이라고 보지는 않는다. 한 번만 실행했고 결과를 보고 규칙을 고치지 않았다."
            if isinstance(hold, dict) else
            "- holdout: `data/commands_holdout.tsv`를 받지 못해 미실시."),
           "- team 문장: 없음(미실시).", ""]
    for name in ("holdout", "team"):
        path = RESULTS / "nlu" / f"{name}.csv"
        if isinstance(nlu_sum.get(name), dict) and path.exists():
            with open(path, encoding="utf-8") as f:
                wrong = [r for r in csv.DictReader(f) if r["correct"] != "1"]
            md += [f"{name}에서 틀린 문장 ({len(wrong)}건, 결과를 보고 규칙을 고치지 않음):", ""]
            md += [f"- '{r['text']}': 기대 {r['expected_action']}{('(' + r['expected_floor'] + ')') if r['expected_floor'] else ''}, "
                   f"결과 {r['action']}{('(' + r['floor'] + ')') if r['floor'] else ''}, 사건 {r['events']}"
                   + (" — 움직이지 않음" if r["action"] != "PRESS" else "") for r in wrong] or ["- 없음"]
            md += [""]

    # 추가 시험
    if supp_rows is not None:
        ssec = _section_run("supplementary", supp_rows)
        S["supplementary"] = ssec
        lines, detail, _ = _failure_table(supp_rows)
        md += ["## 추가 시험 200회 (공식 결과와 별도)", "", "| 구분 | 성공 |", "|---|---|",
               f"| 전체 (200회) | {_rate_str(ssec['all'])} |", f"| 기본 (100회, 시드 3001~3100) | {_rate_str(ssec['basic'])} |",
               f"| 변화 (100회, 시드 4001~4100) | {_rate_str(ssec['variation'])} |",
               f"| 일반화 격차 | {ssec['gap_pp']:+.0f}%p |", "", "실패 유형:", ""] + lines + [""] + detail + [""]

    md += ["## 학습", "", "- 직접 학습한 모델: 해당 없음.",
           "- 사전 학습 모델: kiwipiepy (Kiwi 한국어 형태소 분석기)에 들어 있는 모델 "
           f"(kiwipiepy {sysinfo.get('packages', {}).get('kiwipiepy', '')}, kiwipiepy_model {sysinfo.get('packages', {}).get('kiwipiepy_model', '')}). "
           "형태소 분리에만 쓰고 판단은 규칙으로 한다.", ""]

    (RESULTS / "summary.json").write_text(json.dumps(S, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTS / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["protocol", "official", "baseline", "supplementary", "nlu", "summary"])
    ap.add_argument("--out", help="결과 폴더 (official·baseline·supplementary)")
    args = ap.parse_args()
    {"protocol": cmd_protocol, "official": cmd_official, "baseline": cmd_baseline,
     "supplementary": cmd_supplementary, "nlu": cmd_nlu, "summary": cmd_summary}[args.what](args)


if __name__ == "__main__":
    main()
