# LLM 실험 3단계: 모델 실행과 결합 비교

브랜치 exp/llm-fallback. 규칙(`src/assist/nlu.py`)은 import만 했고 고치지 않았다. 게이트 τ = 0.5(2단계).
문장: dev 78 + adv_dev 33 = 111문장, 공식 문장 35개 중 111문장에 없는 것을 더해 모델마다 138문장을 실행했다.
판정: 위험한 실패 = 누르면 안 되는데 PRESS, 또는 기대와 다른 층 PRESS. 안전한 실패 = 그 밖의 오답. 표의 숫자는 `정답/위험/안전`.

> **adv_dev 수치는 낙관적이다.** 게이트 기준 (2)~(6)을 adv_dev를 보고 만들었고, 조합 여러 개 중에서 고른 값이다.
> 일반화는 4단계(holdout, adv_test)로 판단한다.

## 1. 후보와 실행 상태

| 키 | 모델 | 파일 크기 | 상태 |
|---|---|---|---|
| A | Qwen3.5-4B | 3.01 GB | 실행 (Metal A·B, CPU A 2회) |
| B | Qwen3.5-2B | 1.40 GB | 실행 (Metal A·B) |
| C | kanana-2-3b-instruct | 2.16 GB | 첫 실행은 템플릿 오류로 로드 실패 → 수정 템플릿으로 재시도해 실행 (Metal A·B). `kanana_template.md` |
| D | Qwen3.5-9B | 6.17 GB | **미실시(상한 확인용, 시간 부족)**. 실행하지 않았다. 다만 파일은 받아졌다(7절) |
| E | Gemma 4 E2B | 3.46 GB | 실행 (Metal A·B, CPU A 2회) |
| F | EXAONE-4.0-1.2B | 0.81 GB | 실행 (Metal A·B) |

설정: llama-cpp-python 0.3.37, n_ctx 4096, n_threads 4, seed 0, temperature 0(top_k 1), JSON 스키마 문법 강제, 같은 Llama 객체 재사용, 문장마다 `reset()`.
thinking 끄기: Qwen·Gemma·EXAONE은 템플릿에 `enable_thinking=False`. kanana는 `thinking_mode` 기본값이 `no_think`(생성 프롬프트에 빈 `<think></think>`).
변형 B: 모든 모델에서 138/138 출력이 `reason` 필드로 시작했다. JSON 파싱 오류는 모든 실행에서 0건.

## 2. Metal 결과 (모델 × 변형 × 결합 방식)

R(규칙만): dev 78/0/0, adv_dev 14/7/12, 공식 35 = 35. 아래 모든 G-* 결과는 공식 35개 결과가 R과 같다(M·A-safe는 대부분 다름, `combos.csv`).

| 모델·변형 | G-safe dev | G-safe adv | G-floor dev | G-floor adv | G-model dev | G-model adv | M dev | M adv |
|---|---|---|---|---|---|---|---|---|
| qwen35-4b·A | 77/0/1 | 19/0/14 | 77/0/1 | **24/0/9** | 74/3/1 | 28/0/5 | 61/6/11 | 26/0/7 |
| qwen35-4b·B | 77/0/1 | 19/0/14 | 77/0/1 | 23/1/9 | 75/3/0 | 27/1/5 | 70/5/3 | 26/1/6 |
| gemma4-e2b·A | 77/0/1 | 19/0/14 | 77/0/1 | **24/0/9** | 74/4/0 | 27/2/4 | 70/8/0 | 25/3/5 |
| gemma4-e2b·B | 77/0/1 | 19/0/14 | 77/0/1 | **24/0/9** | 74/4/0 | 27/1/5 | 65/10/3 | 27/1/5 |
| exaone4-1.2b·B | 76/0/2 | 19/0/14 | 76/0/2 | **24/0/9** | 72/5/1 | 25/3/5 | 52/16/10 | 24/3/6 |
| exaone4-1.2b·A | 76/0/2 | 16/2/15 | 75/1/2 | 21/2/10 | 72/5/1 | 23/5/5 | 56/16/6 | 23/5/5 |
| qwen35-2b·A | 76/0/2 | 18/0/15 | 76/0/2 | 21/1/11 | 72/5/1 | 23/1/9 | 57/10/11 | 22/1/10 |
| qwen35-2b·B | 77/0/1 | 18/1/14 | 77/0/1 | 23/1/9 | 74/3/1 | 27/1/5 | 61/12/5 | 26/1/6 |
| kanana2-3b·A | 76/0/2 | 18/1/14 | 75/1/2 | 22/2/9 | 72/6/0 | 25/5/3 | 56/15/7 | 24/5/4 |
| kanana2-3b·B | 76/0/2 | 17/2/14 | 76/0/2 | 21/3/9 | 74/2/2 | 24/6/3 | 58/11/9 | 23/6/4 |

