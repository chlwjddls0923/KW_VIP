"""3단계: 저장한 원시 출력으로 결합 방식을 비교한다(모델을 다시 돌리지 않는다).

  .venv-llm/bin/python experiments/llm/combine.py            Metal 출력 전부
  .venv-llm/bin/python experiments/llm/combine.py --tag cpu1 CPU 출력이 있는 것만

출력: results/exp_llm/combos[_{tag}].csv, decisions/{모델}_{변형}[_{tag}].csv
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from common import EPS_RULE, OUT, SEEN, judge, load_adv, load_dev, nlu, official35, rule
from gate import gate
from models import CANDIDATES

METHODS = ["R", "M", "A-safe", "G-safe", "G-floor", "G-model"]
METHOD_RANK = {"G-safe": 0, "G-floor": 1, "G-model": 2, "A-safe": 3, "M": 4, "R": 5}
TYPES = ["neg2", "unreal", "floor", "vocab", "meta"]


def model_action(obj):
    """모델 답 → (행동, 층). press_now는 층을 코드로 계산하고 ground를 거친다."""
    if not isinstance(obj, dict):
        return "CLARIFY", None                                   # JSON 오류
    it = obj.get("intent")
    if it == "wait":
        return "WAIT", None
    if it == "not_command":
        return "REJECT", None
    if it != "press_now":
        return "CLARIFY", None                                   # unclear
    ft, base, off = obj.get("floor_type"), obj.get("base", 0), obj.get("offset", 0)
    if ft == "number":
        n = base
    elif ft == "highest":
        n = max(SEEN)
    elif ft == "lowest":
        n = min(SEEN)
    elif ft == "relative":
        n = base + off
    else:
        return "CLARIFY", None                                   # 층을 못 정함
    g = nlu.ground({"intent": "PRESS", "floor": n}, SEEN)
    return g["action"], g["floor"]


def g_safe(ra, rf, ma, mf):
    if ra != "PRESS" and ma == "PRESS":
        return "CLARIFY", None
    if ra == "PRESS" and ma != "PRESS":
        return ma, None
    if ra == "PRESS" and ma == "PRESS":
        return ("PRESS", rf) if rf == mf else ("CLARIFY", None)
    return ra, None


def rule_wanted_press_unresolved(p):
    """규칙이 누르기로 판단했지만 층을 하나로 못 정한 CLARIFY (판정 4단계의 CLARIFY)."""
    P, W, O = p["scores"]["PRESS"], p["scores"]["WAIT"], p["scores"]["OTHER"]
    stage2 = W >= P - 0.3 - EPS_RULE and W >= O - EPS_RULE
    stage3 = O > P + EPS_RULE
    return p["intent"] == "CLARIFY" and P >= 0.4 - EPS_RULE and not stage2 and not stage3 and len(p["candidates"]) != 1


def decide(method, p, ra, rf, hits, ma, mf):
    gated = bool(hits)
    if method == "R":
        return ra, rf
    if method == "M":
        return ma, mf
    if method == "A-safe":
        return g_safe(ra, rf, ma, mf)
    if not gated:
        return ra, rf
    if method == "G-model":
        return ma, mf
    if method == "G-floor":
        if ra == "PRESS" and 4 in hits and ma == "PRESS" and mf != rf:
            return "PRESS", mf                                   # (a)
        if ma == "PRESS" and rule_wanted_press_unresolved(p):
            return "PRESS", mf                                   # (b)
    return g_safe(ra, rf, ma, mf)                                # G-safe와 G-floor의 나머지


def raw_path(name, v, tag):
    return OUT / (f"raw_{name}_{v}.jsonl" if tag == "metal" else f"raw_{name}_{v}_{tag}.jsonl")


def evaluate(name, v, tag, tau=None):
    raw = {}
    with open(raw_path(name, v, tag), encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            raw[r["text"]] = r
    data = {"dev": load_dev(), "adv_dev": load_adv(), "official": official35()}
    res = {m: {} for m in METHODS}
    rows_out = []
    official_same = {m: True for m in METHODS}
    for set_name, rows in data.items():
        for m in METHODS:
            res[m][set_name] = Counter()
        for r in rows:
            p, ra, rf = rule(r["text"])
            hits = gate(r["text"], p) if tau is None else gate(r["text"], p, tau=tau)
            rec = raw.get(r["text"])
            ma, mf = model_action(rec["parsed"]) if rec else ("CLARIFY", None)
            out = {"set": set_name, "text": r["text"], "expected": f"{r['expected_action']}({r['expected_floor'] or ''})",
                   "type": r.get("type", ""), "debatable": r.get("debatable", ""), "gate": " ".join(map(str, hits)),
                   "rule": f"{ra}({rf or ''})", "model": f"{ma}({mf or ''})", "model_raw": rec["raw"] if rec else ""}
            for m in METHODS:
                a, fl = decide(m, p, ra, rf, hits, ma, mf)
                g, sub = judge(a, fl, r["expected_action"], r["expected_floor"])
                c = res[m][set_name]
                c[g] += 1
                if sub:
                    c[sub] += 1
                if set_name == "adv_dev":
                    c[f"{r['type']}:{g}"] += 1
                    if not r["debatable"]:
                        c[f"nodeb:{g}"] += 1
                if set_name == "official" and (a, fl) != (ra, rf):
                    official_same[m] = False
                out[m] = f"{a}({fl or ''})"
                out[m + "_grade"] = g
            rows_out.append(out)
    return res, official_same, rows_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="metal")
    ap.add_argument("--tau", type=float, default=None, help="민감도 확인용 τ (기본: gate.TAU)")
    args = ap.parse_args()
    suffix = ("" if args.tag == "metal" else f"_{args.tag}") + (f"_tau{args.tau}" if args.tau else "")
    (OUT / "decisions").mkdir(parents=True, exist_ok=True)
    table = []
    for key, c in CANDIDATES.items():
        for v in ("A", "B"):
            if not raw_path(c["name"], v, args.tag).exists():
                continue
            res, same, rows = evaluate(c["name"], v, args.tag, args.tau)
            with open(OUT / "decisions" / f"{c['name']}_{v}{suffix}.csv", "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            for m in METHODS:
                d, a, o = res[m]["dev"], res[m]["adv_dev"], res[m]["official"]
                row = {"model": key, "name": c["name"], "variant": v, "method": m, "bytes": c["bytes"],
                       "dev_correct": d["correct"], "dev_dangerous": d["dangerous"], "dev_safe": d["safe"],
                       "adv_correct": a["correct"], "adv_dangerous": a["dangerous"], "adv_safe": a["safe"],
                       "adv_nodeb_correct": a["nodeb:correct"], "adv_nodeb_dangerous": a["nodeb:dangerous"],
                       "adv_nodeb_safe": a["nodeb:safe"],
                       "official_correct": o["correct"], "official_same_as_R": same[m],
                       "adv_press_should_not": a["press_should_not"], "adv_wrong_floor": a["wrong_floor"],
                       "adv_press_should_clarify": a["press_should_clarify"],
                       "dev_press_should_not": d["press_should_not"], "dev_wrong_floor": d["wrong_floor"],
                       "dev_press_should_clarify": d["press_should_clarify"]}
                for t in TYPES:
                    row[f"adv_{t}"] = f"{a[t + ':correct']}/{a[t + ':dangerous']}/{a[t + ':safe']}"
                table.append(row)
    with open(OUT / f"combos{suffix}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)

    def rank_key(r):
        return (r["dev_dangerous"] + r["adv_dangerous"] > 0, not r["official_same_as_R"], r["dev_correct"] != 78,
                -r["adv_correct"], r["bytes"], METHOD_RANK[r["method"]])
    cand = sorted([r for r in table if r["model"] != "D" and r["method"] != "R"], key=rank_key)
    print(f"{'model':6}{'v':3}{'method':9}{'dev(c/d/s)':14}{'adv(c/d/s)':14}{'off=R':6}")
    for r in sorted(table, key=rank_key):
        print(f"{r['name']:13}{r['variant']:3}{r['method']:9}"
              f"{r['dev_correct']}/{r['dev_dangerous']}/{r['dev_safe']:<9}"
              f"{r['adv_correct']}/{r['adv_dangerous']}/{r['adv_safe']:<9}{str(r['official_same_as_R']):6}")
    print("상위:", [(r["name"], r["variant"], r["method"]) for r in cand[:5]])


if __name__ == "__main__":
    main()
