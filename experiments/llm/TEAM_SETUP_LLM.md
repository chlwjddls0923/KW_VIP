# LLM 실험 환경 (팀원용 메모)

LLM 실험(규칙 + 작은 LLM)은 본 시스템에 연결하지 않았다. 본 시스템 설치는 main 브랜치의 `docs/TEAM_SETUP.md`를 따른다.
이 문서는 실험을 다시 돌려 보고 싶을 때의 주의점만 적는다.

## 1. 가상환경과 llama-cpp-python

본 시스템의 `.venv`와 섞지 않고 `.venv-llm`을 따로 만든다.

```bash
# macOS (확인함: Python 3.11.13, Apple clang 21)
/opt/homebrew/bin/python3.11 -m venv .venv-llm
.venv-llm/bin/python -m pip install -r experiments/llm/requirements-llm.txt
```

| 항목 | 내용 |
|---|---|
| 버전 | `llama_cpp_python==0.3.37` |
| 설치 방식 | PyPI에는 소스만 있어 **설치 중에 C/C++ 컴파일**을 한다. macOS에서는 소스 빌드 약 1분 20초. Metal·Accelerate 백엔드가 함께 빌드됐다(`results/exp_llm/step1_candidates.md` 5절) |
| macOS 준비물 | Xcode Command Line Tools(clang). 빌드에 쓰는 cmake·scikit-build-core는 pip가 격리 환경에 알아서 받는다 |
| Windows 준비물 | **C++ 빌드 도구(Visual Studio Build Tools의 'C++를 사용한 데스크톱 개발')가 필요할 수 있다 [확인 필요]**. 미리 빌드된 CPU 휠을 쓰는 방법도 있지만 이 실험에서는 써 보지 않았다 [확인 필요] |
| 빌드 임시 폴더 | macOS에서는 `TMPDIR`와 `PIP_CACHE_DIR`를 프로젝트 안 `.cache-llm/`으로 돌렸다(용량 약 350 MB) |
| 실행 장치 | 최종 확인(4단계)은 CPU만 썼다(`n_gpu_layers=0`, 4스레드). GPU가 없어도 된다 |

## 2. 모델 파일 받기

모델 파일은 git에 넣지 않는다(`models/`는 .gitignore).
`experiments/llm/download.py`가 Hugging Face에서 정해진 revision의 파일을 받고, sha256을 `models.py`에 적힌 값과 비교한다.

```bash
HF_HOME=models/.hf .venv-llm/bin/python experiments/llm/download.py E      # 4단계에 쓴 Gemma 4 E2B만
```

| 키 | 모델 | 파일 | 크기 | 라이선스 |
|---|---|---|---|---|
| E | Gemma 4 E2B (4단계 조합) | `google_gemma-4-E2B-it-Q4_K_M.gguf` (bartowski) | 3.46 GB | Apache-2.0 |
| A | Qwen3.5-4B | `Qwen_Qwen3.5-4B-Q4_K_M.gguf` (bartowski) | 3.01 GB | Apache-2.0 |
| B | Qwen3.5-2B | `Qwen_Qwen3.5-2B-Q4_K_M.gguf` (bartowski) | 1.40 GB | Apache-2.0 |
| C | kanana-2-3b-instruct | `kanana-2-3b-instruct.Q4_K_M.gguf` (mradermacher) | 2.16 GB | Kanana Open License. 대화 템플릿 수정 필요(`results/exp_llm/kanana_template.md`) |
| F | EXAONE-4.0-1.2B | `EXAONE-4.0-1.2B-Q4_K_M.gguf` (공식) | 0.81 GB | 비상업 라이선스 |

- 저장소, revision, sha256은 `experiments/llm/models.py`에 있다. 결과는 `results/exp_llm/downloads.json`에 기록된다.
- 로그인 없이 받을 수 있었다. 경고 'unauthenticated requests'는 속도 제한 안내일 뿐이다.

## 3. 4단계 조합 다시 실행

`experiments/llm/REPORT.md`와 `results/exp_llm/step4.md`를 본다. holdout은 한 번만 실행하는 원칙이라 다시 돌리지 않는다.