- 완벽한 모델을 가정한 adv_dev 상한(다른 구현으로 계산): G-safe 19, G-floor 24, G-model 33. 위 표의 G-safe 19와 G-floor 24는 이 상한과 같다.
- G-model은 adv_dev 정답이 가장 많지만 모든 모델에서 dev 위험한 실패가 2~6건 있다.

### dev에서 놓친 문장 (G-safe·G-floor, 모두 안전한 실패)
| 문장 | 기대 | 규칙 | 모델 | 결합 결과 | 해당 |
|---|---|---|---|---|---|
| 신호를 받으면 3층 눌러 | REJECT | REJECT | PRESS(3) | CLARIFY | exaone A·B, gemma A·B, qwen2b A·B, qwen4b A |
| 3층 눌러 주시면 어떻게 돼요? | REJECT | REJECT | PRESS(3) | CLARIFY | exaone A·B, qwen2b A, qwen4b B |

두 문장 모두 게이트 기준 (2)에 걸린 dev 문장이다. **그래서 모든 (모델, 변형)이 PLAN 추천 순서 ③(dev 정답 78 그대로)을 통과하지 못했다.**

### Metal에서 나온 위험한 실패 (G-safe·G-floor)
| 문장 | 기대 | 결과 | 조합 |
|---|---|---|---|
| 3층 누를 뻔했네 | NOMOVE | PRESS(3) (규칙·모델 둘 다 누름) | qwen2b·B G-safe·G-floor |
| 3층 눌러, 농담이야 | NOMOVE | PRESS(3) (규칙·모델 둘 다 누름) | exaone·A G-safe·G-floor |
| 3, 4층 눌러줘 | CLARIFY | PRESS(4) (규칙·모델 둘 다 PRESS(4)) | exaone·A G-safe·G-floor |
| 3층이나 4층 눌러줘 (dev) | CLARIFY | PRESS(4) (G-floor (b)) | exaone·A G-floor |
| 5층 누르지 말고 대기하지도 말고 6층 눌러 | PRESS(6) | PRESS(1) (G-floor (a)) | qwen2b·A G-floor |
| 2층 바로 위층 눌러줘 | PRESS(3) | PRESS(1) (G-floor (a)) | qwen4b·B G-floor |

## 3. CPU 재실행 대상 선택

규칙(사용자 지시): 서로 다른 (모델, 변형) 2개. PLAN ①~⑤를 통과한 조합 중 가장 좋은 결합 방식을 가진 것부터 고른다.
①~③ 통과가 부족하면 위험한 실패 합이 가장 적고, 그다음 adv_dev 정답이 가장 많은 것으로 채우고 '①~③ 미통과'로 적는다.
동점이면 PLAN 순서대로 ② → ③(dev 정답 수가 많은 쪽) → ⑤(파일 크기 → 변형 A) 순으로 정했다. 코드: `experiments/llm/select_cpu.py`, 결과: `cpu_selection.json`.

- ①~③을 통과한 (모델, 변형): **0개**. 두 개 모두 보조 기준으로 골랐다(**①~③ 미통과**).
- 위험 0, adv_dev 24인 (모델, 변형)이 4개였다: qwen35-4b·A, gemma4-e2b·A, gemma4-e2b·B(이상 dev 77), exaone4-1.2b·B(dev 76).

