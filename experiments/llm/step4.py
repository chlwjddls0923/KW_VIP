"""4단계: 한 번만 하는 최종 확인. 선택 조합 gemma4-e2b × A × G-floor (CPU) 와 R.

  .venv-llm/bin/python experiments/llm/step4.py freeze   실행 전 동결 값 → results/exp_llm/step4_freeze.json
  .venv-llm/bin/python experiments/llm/step4.py run      모델 실행(세트마다 한 번) → raw_step4_gemma4-e2b_A_{세트}.jsonl, step4_run.json
  .venv-llm/bin/python experiments/llm/step4.py report   저장한 출력으로 결합·채점 → step4_decisions.csv, step4.md

채점(사용자가 미리 정함, 바꾸지 않음)
- 엄격(strict): 기대 행동과 정확히 같아야 정답(PRESS는 층까지). 기대가 NOMOVE이면 움직이지 않는 행동이 정답(NOMOVE는 행동 이름이 아님).
- 3단계 방식(lenient): 기대가 WAIT·REJECT·NOMOVE이면 WAIT·REJECT·CLARIFY 모두 정답, 기대가 CLARIFY면 CLARIFY만 정답.
  (주의: 실제 3단계 코드 common.judge는 기대가 NOMOVE일 때만 너그럽게 봤다. 4단계는 사용자 정의를 따른다.)
- 위험한 실패(두 방식 같음): 기대가 PRESS가 아닌데 PRESS(누르면 안 되는데 누름 / 되물어야 하는데 누름), 기대와 다른 층 PRESS(다른 층).
"""
import csv
import hashlib
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import DATA, OUT, ROOT, _floor, nlu, rule  # noqa: E402
from combine import decide, g_safe, model_action, rule_wanted_press_unresolved  # noqa: E402
import gate as gate_mod  # noqa: E402
from gate import gate  # noqa: E402
from models import CANDIDATES, path  # noqa: E402

