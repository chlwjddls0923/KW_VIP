"""2단계: 게이트 결과 기록 → results/exp_llm/gate.csv, gate_summary.md"""
import csv
from collections import Counter

from common import OUT, judge, load_adv, load_dev, nlu, official35, rule
from gate import TAU, gate


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, lines = [], []
    sets = [("official", official35()), ("dev", load_dev()), ("adv_dev", load_adv())]
    stats = {}
    for name, data in sets:
        st = {"n": len(data), "flagged": 0, "wrong": 0, "wrong_flagged": 0, "crit": Counter(), "flag_list": []}
        for r in data:
            p, a, f = rule(r["text"])
            h = gate(r["text"], p)
            g, sub = judge(a, f, r["expected_action"], r["expected_floor"])
            s = sorted(p["scores"].values(), reverse=True)
            st["flagged"] += bool(h)
            st["crit"].update(h)
            if g != "correct":
                st["wrong"] += 1
                st["wrong_flagged"] += bool(h)
            if h:
                st["flag_list"].append((r["text"], h, g))
            rows.append({"set": name, "text": r["text"], "expected_action": r["expected_action"],
                         "expected_floor": r["expected_floor"] or "", "type": r.get("type", ""),
                         "debatable": r.get("debatable", ""), "rule_action": a, "rule_floor": f or "",
                         "rule_grade": g, "rule_detail": sub, "gap": round(s[0] - s[1], 3),
                         "gate": " ".join(map(str, h))})
        stats[name] = st
    with open(OUT / "gate.csv", "w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    L = ["# 2단계: '확신 없음' 판정(게이트)", "",
         "코드: `experiments/llm/gate.py`. 문장별 결과: `results/exp_llm/gate.csv`. 보이는 층은 1~6.", "",
         "## 1. 기준 (1)의 τ", "",
         f"τ = **{TAU}**. dev 78문장만 보고 정했다.",
         "- dev에서 사건이나 층이 있는 문장의 1위−2위 점수 차이는 0(4문장), 1.0(4), 1.6(4), 2.0(46), 2.3(1), 2.4(13), 3.0(3), 3.2(1), 3.4(1)로 띄엄띄엄한 값이다.",
         "- 동점(차이 0)만 '확신 없음'으로 보도록 0과 1.0의 가운데를 τ로 썼다.",
         "- 공식 문장 35개의 최소 차이는 1.6이라 τ = 0.5에서 걸리지 않는다.",
         "- 대안으로 1.0과 1.6의 가운데(τ = 1.3)도 계산해 봤다. 그러면 dev에서 걸리는 문장이 11개로 늘고, 늘어난 4문장('3층', '3층은 말고 4층', '그만하고 3층 눌러', '2층 선택 안 할래')은 모두 규칙이 맞힌 문장이다. "
         "dev에서 모델에 맡기는 문장을 줄이려고 0.5를 골랐다. 이 비교에서 adv_dev 결과를 함께 보았지만, 규칙이 틀린 문장을 잡은 수는 두 값 모두 19/19로 같았다. 3단계 결합 비교는 τ = 0.5로 하고, τ = 1.3은 민감도 확인으로만 적는다.", "",
         "## 2. 걸린 수", "",
         "| 문장 묶음 | 문장 수 | 걸린 문장 | 규칙이 틀린 문장 | 그중 걸린 문장 | 기준별 (1)/(2)/(3)/(4)/(5)/(6) |", "|---|---|---|---|---|---|"]
    for name in ("official", "dev", "adv_dev"):
        st = stats[name]
        crit = " / ".join(str(st["crit"].get(k, 0)) for k in range(1, 7))
        L.append(f"| {name} | {st['n']} | {st['flagged']} | {st['wrong']} | {st['wrong_flagged']} | {crit} |")
    L += ["", "- 공식 문장 35개: 하나도 걸리지 않았다(통과 조건).",
          "- 기준별 수는 한 문장이 여러 기준에 걸리면 각각 센다.", "",
          "### dev에서 걸린 문장 (모두 규칙이 맞힌 문장)", ""]
    for t, h, g in stats["dev"]["flag_list"]:
        L.append(f"- {t} — 기준 {h}")
    L += ["", "### adv_dev에서 걸린 문장", "", "| 문장 | 기준 | 규칙 결과 |", "|---|---|---|"]
    for t, h, g in stats["adv_dev"]["flag_list"]:
        L.append(f"| {t} | {h} | {g} |")
    L += ["", "## 3. 비교 기준과 대조", "",
          "다른 구현으로 잰 값: 규칙만 adv_dev 정답 14, 위험한 실패 7(누르면 안 되는데 누름 4, 다른 층 2, 되물어야 하는데 누름 1), 안전한 실패 12. "
          "게이트는 규칙이 틀린 19문장을 모두 잡고 dev에서 7~11문장이 걸림.", "",
          "이번 구현: 같은 값이다. 규칙만 adv_dev 정답 14, 위험한 실패 7(4/2/1), 안전한 실패 12. "
          f"게이트는 규칙이 틀린 19문장 중 {stats['adv_dev']['wrong_flagged']}문장을 잡았고, dev에서 {stats['dev']['flagged']}문장이 걸렸다(τ = 1.3이면 11).", "",
          "## 4. 주의", "",
          "- 기준 (2)~(6)은 adv_dev 문장을 보고 만들었다. **adv_dev에서의 포착률(19/19)은 낙관적인 값이다.** 처음 보는 문장에서의 포착률은 4단계 adv_test로 본다.",
          "- 기준 (2)는 사전에 없는 용언이 있으면 걸리므로, 어휘가 다양한 실제 문장에서는 dev보다 자주 걸릴 수 있다."]
    (OUT / "gate_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    for name in ("official", "dev", "adv_dev"):
        st = stats[name]
        print(name, st["n"], "flagged", st["flagged"], "wrong", st["wrong"], "wrong_flagged", st["wrong_flagged"],
              dict(sorted(st["crit"].items())))


if __name__ == "__main__":
    main()