| 순위 | 고른 (모델, 변형) | 가장 좋은 방식 | 이유 |
|---|---|---|---|
| 1 | **qwen35-4b·A** | G-floor | 위험 0, adv_dev 24, 공식 35 = R, dev 77. dev 77인 후보 중 파일이 가장 작음(3.01 GB) |
| 2 | **gemma4-e2b·A** | G-floor | 같은 수치. gemma·B와 동점이라 변형 A(최대 96토큰)를 골랐다 |
| 제외 | exaone4-1.2b·B | G-floor | adv_dev 24/0으로 같지만 dev 76이라 ③ 동점 기준에서 밀렸다. 파일은 0.81 GB로 가장 작다 |

## 4. CPU 결과 (n_gpu_layers = 0, 최종 표)

| 모델·변형 | 방식 | dev | adv_dev | adv_dev(debatable 제외) | 공식 35 = R | adv type별 neg2 / unreal / floor / vocab / meta |
|---|---|---|---|---|---|---|
| qwen35-4b·A | R | 78/0/0 | 14/7/12 | 14/7/8 | O | 1/0/4, 4/4/0, 1/3/3, 4/0/5, 4/0/0 |
| qwen35-4b·A | M | 61/7/10 | 26/0/7 | 24/0/5 | X (30/35) | 2/0/3, 8/0/0, 7/0/0, 5/0/4, 4/0/0 |
| qwen35-4b·A | A-safe | 72/0/6 | 17/0/16 | 17/0/12 | X | 1/0/4, 8/0/0, 2/0/5, 2/0/7, 4/0/0 |
| qwen35-4b·A | G-safe | 77/0/1 | 19/0/14 | 19/0/10 | O | 1/0/4, 8/0/0, 2/0/5, 4/0/5, 4/0/0 |
| qwen35-4b·A | **G-floor** | **77/0/1** | **24/0/9** | **23/0/6** | O | 1/0/4, 8/0/0, 7/0/0, 4/0/5, 4/0/0 |
| qwen35-4b·A | G-model | 74/4/0 | 28/0/5 | 26/0/3 | O | 2/0/3, 8/0/0, 7/0/0, 7/0/2, 4/0/0 |
| gemma4-e2b·A | M | 69/9/0 | 24/3/6 | 22/2/5 | O | 1/0/4, 7/1/0, 7/0/0, 6/1/2, 3/1/0 |
| gemma4-e2b·A | A-safe | 72/0/6 | 18/0/15 | 18/0/11 | X | 1/0/4, 8/0/0, 2/0/5, 3/0/6, 4/0/0 |
| gemma4-e2b·A | G-safe | 77/0/1 | 19/0/14 | 19/0/10 | O | 1/0/4, 8/0/0, 2/0/5, 4/0/5, 4/0/0 |
| gemma4-e2b·A | **G-floor** | **77/0/1** | **24/0/9** | **23/0/6** | O | 1/0/4, 8/0/0, 7/0/0, 4/0/5, 4/0/0 |
| gemma4-e2b·A | G-model | 74/4/0 | 26/2/5 | 24/1/4 | O | 1/0/4, 8/0/0, 7/0/0, 7/1/1, 3/1/0 |

(type별 칸은 정답/위험/안전. R은 두 모델이 같아 한 줄만 적었다.)

### Metal ↔ CPU, 재현성
| 모델·변형 | Metal vs CPU 1회차 (원시 출력 같음) | 달라진 문장 | CPU 1회차 vs 2회차 |
|---|---|---|---|
| qwen35-4b·A | 136/138 | 위로 가자(not_command → relative +1), 6층 가고 싶어(press 6 → not_command) | 138/138 |
| gemma4-e2b·A | 136/138 | 엘리베이터 오층 선택(relative +5 → +1), 3층에 사는 친구 만나러 가(press 3 → not_command) | 138/138 |

- 문장별 최종 행동이 Metal과 CPU에서 달라진 것(`decisions/*_cpu1.csv`와 비교):
  - qwen35-4b·A: G-safe·G-floor 0문장. G-model 1문장('위로 가자' REJECT → **PRESS(1)**, dev 위험 3 → 4). M 2문장.
  - gemma4-e2b·A: G-safe·G-floor 1문장('3층에 사는 친구 만나러 가' CLARIFY → REJECT, 둘 다 안전한 실패, debatable). G-model 1문장(PRESS(3) → REJECT). M 2문장('엘리베이터 오층 선택' PRESS(5) → **PRESS(1)** 포함).
  - 그래서 G-safe·G-floor의 정답/위험/안전 수는 Metal과 같다. M·G-model은 장치에 따라 위험한 실패 수가 바뀐다.