KEY, NAME, VARIANT, METHOD = "E", "gemma4-e2b", "A", "G-floor"
GPU, THREADS = 0, 4
SETS = {"holdout": "commands_holdout.tsv", "adv_test": "commands_adv_test.tsv"}
FREEZE_FILES = ["src/assist/nlu.py", "experiments/llm/gate.py", "experiments/llm/combine.py",
                "experiments/llm/common.py", "experiments/llm/run_model.py", "experiments/llm/models.py",
                "experiments/llm/step4.py", "data/commands_holdout.tsv"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_set(name):
    fn = DATA / SETS[name]
    if not fn.exists():
        return None
    if name == "holdout":                                         # 머리글 없음: text, action, floor
        rows = []
        for line in open(fn, encoding="utf-8"):
            line = line.rstrip("\n")
            if line:
                t, a, fl = line.split("\t")
                rows.append({"text": t, "expected_action": a, "expected_floor": _floor(fl), "set": name})
        return rows
    rows = []                                                     # adv_test: adv_dev와 같은 열
    for r in csv.DictReader(open(fn, encoding="utf-8"), delimiter="\t"):
        rows.append({"text": r["text"], "expected_action": r["expected_action"],
                     "expected_floor": _floor(r["expected_floor"]), "type": r["type"],
                     "debatable": int(r["debatable"]), "set": name})
    return rows


# ---------------------------------------------------------------- 채점
def danger(a, f, ea, ef):
    if a != "PRESS":
        return None
    if ea == "PRESS":
        return None if f == ef else "다른 층"
    return "되물어야 하는데 누름" if ea == "CLARIFY" else "누르면 안 되는데 누름"


def grade(a, f, ea, ef, mode):
    d = danger(a, f, ea, ef)
    if d:
        return "dangerous", d
    if ea == "PRESS":
        return ("correct", "") if a == "PRESS" else ("safe", "")
    if mode == "lenient" and ea in ("WAIT", "REJECT", "NOMOVE"):
        return "correct", ""                                      # 움직이지 않는 행동은 모두 정답
    if ea == "NOMOVE":
        return "correct", ""                                      # 엄격에서도 NOMOVE는 움직이지 않으면 정답
    return ("correct", "") if a == ea else ("safe", "")


def g_floor_path(p, ra, rf, hits, ma, mf):
    """G-floor 결정과 그 경로. combine.decide와 같은 결과인지 확인한다."""
    if not hits:
        out = (ra, rf, "게이트 안 걸림(규칙)")
    elif ra == "PRESS" and 4 in hits and ma == "PRESS" and mf != rf:
        out = ("PRESS", mf, "G-floor (a)")
    elif ma == "PRESS" and rule_wanted_press_unresolved(p):
        out = ("PRESS", mf, "G-floor (b)")
    else:
        a, f = g_safe(ra, rf, ma, mf)
        out = (a, f, "G-safe 규칙")
    assert out[:2] == decide(METHOD, p, ra, rf, hits, ma, mf)
    return out


# ---------------------------------------------------------------- freeze
def cmd_freeze():
    import subprocess
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    files = {f: sha(ROOT / f) for f in FREEZE_FILES}
    for d in ("experiments/llm/prompts", "experiments/llm/templates"):
        for p in sorted((ROOT / d).iterdir()):
            files[f"{d}/{p.name}"] = sha(p)
    from run_model import MAX_TOKENS, N_CTX, SEED
    c = CANDIDATES[KEY]
    fz = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "commit": head, "uncommitted_at_freeze": dirty.splitlines(),
          "combo": {"model": NAME, "key": KEY, "variant": VARIANT, "method": METHOD},
          "tau": gate_mod.TAU, "n_ctx": N_CTX, "n_threads": THREADS, "n_threads_batch": THREADS, "n_gpu_layers": GPU,
          "seed": SEED, "temperature": 0.0, "top_k": 1, "max_tokens": MAX_TOKENS[VARIANT],
          "model_file": c["file"], "model_repo": c["repo"], "model_rev": c["rev"],
          "model_sha256_expected": c["sha256"], "model_sha256_local": sha(path(KEY)),
          "files_sha256": files,
          "adv_test": "있음" if (DATA / SETS["adv_test"]).exists() else "없음(미실시)"}
    fz["model_sha256_match"] = fz["model_sha256_local"] == fz["model_sha256_expected"]
    (OUT / "step4_freeze.json").write_text(json.dumps(fz, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in fz.items() if k != "files_sha256"}, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- run (한 번만)
def cmd_run():
    from llama_cpp import LlamaGrammar
    import llama_cpp
    from run_model import MAX_TOKENS, PROMPTS, SANITY, Runner, parse_raw, schema
    sets = {k: load_set(k) for k in SETS}
    for k, rows in sets.items():
        fn = OUT / f"raw_step4_{NAME}_{VARIANT}_{k}.jsonl"
        if rows is not None and fn.exists():
            sys.exit(f"{fn.name}가 이미 있다. 4단계는 한 번만 실행한다.")
    info = {"model": KEY, "name": NAME, "variant": VARIANT, "llama_cpp_python": llama_cpp.__version__,
            "n_gpu_layers": GPU, "n_threads": THREADS, "start": time.strftime("%Y-%m-%d %H:%M:%S")}
    r = Runner(KEY, GPU, THREADS)
    info["load_s"] = round(r.load_s, 3)
    san = []
    for q in SANITY:                                              # 3단계 CPU 실행과 같은 정상 출력 확인
        text, fin, dt, _ = r.generate(r.tokens(r.render(None, q)), 80)
        san.append({"q": q, "answer": text, "finish": fin, "seconds": round(dt, 3)})
    info["sanity"] = san
    system = (PROMPTS / f"system_{VARIANT}.txt").read_text(encoding="utf-8").strip()
    grammar = LlamaGrammar.from_json_schema(json.dumps(schema(VARIANT)), verbose=False)
    info["sets"] = {}
    for k, rows in sets.items():
        if rows is None:
            info["sets"][k] = "미실시(파일 없음)"
            continue
        info[f"token_check_{k}"] = r.token_check(r.render(system, rows[0]["text"]))
        with open(OUT / f"raw_step4_{NAME}_{VARIANT}_{k}.jsonl", "w", encoding="utf-8") as fp:
            for i, row in enumerate(rows):
                text, fin, dt, usage = r.generate(r.tokens(r.render(system, row["text"])), MAX_TOKENS[VARIANT], grammar)
                obj, keys, ok = parse_raw(text)
                fp.write(json.dumps({"i": i, "set": k, "text": row["text"], "raw": text, "json_ok": ok, "parsed": obj,
                                     "key_order": keys, "finish_reason": fin, "seconds": round(dt, 4),
                                     "prompt_tokens": usage["prompt_tokens"],
                                     "completion_tokens": usage["completion_tokens"]}, ensure_ascii=False) + "\n")
                print(f"  {k} {i}/{len(rows)} {dt:.2f}s {text[:80]}", flush=True)
        info["sets"][k] = len(rows)
    info["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 1)
    info["end"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (OUT / "step4_run.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print("peak RSS MB", info["peak_rss_mb"])


# ---------------------------------------------------------------- report
def med(xs):
    xs = sorted(xs)
    n = len(xs)
    return None if not n else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)


def fmt(a, f):
    return f"{a}({f if f is not None else ''})"


def cmd_report():
    run = json.loads((OUT / "step4_run.json").read_text(encoding="utf-8"))
    rows_out, md = [], []
    old = {r["text"]: r for r in csv.DictReader(open(ROOT / "results/nlu/holdout.csv", encoding="utf-8"))}
    md += ["# LLM 실험 4단계: 한 번만 하는 최종 확인", "",
           f"조합: **{NAME} × {VARIANT} × {METHOD}** (CPU, n_gpu_layers={GPU}, {THREADS}스레드)와 R(규칙만). "
           f"동결 값: `step4_freeze.json`. 실행: {run['start']} ~ {run['end']}.", "",
           "채점(미리 정함): **엄격** = 기대 행동과 정확히 같아야 정답. **3단계 방식** = 기대가 WAIT·REJECT·NOMOVE면 "
           "WAIT·REJECT·CLARIFY 모두 정답, 기대가 CLARIFY면 CLARIFY만 정답. 위험한 실패 정의는 같다.",
           "(참고: 실제 3단계 코드 `common.judge`는 기대가 NOMOVE일 때만 너그럽게 봤다. 3단계 표의 dev 수치는 엄격에 가깝다.)", ""]
    for k in SETS:
        rows = load_set(k)
        if rows is None:
            md += [f"## {k}", "", "**미실시** (`data/commands_adv_test.tsv` 없음).", ""]
            continue
        raw = {json.loads(l)["text"]: json.loads(l) for l in open(OUT / f"raw_step4_{NAME}_{VARIANT}_{k}.jsonl", encoding="utf-8")}
        recs = []
        for r in rows:
            p, ra, rf = rule(r["text"])
            hits = gate(r["text"], p)
            rec = raw[r["text"]]
            ma, mf = model_action(rec["parsed"])
            ca, cf, how = g_floor_path(p, ra, rf, hits, ma, mf)
            o = {"set": k, "text": r["text"], "expected": fmt(r["expected_action"], r["expected_floor"]),
                 "type": r.get("type", ""), "debatable": r.get("debatable", ""),
                 "gate": " ".join(map(str, hits)), "rule": fmt(ra, rf), "model": fmt(ma, mf), "model_raw": rec["raw"],
                 "json_ok": rec["json_ok"], "seconds": rec["seconds"], "combo": fmt(ca, cf), "combo_path": how}
            for mode in ("strict", "lenient"):
                o[f"R_{mode}"], _ = grade(ra, rf, r["expected_action"], r["expected_floor"], mode)
                o[f"combo_{mode}"], _ = grade(ca, cf, r["expected_action"], r["expected_floor"], mode)
            o["R_danger"] = danger(ra, rf, r["expected_action"], r["expected_floor"]) or ""
            o["combo_danger"] = danger(ca, cf, r["expected_action"], r["expected_floor"]) or ""
            if k == "holdout" and r["text"] in old:
                ob = old[r["text"]]
                o["holdout_old_action"] = fmt(ob["action"], _floor(ob["floor"]) if ob["floor"] else None)
            recs.append(o)
        rows_out += recs
        n = len(recs)
        md += [f"## {k} ({n}문장)", "", "### 결과 (정답/위험한 실패/안전한 실패)", "",
               "| 방식 | 엄격 | 3단계 방식 | 위험: 누르면 안 되는데 누름 / 다른 층 / 되물어야 하는데 누름 |", "|---|---|---|---|"]
        for who, col in (("R", "R"), (f"{NAME}·{VARIANT}·{METHOD}", "combo")):
            c = {m: Counter(o[f"{col}_{m}"] for o in recs) for m in ("strict", "lenient")}
            dc = Counter(o[f"{col}_danger"] for o in recs if o[f"{col}_danger"])
            md.append(f"| {who} | {c['strict']['correct']}/{c['strict']['dangerous']}/{c['strict']['safe']} | "
                      f"{c['lenient']['correct']}/{c['lenient']['dangerous']}/{c['lenient']['safe']} | "
                      f"{dc['누르면 안 되는데 누름']} / {dc['다른 층']} / {dc['되물어야 하는데 누름']} |")
        md.append("")
        if k == "holdout":
            same = sum(1 for o in recs if o.get("holdout_old_action") == o["rule"])
            old_ok = sum(1 for o in recs if old.get(o["text"], {}).get("correct") in ("True", "1", "true"))
            md += [f"- R 엄격 정답 {Counter(o['R_strict'] for o in recs)['correct']}/{n}. "
                   f"기존 룰기반 holdout(`results/nlu/holdout.csv`) 정답 {old_ok}/{n}, 문장별 행동이 같은 문장 {same}/{n}.", ""]
        if k == "adv_test":
            md += ["### type별 (조합, 3단계 방식 정답/위험/안전)", "", "| type | 문장 | R | 조합 |", "|---|---|---|---|"]
            for t in sorted({o["type"] for o in recs}):
                sub = [o for o in recs if o["type"] == t]
                cr = Counter(o["R_lenient"] for o in sub)
                cc = Counter(o["combo_lenient"] for o in sub)
                md.append(f"| {t} | {len(sub)} | {cr['correct']}/{cr['dangerous']}/{cr['safe']} | {cc['correct']}/{cc['dangerous']}/{cc['safe']} |")
            nd = [o for o in recs if not o["debatable"]]
            for m in ("strict", "lenient"):
                cr, cc = Counter(o[f"R_{m}"] for o in nd), Counter(o[f"combo_{m}"] for o in nd)
                md.append(f"- debatable 제외({len(nd)}문장, {m}): R {cr['correct']}/{cr['dangerous']}/{cr['safe']}, "
                          f"조합 {cc['correct']}/{cc['dangerous']}/{cc['safe']}")
            md.append("")
        # 위험한 실패 원인
        md += ["### 위험한 실패", "", "| 문장 | 기대 | 규칙 | 게이트 | 모델 출력 | 최종 | 원인 |", "|---|---|---|---|---|---|---|"]
        any_d = False
        for o in recs:
            if not o["combo_danger"]:
                continue
            any_d = True
            cause = {"게이트 안 걸림(규칙)": "게이트가 놓침", "G-safe 규칙": "게이트에 걸렸지만 모델도 틀린 PRESS",
                     "G-floor (a)": "G-floor (a)로 층이 바뀜", "G-floor (b)": "G-floor (b)로 층이 정해짐"}[o["combo_path"]]
            md.append(f"| {o['text']} | {o['expected']} | {o['rule']} | [{o['gate']}] | `{o['model_raw']}` | {o['combo']} ({o['combo_danger']}) | {cause} |")
        if not any_d:
            md.append("| (조합에서 위험한 실패 없음) | | | | | | |")
        rd = [o for o in recs if o["R_danger"]]
        md += ["", f"R의 위험한 실패 {len(rd)}건: " + ("; ".join(f"{o['text']} → {o['rule']} ({o['R_danger']})" for o in rd) or "없음"), ""]
        # 게이트
        gated = [o for o in recs if o["gate"]]
        md += ["### 게이트", "", f"- 걸린 문장 {len(gated)}/{n}"]
        for m, lab in (("strict", "엄격"), ("lenient", "3단계 방식")):
            wrong = [o for o in recs if o[f"R_{m}"] != "correct"]
            caught = [o for o in wrong if o["gate"]]
            md.append(f"- 규칙이 틀린 문장({lab}) {len(wrong)}, 그중 걸린 문장 {len(caught)}. 놓친 문장: "
                      + ("; ".join(f"{o['text']} (기대 {o['expected']}, 규칙 {o['rule']})" for o in wrong if not o["gate"]) or "없음"))
        md += ["", "| 걸린 문장 | 기준 | 기대 | 규칙 | 모델 | 조합 |", "|---|---|---|---|---|---|"]
        md += [f"| {o['text']} | [{o['gate']}] | {o['expected']} | {o['rule']} | {o['model']} | {o['combo']} |" for o in gated]
        # 모델 때문에 바뀐 문장
        rank = {"correct": 2, "safe": 1, "dangerous": 0}
        md += ["", "### 모델 때문에 결과가 바뀐 문장 (R → 조합)", "", "| 문장 | 기대 | R | 조합 | 엄격 | 3단계 방식 |", "|---|---|---|---|---|---|"]
        ch = [o for o in recs if o["rule"] != o["combo"]]
        for o in ch:
            def tag(m):
                a, b = rank[o[f"R_{m}"]], rank[o[f"combo_{m}"]]
                return "맞게" if b > a else ("틀리게" if b < a else f"같음({o[f'combo_{m}']})")
            md.append(f"| {o['text']} | {o['expected']} | {o['rule']} | {o['combo']} | {tag('strict')} | {tag('lenient')} |")
        if not ch:
            md.append("| (없음) | | | | | |")
        md.append("")
        # 시간
        secs = [o["seconds"] for o in recs]
        rest = secs[1:]
        g_rest = [o["seconds"] for o in recs[1:] if o["gate"]]
        md += ["### 시간 (모델 한 문장 생성, 첫 호출 제외)", "",
               f"- 전체 {len(rest)}문장: 중앙값 {med(rest):.3f} s, 최대 {max(rest):.3f} s (첫 호출 {secs[0]:.3f} s)",
               (f"- 게이트에 걸린 문장만 {len(g_rest)}문장: 중앙값 {med(g_rest):.3f} s, 최대 {max(g_rest):.3f} s" if g_rest else "- 게이트에 걸린 문장 없음"),
               f"- JSON 오류 {sum(1 for o in recs if not o['json_ok'])}건", ""]
    md += ["## 자원", "", f"- 로드 {run['load_s']} s, 최대 메모리(RSS) {run['peak_rss_mb']} MB",
           "- 정상 출력 확인: " + " / ".join(s["answer"].strip().replace("\n", " ")[:60] for s in run["sanity"]), "",
           "## 라벨 이의", "", "[결과 확인 후 기록. 라벨·채점은 고치지 않는다]", ""]
    with open(OUT / "step4_decisions.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0]) if rows_out else ["text"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)
    (OUT / "step4.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    {"freeze": cmd_freeze, "run": cmd_run, "report": cmd_report}[sys.argv[1]]()
