"""3단계: 후보 모델 하나를 실행해 원시 출력을 저장한다.

  .venv-llm/bin/python experiments/llm/run_model.py --model B --gpu -1 --tag metal
  .venv-llm/bin/python experiments/llm/run_model.py --model B --gpu 0 --tag cpu1 --variants A

한 프로세스에서 Llama 객체 하나를 만들어 모든 문장과 변형에 재사용한다.
문장마다 llm.reset()으로 이전 상태를 지워, 문장 순서가 결과에 영향을 주지 않게 한다.
출력:
  results/exp_llm/raw_{모델}_{변형}.jsonl            (tag가 metal일 때)
  results/exp_llm/raw_{모델}_{변형}_{tag}.jsonl      (그 밖)
  results/exp_llm/run_{모델}_{tag}.json              (설정, 로드 시간, 최대 메모리, 정상 출력·토큰 확인)
  results/exp_llm/rendered/{모델}_{변형}.txt         (enable_thinking=False 렌더링 예시)
"""
import argparse
import json
import re
import resource
import sys
import time
from collections import OrderedDict
from pathlib import Path

import jinja2
import jinja2.ext
import jinja2.nodes
import llama_cpp
from jinja2.sandbox import ImmutableSandboxedEnvironment
from llama_cpp import Llama, LlamaGrammar

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, load_adv, load_dev, official35  # noqa: E402
from models import CANDIDATES, path  # noqa: E402

PROMPTS = Path(__file__).resolve().parent / "prompts"
N_CTX = 4096
SEED = 0
MAX_TOKENS = {"A": 96, "B": 192}
BASE_PROPS = OrderedDict([
    ("intent", {"type": "string", "enum": ["press_now", "wait", "not_command", "unclear"]}),
    ("floor_type", {"type": "string", "enum": ["number", "highest", "lowest", "relative", "none"]}),
    ("base", {"type": "integer"}),
    ("offset", {"type": "integer"}),
])
# 정상 출력 확인: 문법 강제 없이 짧은 한국어 질문 3개 (평가 문장과 무관)
SANITY = ["대한민국의 수도는 어디인가요? 한 문장으로 답해 주세요.",
          "사과는 보통 무슨 색인가요? 한 문장으로 답해 주세요.",
          "엘리베이터는 어떤 일을 하는 기계인가요? 한 문장으로 답해 주세요."]
SPECIAL_RE = re.compile(r"<\|[^\s<>|]*\|>|<\|[A-Za-z_]+>|<[A-Za-z_]+\|>|</?[a-z_]+>|\[\|[a-z]+\|\]")


class GenerationTag(jinja2.ext.Extension):
    """HF 템플릿의 {% generation %}...{% endgeneration %} (학습용 assistant 마스크 표시).
    렌더링 결과에는 영향이 없으므로 본문을 그대로 출력한다(transformers의 AssistantTracker와 같은 출력)."""
    tags = {"generation"}

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        body = parser.parse_statements(("name:endgeneration",), drop_needle=True)
        return jinja2.nodes.Scope(body, lineno=lineno)


def schema(variant):
    props = OrderedDict()
    if variant == "B":
        props["reason"] = {"type": "string"}
    props.update(BASE_PROPS)
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def sentences():
    rows = load_dev() + load_adv()
    seen = {r["text"] for r in rows}
    rows += [r for r in official35() if r["text"] not in seen]   # 공식 문장 중 111문장에 없는 것
    return rows