- CPU에서는 같은 설정으로 두 번 실행한 출력이 완전히 같았다. Metal과 CPU는 같은 시드여도 출력이 다를 수 있다.

## 5. 자원

| 모델·변형 | 장치 | 문장당 시간 중앙값 / 최대 (첫 호출 제외) | 로드 | 최대 메모리(RSS) |
|---|---|---|---|---|
| qwen35-4b·A | CPU 4스레드 (1회차 / 2회차) | 9.79 / 12.11 s · 9.71 / 12.10 s | 3.74 s | 5,743 MB · 5,851 MB |
| gemma4-e2b·A | CPU 4스레드 (1회차 / 2회차) | 3.23 / 3.39 s · 3.25 / 4.09 s | 3.28 s · 미기록 | 5,103 MB · 미기록 |
| qwen35-4b | Metal A / B | 3.46 / 3.96 s · 4.73 / 6.31 s | 2.17 s | 3,100 MB |
| gemma4-e2b | Metal A / B | 1.35 / 4.58 s · 2.19 / 3.07 s | 2.76 s | 3,168 MB |
| exaone4-1.2b | Metal A / B | 1.25 / 1.37 s · 1.79 / 2.39 s | 0.73 s | 1,194 MB |
| qwen35-2b | Metal A / B | 1.57 / 1.69 s · 2.28 / 2.99 s | 1.44 s | 1,555 MB |
| kanana2-3b | Metal A / B | 2.33 / 2.40 s · 3.13 / 3.37 s | 0.26 s | 2,804 MB |

- 측정 PC: 맥미니 M4, 16 GB. 팀원 PC의 CPU 시간은 [미측정].
- 최대 메모리는 프로세스 RSS(`ru_maxrss`)이다. CPU 실행에서 Metal보다 크게 나왔다.

## 6. 추천 (PLAN 순서 ①~⑤)

**사용자 결정(2026-11-24):** ③ 미달 1건을 받아들이고, 4단계 조합으로 **gemma4-e2b × A × G-floor**(CPU)를 골랐다.
- ③ 미달 1건: dev '신호를 받으면 3층 눌러'. 기대는 REJECT인데 결과는 CLARIFY(안전한 실패).
  원인은 G-safe 결합 규칙(규칙 비이동 + 모델 PRESS → CLARIFY)이다. 규칙은 REJECT로 맞혔지만 게이트 기준 (2)에 걸렸고, 모델이 PRESS(3)로 답해 CLARIFY가 됐다.
  G-floor에서도 이 경우는 G-safe 규칙을 그대로 따른다.

아래는 결정 전 정리다.

- ①~③을 모두 통과한 조합은 **없다.** ③에서 dev 1문장('신호를 받으면 3층 눌러', 안전한 실패)을 놓친다.
- 이 문장을 감수한다면 CPU 최종 표의 최상위는 **qwen35-4b·A·G-floor와 gemma4-e2b·A·G-floor 동률**이다(dev 77/0/1, adv_dev 24/0/9, 공식 35 = R).
- ⑤에서 '더 작은 모델'은 qwen35-4b(3.01 GB 대 3.46 GB), '더 빠른 모델'은 gemma4-e2b(CPU 3.2 s 대 9.8 s)라 두 기준이 갈린다. 어느 쪽을 쓸지는 사용자가 정한다.
- 덜 맡기는 방식을 원하면 G-safe(두 모델 모두 dev 77/0/1, adv_dev 19/0/14)가 있다.
- D(9B)는 상한 확인용이고 미실시다.

## 7. 계획과 다르게 한 것

