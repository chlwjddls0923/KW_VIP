"""3단계: 같은 (모델, 변형)의 두 실행에서 원시 출력이 문장마다 같은지 비교한다.

  .venv-llm/bin/python experiments/llm/compare_runs.py qwen35-4b A metal cpu1
출력: 같은 수/전체, 다른 문장 목록(첫 5개)을 표준 출력과 results/exp_llm/compare_{모델}_{변형}_{a}_vs_{b}.json에
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT  # noqa: E402


def load(name, v, tag):
    fn = OUT / (f"raw_{name}_{v}.jsonl" if tag == "metal" else f"raw_{name}_{v}_{tag}.jsonl")
    return {r["text"]: r for r in map(json.loads, open(fn, encoding="utf-8"))}


name, v, a, b = sys.argv[1:5]
A, B = load(name, v, a), load(name, v, b)
diff = [{"text": t, a: A[t]["raw"], b: B.get(t, {}).get("raw"), "parsed_same": A[t]["parsed"] == B.get(t, {}).get("parsed")}
        for t in A if A[t]["raw"] != B.get(t, {}).get("raw")]
res = {"model": name, "variant": v, "a": a, "b": b, "n": len(A), "n_b": len(B), "raw_same": len(A) - len(diff),
       "parsed_same": len(A) - sum(1 for d in diff if not d["parsed_same"]), "diff": diff}
(OUT / f"compare_{name}_{v}_{a}_vs_{b}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{name} {v} {a} vs {b}: raw 같음 {res['raw_same']}/{res['n']}, 파싱 결과 같음 {res['parsed_same']}/{res['n']}")
for d in diff[:5]:
    print("  ", d)
