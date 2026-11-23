# 1단계: 후보 확인 (2026-11-23)

계획: `experiments/llm/PLAN.md`. 브랜치 `exp/llm-fallback`. 본 시스템 파일은 바꾸지 않았다.

## 1. 후보 GGUF (Q4_K_M)

크기는 바이트, sha256은 Hugging Face API(`/api/models/{repo}/tree/main`)의 LFS 값이다. 리비전은 확인 시점의 저장소 커밋 앞 10자리다.

| 후보 | 원본 모델 (라이선스) | GGUF 저장소 (리비전) | 파일 | 크기 | sha256 | 변환한 곳 |
|---|---|---|---|---|---|---|
| A. Qwen3.5-4B | Qwen/Qwen3.5-4B (apache-2.0) | bartowski/Qwen_Qwen3.5-4B-GGUF (4168f45a16) | Qwen_Qwen3.5-4B-Q4_K_M.gguf | 3,013,027,808 (3.01 GB) | 13c16f426047e2de38cd075bdade4a7bcbc8c774384876f677740cda65f8a983 | bartowski (imatrix 양자화) |
| B. Qwen3.5-2B | Qwen/Qwen3.5-2B (apache-2.0) | bartowski/Qwen_Qwen3.5-2B-GGUF (7d26695454) | Qwen_Qwen3.5-2B-Q4_K_M.gguf | 1,396,198,496 (1.40 GB) | 57a1085840f497d764a7fc5d346922dbde961efb54cc792ea81d694fd846a1d8 | bartowski (imatrix 양자화). **받음, 로컬 sha256 일치** |
| C. kanana-2-3b-instruct | kakaocorp/kanana-2-3b-instruct (kanana-open-license, `license: other`) | mradermacher/kanana-2-3b-instruct-GGUF (45a8a3e592) | kanana-2-3b-instruct.Q4_K_M.gguf | 2,161,793,920 (2.16 GB) | d76035e014a198801ccc1d6f83f59f64a7bf6969b23773d6311e1696a828d74c | mradermacher (정적 양자화) |
| C 대체. EXAONE-4.0-1.2B | LGAI-EXAONE/EXAONE-4.0-1.2B (`license_name: exaone`, 비상업) | LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF (162446400e) | EXAONE-4.0-1.2B-Q4_K_M.gguf | 812,437,792 (0.81 GB) | 7b5e753540183ae4d56e6febd9b48cdd944de53386e6faa8f51c8f98cb2b47df | 공식(LG AI연구원) |
| D. Qwen3.5-9B (상한용) | Qwen/Qwen3.5-9B (apache-2.0) | bartowski/Qwen_Qwen3.5-9B-GGUF (182be2fd6c) | Qwen_Qwen3.5-9B-Q4_K_M.gguf | 6,169,341,984 (6.17 GB) | d784ce9eda1a5a7b51e8f705a9e6310844bf4f173654d115823c775fdea56d43 | bartowski (imatrix 양자화) |

- Qwen 공식 GGUF 저장소(`Qwen/Qwen3.5-*-GGUF`)는 없다. A·B·D는 세 크기가 모두 있는 같은 변환자(bartowski)로 맞췄다.
- 다른 변환본:
  - `ggml-org/Qwen3.5-4B-GGUF`(llama.cpp 조직, Q4_K_M 3,032,091,584 B, sha256 217002fa…89c14)는 4B만 있다.
  - `unsloth/Qwen3.5-{2,4,9}B-GGUF`에는 Q4_K_M이 각각 1,280,835,840 / 2,740,937,888 / 5,680,522,464 B로 있다. 2026-03-02 이후 갱신되지 않았다.
  - `lmstudio-community/Qwen3.5-2B-GGUF`도 있다.
