"""1단계 확인: GGUF 로드와 JSON 스키마 강제 출력.

  .venv-llm/bin/python experiments/llm/smoke_load.py models/Qwen_Qwen3.5-2B-Q4_K_M.gguf [--gpu -1|0]

평가 파일(dev, adv_dev, holdout, adv_test)의 문장은 쓰지 않는다. 시험 문장 3개는 여기서 새로 쓴 것이다.
결과는 results/exp_llm/step1_smoke_{파일 이름}_{gpu}.json에 저장한다.
"""
import argparse
import hashlib
import json
import os
import platform
import time
from pathlib import Path

import jinja2
import llama_cpp
import psutil
from llama_cpp import Llama, LlamaGrammar

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "exp_llm"

SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["press_now", "wait", "not_command", "unclear"]},
        "floor_type": {"type": "string", "enum": ["number", "highest", "lowest", "relative", "none"]},
        "base": {"type": "integer"},
        "offset": {"type": "integer"},
    },
    "required": ["intent", "floor_type", "base", "offset"],
    "additionalProperties": False,
}
SYSTEM = ("엘리베이터 안에서 로봇팔에게 하는 말을 분류한다. JSON만 출력한다. "
          "intent: press_now(지금 버튼을 누르라는 요청), wait(기다리라는 요청), not_command(명령이 아님), unclear(알 수 없음). "
          "floor_type: number면 base가 층, 쓰지 않는 값은 0.")
TESTS = ["오늘 날씨 좋네", "5번 버튼 부탁해", "잠깐 기다려 봐"]   # 1단계 확인용으로 새로 쓴 문장


def render(llm, user, enable_thinking=False):
    tpl = llm.metadata["tokenizer.chat_template"]
    env = jinja2.Environment(loader=jinja2.BaseLoader(), trim_blocks=True, lstrip_blocks=True)
    env.globals["raise_exception"] = lambda m: (_ for _ in ()).throw(ValueError(m))
    return env.from_string(tpl).render(
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        add_generation_prompt=True, enable_thinking=enable_thinking, tools=None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gguf")
    ap.add_argument("--gpu", type=int, default=-1)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    path = ROOT / args.gguf
    proc = psutil.Process()
    rss0 = proc.memory_info().rss

    t = time.perf_counter()
    llm = Llama(str(path), n_ctx=2048, n_threads=args.threads, n_gpu_layers=args.gpu, seed=0, verbose=False)
    load_s = time.perf_counter() - t
    grammar = LlamaGrammar.from_json_schema(json.dumps(SCHEMA), verbose=False)

    runs = []
    for text in TESTS:
        prompt = render(llm, text)
        t = time.perf_counter()
        out = llm.create_completion(prompt, max_tokens=96, temperature=0.0, seed=0, grammar=grammar)
        dt = time.perf_counter() - t
        raw = out["choices"][0]["text"]
        try:
            parsed, ok = json.loads(raw), True
        except json.JSONDecodeError:
            parsed, ok = None, False
        runs.append({"text": text, "raw": raw, "json_ok": ok, "parsed": parsed, "seconds": round(dt, 3),
                     "finish_reason": out["choices"][0]["finish_reason"],
                     "prompt_tail": prompt[-40:]})
        print(f"{text!r} -> {raw}  ({dt:.2f} s)")

    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    res = {"gguf": args.gguf, "sha256": sha, "bytes": path.stat().st_size,
           "architecture": llm.metadata.get("general.architecture"),
           "llama_cpp_python": llama_cpp.__version__, "n_ctx": 2048, "n_threads": args.threads,
           "n_gpu_layers": args.gpu, "load_s": round(load_s, 3),
           "rss_after_mb": round(proc.memory_info().rss / 2**20, 1), "rss_before_mb": round(rss0 / 2**20, 1),
           "thinking": "chat template에 enable_thinking=False를 넘겨 '<think>\\n\\n</think>\\n\\n'를 미리 붙임",
           "machine": platform.platform(), "cpu_count": os.cpu_count(), "runs": runs}
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"step1_smoke_{path.stem}_{'metal' if args.gpu != 0 else 'cpu'}.json"
    (OUT / name).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"load {load_s:.2f} s, RSS {res['rss_after_mb']} MB, json_ok {[r['json_ok'] for r in runs]} → {name}")


if __name__ == "__main__":
    main()
