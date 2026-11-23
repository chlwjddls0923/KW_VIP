# LLM 실험 보고서: 규칙 + 작은 LLM (한 장 요약)

브랜치 `exp/llm-fallback`. 본 시스템(main)에는 연결하지 않았다. 계획: `experiments/llm/PLAN.md`. 상세: `results/exp_llm/summary.md`(3단계), `results/exp_llm/step4.md`(4단계).

## 목적
처음 보는 표현에 가장 잘 대응하는 조합(모델 × 프롬프트 변형 × 결합 방식)을 찾는다. 지킬 조건은 다음 세 가지다.
- 위험한 실패 0건
- 공식 35문장의 결과가 규칙만(R)일 때와 같음
- 규칙(nlu.py) 수정 금지

최종 추론은 CPU만 쓴다고 가정했다.

## 후보와 결과 (3단계, 표의 숫자는 정답/위험/안전)

| 모델·변형 (Q4_K_M) | 크기 | 가장 좋은 결합 | dev 78 | adv_dev 33 | 공식 35 = R |
|---|---|---|---|---|---|
| R (규칙만) | - | - | 78/0/0 | 14/7/12 | - |
| qwen35-4b·A | 3.01 GB | G-floor | 77/0/1 | 24/0/9 | O |
| gemma4-e2b·A | 3.46 GB | G-floor | 77/0/1 | 24/0/9 | O |
| gemma4-e2b·B | 3.46 GB | G-floor | 77/0/1 | 24/0/9 | O |
| exaone4-1.2b·B | 0.81 GB | G-floor | 76/0/2 | 24/0/9 | O |
| qwen35-2b·A | 1.40 GB | G-safe | 76/0/2 | 18/0/15 | O |
| kanana2-3b·A | 2.16 GB | G-safe | 76/0/2 | 18/1/14 | O |
| Qwen3.5-9B | 6.17 GB | 미실시 (상한 확인용, 시간 부족) | | | |

- 모든 G-* 결합은 공식 35문장 결과가 R과 같았다.
- adv_dev의 G-safe 19, G-floor 24는 완벽한 모델을 가정한 상한과 같다.
- PLAN 추천 순서 ①~③(위험 0, 공식 = R, dev 78)을 모두 통과한 조합은 **0개**였다. 모든 조합이 dev 1~2문장을 안전한 실패로 놓쳤다.

## 고른 조합과 이유
**gemma4-e2b × A × G-floor (CPU 4스레드)**, 사용자 결정.
- dev 77/0/1, adv_dev 24/0/9로 1위 동률이다(qwen35-4b·A와 같음).
- CPU 문장당 시간이 3.2초로, qwen35-4b(9.8초)보다 3배 빠르다.
- CPU 1·2회차 출력이 138/138 같았다.
- ③ 미달 1건('신호를 받으면 3층 눌러' REJECT → CLARIFY)은 받아들였다.

## 4단계 결과 (한 번만 실행, 실행 전 동결 44f25b5)

| 문장 집합 | R | 조합 | 메모 |
|---|---|---|---|
| holdout 30 | 29/0/1 | 29/0/1 | 엄격·3단계 방식 모두 같다. **모델 때문에 바뀐 문장 0** |
| adv_test | 미실시 | 미실시 | `data/commands_adv_test.tsv` 없음 |

## 알게 된 것
- **병목은 게이트다.** holdout에서 규칙이 틀린 유일한 문장 '3층 누를까 말까'(기대 CLARIFY)는 게이트에 걸리지 않았다. 그래서 모델 답(unclear → CLARIFY, 맞는 답)을 쓰지 못했다. 게이트에 걸리지 않으면 모델이 아무리 좋아도 소용없다.
- **모델만 쓰면 위험하다.**
  - 같은 gemma4-e2b·A를 모든 문장에 단독으로 쓰면(M) dev 위험한 실패가 9건이다(CPU).
  - holdout '아래로 내려가자'에서 모델은 PRESS(1)로 답했다. 결합 규칙(규칙 비이동 + 모델 PRESS → CLARIFY)이 CLARIFY로 막았다.
  - G-model(게이트에 걸리면 모델 답을 그대로 씀)은 모든 모델에서 dev 위험이 2~6건 나왔다.
- **Metal과 CPU 차이**
  - 같은 시드·temperature 0이어도 원시 출력이 138문장 중 2문장씩 달랐다(qwen35-4b·A, gemma4-e2b·A).
  - G-safe·G-floor 수치는 같았지만, M·G-model은 위험한 실패 수가 바뀌었다(qwen '위로 가자' → CPU에서 PRESS(1)).
  - CPU 안에서는 두 번 실행한 출력이 완전히 같았다.
- kanana는 GGUF 대화 템플릿의 `{% generation %}` 태그 때문에 로드에 실패했다. 두 태그만 지운 템플릿으로 해결했다(`results/exp_llm/kanana_template.md`).

## 한계
- adv_dev 수치는 **낙관적**이다. 게이트 기준을 이 33문장을 보고 만들었고, 여러 조합 중에서 골랐다.
- **adv_test 미실시.** 처음 보는 적대적 문장에서의 효과는 아직 측정하지 못했다.
- holdout은 계획서 작성 때 시제품 점검에 쓰인 문장이다. 이번 결과(모델 때문에 바뀐 문장 0)로는 모델의 도움을 보여 주지 못한다.
- 문장당 약 3초(CPU)가 걸려, 게이트에 걸린 문장에서는 응답이 그만큼 늦어진다.

## adv_test를 넣으면 실행할 명령
`data/commands_adv_test.tsv`(열: text, expected_action, expected_floor, type, debatable)를 넣은 뒤:

```bash
.venv-llm/bin/python experiments/llm/step4_adv_test.py freeze   # 동결 파일·모델 sha256 확인, adv_test sha256 기록
git add results/exp_llm/step4_adv_test_freeze.json && git commit -m "4단계 adv_test 동결"
.venv-llm/bin/python experiments/llm/step4_adv_test.py run      # 모델 한 번 실행 → results/exp_llm/step4_adv_test/
.venv-llm/bin/python experiments/llm/step4_adv_test.py report   # 결합·채점 → step4_adv_test/step4.md
```

그다음 `step4_adv_test/step4.md`의 내용을 `results/exp_llm/step4.md`의 adv_test 절에 옮기고, adv_test 파일과 결과를 커밋한다.
결과를 본 뒤 게이트·프롬프트·결합·채점·라벨은 고치지 않는다.