class Runner:
    def __init__(self, key, gpu, threads, template_file=None):
        self.key, self.c = key, CANDIDATES[key]
        t = time.perf_counter()
        self.llm = Llama(str(path(key)), n_ctx=N_CTX, n_threads=threads, n_threads_batch=threads,
                         n_gpu_layers=gpu, seed=SEED, verbose=False)
        self.load_s = time.perf_counter() - t
        md = self.llm.metadata
        # --template: GGUF 안의 chat template 대신 파일의 템플릿을 쓴다(kanana: generation 태그만 지운 것)
        self.template = (Path(template_file).read_text(encoding="utf-8") if template_file
                         else md.get("tokenizer.chat_template", ""))
        self.add_bos = md.get("tokenizer.ggml.add_bos_token", "false") == "true"
        self.bos_id = self.llm.token_bos()
        self.bos_text = self._piece(self.bos_id) if self.bos_id >= 0 else ""
        self.eos_text = self._piece(self.llm.token_eos()) if self.llm.token_eos() >= 0 else ""
        env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True,
                                           extensions=["jinja2.ext.loopcontrols", GenerationTag])
        env.globals["raise_exception"] = self._raise
        env.globals["strftime_now"] = lambda fmt: time.strftime(fmt)
        self.tpl = env.from_string(self.template)
        self.system_merged = False

    @staticmethod
    def _raise(msg):
        raise jinja2.exceptions.TemplateError(msg)

    def _piece(self, tid):
        return self.llm.detokenize([tid], special=True).decode("utf-8", errors="replace")

    def render(self, system, user):
        kw = dict(add_generation_prompt=True, enable_thinking=False, bos_token=self.bos_text,
                  eos_token=self.eos_text, tools=None)
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        try:
            return self.tpl.render(messages=msgs, **kw)
        except jinja2.exceptions.TemplateError:
            if not system:
                raise
            self.system_merged = True                     # system 역할을 받지 않는 템플릿
            return self.tpl.render(messages=[{"role": "user", "content": system + "\n\n" + user}], **kw)

    def tokens(self, prompt):
        """템플릿 문자열을 특수 토큰 해석과 함께 토큰화. 템플릿에 BOS가 없고 모델이 BOS를 원하면 하나만 붙인다."""
        toks = self.llm.tokenize(prompt.encode("utf-8"), add_bos=False, special=True)
        if self.add_bos and (not toks or toks[0] != self.bos_id):
            toks = [self.bos_id] + toks
        return toks

    def token_check(self, prompt):
        toks = self.tokens(prompt)
        specials = sorted(set(SPECIAL_RE.findall(prompt)))
        single = {s: len(self.llm.tokenize(s.encode("utf-8"), add_bos=False, special=True)) == 1 for s in specials}
        # BOS를 쓰는 모델(add_bos_token=true)이거나 템플릿이 bos_token을 넣을 때만 BOS 개수가 의미 있다.
        # Qwen은 add_bos_token=false이고 token_bos()가 ','(11)를 돌려주므로 개수를 세지 않는다.
        bos_used = self.add_bos or ("bos_token" in self.template)
        return {"n_tokens": len(toks), "add_bos_token": self.add_bos, "template_uses_bos_token": "bos_token" in self.template,
                "bos_id": self.bos_id, "bos_text": self.bos_text,
                "bos_count_in_prompt": (sum(1 for t in toks if t == self.bos_id) if bos_used else "해당 없음(BOS 미사용)"),
                "starts_with_double_bos": len(toks) > 1 and toks[0] == self.bos_id and toks[1] == self.bos_id,
                "special_strings": specials, "special_single_token": single,
                "first10": [(t, self._piece(t)) for t in toks[:10]],
                "last10": [(t, self._piece(t)) for t in toks[-10:]]}

    def generate(self, toks, max_tokens, grammar=None):
        self.llm.reset()
        t = time.perf_counter()
        out = self.llm.create_completion(toks, max_tokens=max_tokens, temperature=0.0, top_k=1, top_p=1.0,
                                         min_p=0.0, repeat_penalty=1.0, seed=SEED, grammar=grammar)
        return out["choices"][0]["text"], out["choices"][0]["finish_reason"], time.perf_counter() - t, \
            out["usage"]