- kanana-2-3b-instruct의 `config.json`은 `Qwen3ForCausalLM`(model_type qwen3, 32층, 모두 full attention)이다. llama.cpp가 지원하는 구조다. kakaocorp 공식 GGUF는 없다. imatrix 판(`mradermacher/kanana-2-3b-instruct-i1-GGUF`의 i1-Q4_K_M, 2,161,794,208 B, sha256 2e92fc2d…20ad2)도 있다.
- C는 아직 받지 않았고 로드도 해 보지 않았다. 대체 여부는 실제로 받아서 로드한 뒤 정한다.
- Qwen3.5 GGUF에는 비전용 `mmproj` 파일이 따로 있다. 텍스트만 쓰므로 받지 않는다.

## 2. thinking 모드 끄는 방법 (모델 카드 확인)

| 모델 | 기본값 | 끄는 방법 |
|---|---|---|
| Qwen3.5-2B | 카드: "Qwen3.5-2B operates in non-thinking mode by default" | chat template에 `enable_thinking=False`를 넘긴다. template이 `<|im_start|>assistant\n<think>\n\n</think>\n\n`를 붙인다. 카드: `/think`·`/nothink` 소프트 스위치는 공식 지원하지 않음 |
| Qwen3.5-4B, 9B | 카드: "operate in thinking mode by default" | 카드의 방법: `chat_template_kwargs: {"enable_thinking": False}`. 여기서는 GGUF 안의 chat template을 jinja2로 직접 렌더링하며 `enable_thinking=False`를 넘긴다 |
| EXAONE-4.0-1.2B | 카드 예시: `"chat_template_kwargs": {"enable_thinking": false}` | 같은 방식 |
| kanana-2-3b-instruct | 카드에 thinking 언급 없음 | [받은 뒤 GGUF의 chat template으로 확인] |

## 3. 더 나은 후보 제안 (제안만 함, 받지 않음)

| 후보 | 저장소 / 파일 | 크기 | 라이선스 | 이유 | 걱정 |
|---|---|---|---|---|---|
| Gemma 4 E2B-it | bartowski/google_gemma-4-E2B-it-GGUF / google_gemma-4-E2B-it-Q4_K_M.gguf (sha256 923c4c86…bd7bf7e) | 3.46 GB | apache-2.0 | 다국어 학습 비중이 크다. 계산량은 2B급(유효 파라미터)이라 CPU 속도가 B와 비슷할 수 있다 | 파일이 B의 2.5배다(임베딩 포함). llama-cpp-python 0.3.37의 gemma4 구조 지원은 [확인 안 함]. 공식 GGUF는 `google/gemma-4-E2B-it-qat-q4_0-gguf`(Q4_0 QAT, 3.35 GB)뿐이고 Q4_K_M이 아니다 |
| Gemma 4 E4B-it | bartowski/google_gemma-4-E4B-it-GGUF / google_gemma-4-E4B-it-Q4_K_M.gguf (sha256 d35a3aa7…efe9f) | 5.41 GB | apache-2.0 | A(4B)와 같은 급의 비교 대상 | 같음 |
| (참고) Qwen3.5-0.8B | ggml-org/Qwen3.5-0.8B-GGUF | [크기 확인 안 함] | apache-2.0 | 팀원 PC CPU 속도 하한용 | 정확도 낮을 가능성 |

Gemma 4 E2B는 'CPU에서 2B급 속도 + 다국어' 조건에 맞아 B의 대안으로 넣어 볼 만하다. 목록은 사용자가 정한다.

## 4. 디스크, 다운로드, 예상 시간