- D(9B) 미실시(사용자 지시). `run_all.sh`는 A 실행이 끝난 직후(00:55:18) SIGTERM으로 멈췄다(`experiments/llm/stop_after_A.sh`, 기록 `.cache-llm/stop_after_A.log`).
- **지시와 다르게 된 것: D 파일이 다운로드됐다.** '다운로드는 A만, D는 지금 받지 마' 지시 전(23:59)에 시작된 `download.py`의 인자가 `B F C E A D`였다.
  ps 출력이 잘린 것을 보고 D가 목록에 없다고 잘못 판단해 다운로드를 멈추지 않았다.
  D는 00:55:23에 받기를 마쳤다(1188 s, sha256 일치, `downloads.json`의 D 항목, `models/Qwen_Qwen3.5-9B-Q4_K_M.gguf`, git 제외).
  run_all.sh는 그보다 5초 앞서 멈췄기 때문에 D는 실행되지 않았다.
- 순서: A는 다운로드가 끝나자 `run_all.sh`가 00:36에 바로 시작해서, EXAONE B 결합은 A가 끝난 뒤(00:55 이후)에 했다. 결합은 저장한 출력으로 하므로 수치에는 영향이 없다.
- **미완성 출력으로 계산된 수치(정정):** 첫 `combos.csv`(00:15)는 EXAONE A 원시 출력(`raw_exaone4-1.2b_A.jsonl`, 00:16에 138줄 완성)이 다 쓰이기 전에 계산됐다.
  출력이 없는 문장은 CLARIFY로 처리돼서, 중간 보고에서 EXAONE·A·G-safe를 잘못 추천했다.

  | EXAONE·A | 미완성 출력으로 계산한 값 (00:15) | 138문장으로 다시 계산한 값 |
  |---|---|---|
  | G-safe dev | 78/0/0 | 76/0/2 |
  | G-safe adv_dev | 18/0/15 | 16/2/15 |
  | G-floor dev / adv_dev | 78/0/0 / 18/0/15 | 75/1/2 / 21/2/10 |
  | G-model dev / adv_dev | 76/0/2 / 18/0/15 | 72/5/1 / 23/5/5 |
  | M dev / adv_dev / 공식 35 정답 | 61/4/13 / 15/0/18 / 8 | 56/16/6 / 23/5/5 / 34 |

  이 문서의 모든 표는 다시 계산한 값이다.
- kanana: GGUF 템플릿에서 `{%- generation -%}`, `{%- endgeneration -%}` 두 태그만 지운 `templates/kanana_fixed.jinja`를 썼다. 정상 출력·토큰 확인을 통과했다. 자세한 내용은 `kanana_template.md`.
- `run_model.py`: 다른 세션이 00:24:58에 `GenerationTag` 확장을 넣었다(E 실행은 00:24:39에 시작해 수정 전 코드로 돌았다). 이 세션은 `--template`, `--sanity-only` 옵션을 더했다. 다른 모델의 렌더링 결과는 바뀌지 않는다.
- CPU 재실행 대상 선택 규칙에 동점 처리(② → ③ dev 정답 수 → ⑤)를 더했다(3절).
- gemma4-e2b·A CPU 2회차 실행 중(02:02~02:10)에 프로젝트 폴더가 `~/Desktop/mojuco`에서 `~/mojuco`로 옮겨졌다. 원시 출력 `raw_gemma4-e2b_A_cpu2.jsonl`(138줄)은 모두 기록됐고 비교에 썼다.
  - **미기록:** `results/exp_llm/run_gemma4-e2b_cpu2_A.json`. 실행이 끝날 때 예전 절대 경로(`~/Desktop/mojuco/...`)에 쓰려다 FileNotFoundError로 실패했다(종료 코드 1).
    이 파일에 들어갈 내용은 실행 설정, 로드 시간, 정상 출력 확인, 토큰 확인, 시간 요약, 최대 메모리다.
  - 시간 요약(중앙값 3.2487 s, 최대 4.0904 s, 합계 453.5 s)과 정상 출력 답은 로그 `.cache-llm/run_E_cpu2_A.log`에 남아 있다(로그는 커밋 대상이 아님).
    **로드 시간과 최대 메모리는 미기록이다.**

## 8. 파일

- 코드: `experiments/llm/` — run_model.py, combine.py, select_cpu.py, compare_runs.py, run_cpu.sh, run_all.sh, stop_after_A.sh, extract_template.py, templates/
- 결과: `results/exp_llm/` — raw_*.jsonl, combos.csv(Metal), combos_cpu1.csv(CPU), decisions/, compare_*.json, cpu_selection.json, run_*.json, kanana_template.md
