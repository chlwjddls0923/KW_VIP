"""후보 GGUF를 models/에 받고 sha256을 HF 값과 비교한다.

  HF_HOME=models/.hf .venv-llm/bin/python experiments/llm/download.py F C E A D
결과: results/exp_llm/downloads.json
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from models import CANDIDATES, MODELS, ROOT, path  # noqa: E402

from huggingface_hub import hf_hub_download  # noqa: E402

OUT = ROOT / "results" / "exp_llm" / "downloads.json"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def main(keys):
    log = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for k in keys:
        c = CANDIDATES[k]
        t = time.time()
        try:
            if not path(k).exists():
                hf_hub_download(c["repo"], c["file"], revision=c["rev"], local_dir=str(MODELS))
            got = sha256(path(k))
            rec = {"file": c["file"], "repo": c["repo"], "rev": c["rev"], "bytes": path(k).stat().st_size,
                   "sha256_local": got, "sha256_hf": c["sha256"], "match": got == c["sha256"],
                   "seconds": round(time.time() - t, 1)}
        except Exception as e:  # 실패도 기록하고 다음 후보로
            rec = {"file": c["file"], "repo": c["repo"], "error": f"{type(e).__name__}: {e}"}
        log[k] = rec
        OUT.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(k, json.dumps(rec, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
