"""GGUF 파일 머리말에서 tokenizer.chat_template 문자열만 읽는다(모델 가중치·어휘는 불러오지 않음).

  .venv-llm/bin/python experiments/llm/extract_template.py C experiments/llm/templates/kanana_original.jinja
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from models import path  # noqa: E402

SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


def read_template(fn):
    with open(fn, "rb") as f:
        rd = lambda n: f.read(n)
        u32 = lambda: struct.unpack("<I", rd(4))[0]
        u64 = lambda: struct.unpack("<Q", rd(8))[0]
        s = lambda: rd(u64()).decode("utf-8")
        assert rd(4) == b"GGUF"
        u32(); u64(); n_kv = u64()

        def skip(t):
            if t == 8:
                f.seek(u64(), 1)
            elif t == 9:
                et, n = u32(), u64()
                if et == 8:
                    for _ in range(n):
                        f.seek(u64(), 1)
                else:
                    f.seek(SIZES[et] * n, 1)
            else:
                f.seek(SIZES[t], 1)

        for _ in range(n_kv):
            k, t = s(), u32()
            if k == "tokenizer.chat_template" and t == 8:
                return s()
            skip(t)
    raise KeyError("tokenizer.chat_template 없음")


if __name__ == "__main__":
    Path(sys.argv[2]).write_text(read_template(path(sys.argv[1])), encoding="utf-8")