def parse_raw(raw):
    try:
        pairs = json.loads(raw, object_pairs_hook=lambda p: p)
        obj = dict(pairs)
        return obj, [k for k, _ in pairs], True
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, [], False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--gpu", type=int, default=-1)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--tag", default="metal")
    ap.add_argument("--variants", nargs="+", default=["A", "B"])
    ap.add_argument("--no-sanity", action="store_true")
    ap.add_argument("--template", default=None, help="chat template 파일 (기본: GGUF 안의 것)")
    ap.add_argument("--sanity-only", action="store_true", help="정상 출력·토큰 확인만 하고 평가 문장은 돌리지 않음")
    args = ap.parse_args()
    c = CANDIDATES[args.model]
    name = c["name"]
    info = {"model": args.model, "name": name, "file": c["file"], "repo": c["repo"], "bytes": path(args.model).stat().st_size,
            "llama_cpp_python": llama_cpp.__version__, "n_ctx": N_CTX, "n_threads": args.threads,
            "n_threads_batch": args.threads, "n_gpu_layers": args.gpu, "seed": SEED, "temperature": 0.0,
            "tag": args.tag, "variants": args.variants, "reset_each_call": True}
    if args.template:
        import hashlib
        info["template_file"] = args.template
        info["template_sha256"] = hashlib.sha256(Path(args.template).read_bytes()).hexdigest()
    try:
        r = Runner(args.model, args.gpu, args.threads, args.template)
    except Exception as e:
        info["load_error"] = f"{type(e).__name__}: {e}"
        (OUT / f"run_{name}_{args.tag}.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        print("LOAD FAILED", info["load_error"])
        sys.exit(2)
    info["load_s"] = round(r.load_s, 3)
    info["architecture"] = r.llm.metadata.get("general.architecture")
    info["template_has_enable_thinking"] = "enable_thinking" in r.template
    info["template_len"] = len(r.template)

    if not args.no_sanity:
        san = []
        for q in SANITY:
            toks = r.tokens(r.render(None, q))
            text, fin, dt, _ = r.generate(toks, 80)
            san.append({"q": q, "answer": text, "finish": fin, "seconds": round(dt, 3)})
            print("[정상 출력]", q, "→", text.strip().replace("\n", " ")[:160])
        info["sanity"] = san

    rows = sentences()
    if args.sanity_only:
        for v in args.variants:
            system = (PROMPTS / f"system_{v}.txt").read_text(encoding="utf-8").strip()
            example = r.render(system, rows[0]["text"])
            info[f"rendered_{v}"] = example
            info[f"token_check_{v}"] = r.token_check(example)
        info["system_merged_into_user"] = r.system_merged
        (OUT / f"run_{name}_{args.tag}.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        print("sanity-only 끝")
        return
    rend_dir = OUT / "rendered"
    rend_dir.mkdir(parents=True, exist_ok=True)
    info["timing"] = {}
    for v in args.variants:
        system = (PROMPTS / f"system_{v}.txt").read_text(encoding="utf-8").strip()
        example = r.render(system, rows[0]["text"])
        (rend_dir / f"{name}_{v}.txt").write_text(example, encoding="utf-8")
        info[f"token_check_{v}"] = r.token_check(example)
        info["system_merged_into_user"] = r.system_merged
        grammar = LlamaGrammar.from_json_schema(json.dumps(schema(v)), verbose=False)
        fn = f"raw_{name}_{v}.jsonl" if args.tag == "metal" else f"raw_{name}_{v}_{args.tag}.jsonl"
        times = []
        with open(OUT / fn, "w", encoding="utf-8") as fp:
            for i, row in enumerate(rows):
                toks = r.tokens(r.render(system, row["text"]))
                text, fin, dt, usage = r.generate(toks, MAX_TOKENS[v], grammar)
                obj, keys, ok = parse_raw(text)
                rec = {"i": i, "set": row["set"], "text": row["text"], "raw": text, "json_ok": ok, "parsed": obj,
                       "key_order": keys, "finish_reason": fin, "seconds": round(dt, 4),
                       "prompt_tokens": usage["prompt_tokens"], "completion_tokens": usage["completion_tokens"]}
                fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
                times.append(dt)
                if i % 20 == 0:
                    print(f"  {name} {v} {i}/{len(rows)} {dt:.2f}s {text[:90]}", flush=True)
        rest = sorted(times[1:])
        info["timing"][v] = {"n": len(times), "first_s": round(times[0], 3),
                             "median_s_excl_first": round(rest[len(rest) // 2] if len(rest) % 2 else
                                                          (rest[len(rest) // 2 - 1] + rest[len(rest) // 2]) / 2, 4),
                             "max_s_excl_first": round(max(rest), 4), "total_s": round(sum(times), 1)}
        print(v, info["timing"][v], flush=True)
    info["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 1)   # macOS: bytes
    (OUT / f"run_{name}_{args.tag}.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print("peak RSS MB", info["peak_rss_mb"])


if __name__ == "__main__":
    main()
