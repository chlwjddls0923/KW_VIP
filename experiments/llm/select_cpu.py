"""3단계: CPU 재실행 대상 (모델, 변형) 2개를 combos.csv에서 고른다 (사용자 지시 2026-11-24).

- 결합 방식은 저장한 출력으로 계산하므로 같은 (모델, 변형)의 여러 결합 방식은 1개로 센다.
- PLAN 추천 순서 ①~⑤: ① dev·adv_dev 위험한 실패 0 ② 공식 35개가 R과 같음 ③ dev 정답 78
  ④ adv_dev 정답 최대 ⑤ 작은 모델, 모델에 덜 맡기는 방식(G-safe, G-floor, G-model 순).
- ①~③을 통과한 (모델, 변형)을 가장 좋은 결합 방식 기준으로 줄 세워 앞에서 2개.
- 통과한 것이 2개보다 적으면(0개 포함) 나머지는 '위험한 실패 합이 가장 적고, 그다음 adv_dev 정답이 가장 많은 것'으로
  채우고 '①~③ 미통과'로 표시한다. 그래도 같으면 ② → ③(dev 정답 수) → ⑤ 순. D(9B)와 R은 대상에서 뺀다.

  .venv-llm/bin/python experiments/llm/select_cpu.py   → results/exp_llm/cpu_selection.json
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from combine import METHOD_RANK  # noqa: E402
from common import OUT  # noqa: E402


def load():
    rows = list(csv.DictReader(open(OUT / "combos.csv", encoding="utf-8")))
    for r in rows:
        for k in ("bytes", "dev_correct", "dev_dangerous", "adv_correct", "adv_dangerous"):
            r[k] = int(r[k])
        r["official_same_as_R"] = r["official_same_as_R"] == "True"
        r["danger"] = r["dev_dangerous"] + r["adv_dangerous"]
        r["pass123"] = r["danger"] == 0 and r["official_same_as_R"] and r["dev_correct"] == 78
    return [r for r in rows if r["model"] != "D" and r["method"] != "R"]


def plan_key(r):
    return (not r["pass123"], -r["adv_correct"], r["bytes"], METHOD_RANK[r["method"]])


def fallback_key(r):
    # 사용자 기준: 위험한 실패 합 최소 → adv_dev 정답 최대. 그래도 같으면 PLAN 순서대로
    # ② 공식 35개 = R → ③ dev 정답 수(많을수록) → ⑤ 파일 크기 → 변형 A(최대 96토큰, 더 빠름) → 덜 맡기는 방식
    return (r["danger"], -r["adv_correct"], not r["official_same_as_R"], -r["dev_correct"],
            r["bytes"], r["variant"], METHOD_RANK[r["method"]])


def main():
    rows = load()
    pairs = {}
    for r in rows:
        pairs.setdefault((r["name"], r["variant"]), []).append(r)
    passed = sorted((min((r for r in rs if r["pass123"]), key=plan_key) for rs in pairs.values()
                     if any(r["pass123"] for r in rs)), key=plan_key)
    chosen = [dict(pick=r, why="①~③ 통과, 가장 좋은 결합 방식 기준 PLAN 순서 ④⑤") for r in passed[:2]]
    if len(chosen) < 2:
        used = {(c["pick"]["name"], c["pick"]["variant"]) for c in chosen}
        rest = sorted((min(rs, key=fallback_key) for k, rs in pairs.items() if k not in used), key=fallback_key)
        for r in rest[:2 - len(chosen)]:
            chosen.append(dict(pick=r, why="①~③ 미통과: 위험한 실패 합 최소, 그다음 adv_dev 정답 최대"))
    out = []
    for c in chosen:
        r = c["pick"]
        out.append({"model": r["model"], "name": r["name"], "variant": r["variant"], "best_method": r["method"],
                    "dev": f"{r['dev_correct']}/{r['dev_dangerous']}/{r['dev_safe']}",
                    "adv_dev": f"{r['adv_correct']}/{r['adv_dangerous']}/{r['adv_safe']}",
                    "official_same_as_R": r["official_same_as_R"], "pass123": r["pass123"], "why": c["why"]})
    out_all = [{"name": k[0], "variant": k[1], "pass123_methods": [r["method"] for r in rs if r["pass123"]]}
               for k, rs in sorted(pairs.items())]
    res = {"n_pairs_pass123": len(passed), "chosen": out, "all_pairs": out_all}
    (OUT / "cpu_selection.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
