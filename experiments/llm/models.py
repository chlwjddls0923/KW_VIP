"""후보 모델 목록 (1단계에서 Hugging Face API로 확인한 값, 사용자 확정 2026-11-23).

revision은 확인 시점 저장소 커밋 앞 10자리, sha256은 HF LFS 값이다.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "models"

CANDIDATES = {
    "A": dict(name="qwen35-4b", repo="bartowski/Qwen_Qwen3.5-4B-GGUF", rev="4168f45a16",
              file="Qwen_Qwen3.5-4B-Q4_K_M.gguf", bytes=3013027808,
              sha256="13c16f426047e2de38cd075bdade4a7bcbc8c774384876f677740cda65f8a983",
              source="Qwen/Qwen3.5-4B", license="apache-2.0", converter="bartowski (imatrix)",
              must_work=True),
    "B": dict(name="qwen35-2b", repo="bartowski/Qwen_Qwen3.5-2B-GGUF", rev="7d26695454",
              file="Qwen_Qwen3.5-2B-Q4_K_M.gguf", bytes=1396198496,
              sha256="57a1085840f497d764a7fc5d346922dbde961efb54cc792ea81d694fd846a1d8",
              source="Qwen/Qwen3.5-2B", license="apache-2.0", converter="bartowski (imatrix)",
              must_work=True),
    "C": dict(name="kanana2-3b", repo="mradermacher/kanana-2-3b-instruct-GGUF", rev="45a8a3e592",
              file="kanana-2-3b-instruct.Q4_K_M.gguf", bytes=2161793920,
              sha256="d76035e014a198801ccc1d6f83f59f64a7bf6969b23773d6311e1696a828d74c",
              source="kakaocorp/kanana-2-3b-instruct", license="kanana-open-license",
              converter="mradermacher (static)", must_work=False),
    "D": dict(name="qwen35-9b", repo="bartowski/Qwen_Qwen3.5-9B-GGUF", rev="182be2fd6c",
              file="Qwen_Qwen3.5-9B-Q4_K_M.gguf", bytes=6169341984,
              sha256="d784ce9eda1a5a7b51e8f705a9e6310844bf4f173654d115823c775fdea56d43",
              source="Qwen/Qwen3.5-9B", license="apache-2.0", converter="bartowski (imatrix)",
              must_work=True),
    "E": dict(name="gemma4-e2b", repo="bartowski/google_gemma-4-E2B-it-GGUF", rev="81012ba353",
              file="google_gemma-4-E2B-it-Q4_K_M.gguf", bytes=3462680032,
              sha256="923c4c86177d2ee173a7f5b4fa3d0ac65f5962ab15e6d6a5bc250aec4fd7bf7e",
              source="google/gemma-4-E2B-it", license="apache-2.0", converter="bartowski (imatrix)",
              must_work=False),
    "F": dict(name="exaone4-1.2b", repo="LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF", rev="162446400e",
              file="EXAONE-4.0-1.2B-Q4_K_M.gguf", bytes=812437792,
              sha256="7b5e753540183ae4d56e6febd9b48cdd944de53386e6faa8f51c8f98cb2b47df",
              source="LGAI-EXAONE/EXAONE-4.0-1.2B", license="exaone (비상업)", converter="공식 (LG AI연구원)",
              must_work=False),
}


def path(key):
    return MODELS / CANDIDATES[key]["file"]