- 남은 디스크: 62 GiB (`df -h`, B를 받고 venv를 만든 뒤)
- 지금까지 쓴 용량: `.venv-llm` 307 MB, `.cache-llm`(pip 캐시·빌드 임시 폴더) 348 MB, `models/` 1.3 GB
- 다운로드 합계 (A+B+C+D): 3.01 + 1.40 + 2.16 + 6.17 = **12.74 GB**. 받은 것은 1.40 GB(B), 남은 것은 11.34 GB. C를 EXAONE으로 바꾸면 남은 양은 9.99 GB다
- 측정한 다운로드 속도: B 1.40 GB에 6분 50초(약 3.4 MB/s, 토큰 없이 받음) → 남은 양은 약 55분
- 예상 실행 시간 (3단계): **[대략적인 값. 실제 프롬프트 길이에 따라 크게 달라진다]**
  - 측정 근거: B를 짧은 프롬프트로 돌렸을 때 문장당 Metal 0.83~1.27 s, CPU(4스레드) 1.20~1.28 s
  - 3단계 프롬프트는 예시 8~12개가 들어가 더 길다. Qwen3.5는 선형 어텐션(DeltaNet)이 섞인 구조라 프롬프트 앞부분 캐시 재사용이 되는지 [확인 안 함]
  - Metal 전체(4모델 × 2변형 × 111문장 = 888회): [약 1~2시간]
  - 상위 2개 조합의 CPU 재실행 2회(444회): [약 0.5~1시간]

## 5. llama-cpp-python 설치와 B 확인

| 항목 | 값 |
|---|---|
| 버전 | llama-cpp-python **0.3.37** (PyPI sdist, 2026-11-15). 0.3.38은 오늘(2026-11-23) 나와서 쓰지 않았다 |
| 방법 | **소스 빌드**: `pip install --no-binary llama-cpp-python llama-cpp-python==0.3.37`. 미리 빌드된 휠은 쓰지 않았다. 빌드 1분 20초 |
| 컴파일러 | Apple clang 21.0.0 (Command Line Tools, 이미 설치되어 있던 것). 시스템에 새로 설치한 것은 없다 |
| 빌드 도구 | pip가 격리된 빌드 환경에 PyPI의 cmake 4.4.5 휠과 scikit-build-core 1.1.2를 받아 썼다. venv와 시스템에는 남지 않는다 |
| 백엔드 | 빌드 로그: "Including METAL backend", "Including BLAS backend"(Accelerate) |
| 임시 파일 위치 | `TMPDIR`와 `PIP_CACHE_DIR`를 프로젝트 안 `.cache-llm/`으로 돌렸다. 빌드 로그는 `.cache-llm/build_llama.log`에 있다 |
| 함께 설치된 의존성 | llama-cpp-python: numpy, jinja2, MarkupSafe, diskcache, typing-extensions. huggingface_hub 2.4.0: httpx2, hf-xet, tqdm, filelock, fsspec, PyYAML 등. 전체 목록은 `experiments/llm/requirements-llm.txt` |

B 로드와 JSON 스키마 강제 출력 (`experiments/llm/smoke_load.py`):

- 시험 문장 3개는 새로 쓴 것이다. 평가 파일 문장은 쓰지 않았다.
- 설정: `n_ctx=2048`, `n_threads=4`, `seed=0`, `temperature=0`, `max_tokens=96`, 스키마는 `LlamaGrammar.from_json_schema`로 걸었다.

| 실행 | 로드 | 문장당 시간 | JSON 파싱 | 프로세스 RSS |
|---|---|---|---|---|
| Metal (`n_gpu_layers=-1`) | 0.39 s | 0.83~1.27 s | 3/3 | 2,819 MB |
| CPU (`n_gpu_layers=0`) | 0.64 s | 1.20~1.28 s | 3/3 | 4,165 MB |

- 결과 파일: `results/exp_llm/step1_smoke_Qwen_Qwen3.5-2B-Q4_K_M_{metal,cpu}.json`
- GGUF 구조: `general.architecture = qwen35`. 0.3.37에 들어 있는 llama.cpp가 이 구조를 로드했다.
- 세 문장 모두 Metal과 CPU의 JSON 값이 같았다. 공백만 달랐다.
- 이번 시스템 프롬프트는 최소한의 한 줄이라 분류 품질은 보지 않았다. 예를 들어 '잠깐 기다려 봐'에 `floor_type: highest`가 나왔다. 3단계에서 프롬프트를 제대로 쓴다.
- CPU 4스레드는 M4의 성능 코어 수(4)에 맞췄다(효율 코어 6). 3단계에서 값을 다시 정해 기록한다.
