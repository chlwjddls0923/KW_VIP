# 야간 작업 보고 (2026-11-24, 03:32~)

## 요약 (04:15 기준, 작업 6 push 결과는 맨 아래 '작업 6' 절)

| 작업 | 상태 | 핵심 수치 | 커밋 (브랜치) | push |
|---|---|---|---|---|
| 0 원격 확인과 push | 완료 | fetch 성공, 원격에만 있는 커밋 0, 검사 통과 | 255fd06 (main) | main 이미 같음, exp/llm-fallback 66f1017..201ed5b push |
| 1 깨끗한 복제본 재현 | 완료 | pytest 42 passed, 명령 점검 5/5, dev 78/78·holdout 29/30 원본과 같음, README 수정 없음 | a40fda7 (main) | 작업 6 |
| 2 팀원 PC 안내서 | 완료 (Windows [미확인]) | macOS 확인 항목 ✅ 표시 | f4cd6ce (main), 166c763 (exp/llm-fallback) | 작업 6 |
| 3 발표 재료 | 완료 | 5분 6절, 그림 2장(pillow), 네 질문 답 | 6c10560 (main) | 작업 6 |
| 4 LLM 실험 보고서 | 완료 | 한 장 요약, adv_test 실행 명령 | ba83cde (exp/llm-fallback) | 작업 6 |
| 5 정리 | 완료 | PROGRESS.md 갱신 | f488bac (main) | 작업 6 |
| 7 가림 한계 지도 | 완료 (5분, 제한 1.5시간 안) | 검출률 하락 시작 0.86~0.87 m(78%), 미검출 39건 모두 link1 가림, 가림 0이면 1,081/1,081 | 55e01af (main) | 작업 6 |
| 8 관찰 자세 탐색 | 완료 (32분, 제한 2.5시간 안) | 후보 100개 중 원래보다 나은 자세 0개, 상위 3개 2차 평가 모두 97/100(원래와 같음) | 90314ac (exp/observe-pose) | **안 함**(지시) |
| 9 규칙 보강 후보 | 완료 (6분, 제한 1.5시간 안) | 보강 7개 모두 조건 통과, adv_dev 14/7/12 → 20/2/11, dev 78/78·공식 35 불변 | e5dc1fe (exp/rule-v2) | **안 함**(지시) |
| 사후 탐색 → 발표 자료 | 완료 | PRESENTATION_NOTES '한계와 다음 일'에 '사후 탐색' 표 | (작업 6 직전 커밋) | 작업 6 |
| 6 마지막 push | 아래 '작업 6' 절 | | | |

## 내가 정해야 할 것
1. **원격 push의 주체:** 03:31:55 main push(2ba9361)와 00:46 push는 이 세션이 한 것이 아니다. 누가 했는지 확인 필요.
2. **저장소 공개:** GitHub 저장소가 공개(public)다. holdout 문장·결과, LLM 실험 원시 출력도 올라가 있다. 비공개로 둘지 정한다.
3. **팀원 PC(Windows) 확인:** `docs/TEAM_SETUP.md`의 [미확인] 항목을 실제로 확인할 사람과 시점.
4. **adv_test:** 팀원 적대적 문장 수집 방법(규칙을 보지 않고 쓰기)과 목표 문장 수.
5. **발표:** 팀명·팀원·발표일 [대괄호]. 실제 로봇 계획 [미정].
6. **규칙 보강(exp/rule-v2):** 7개 보강을 본 시스템에 넣을지. 넣으면 공식 결과를 본 뒤의 코드 변경이다. 계획서 4절 규칙대로 CHANGELOG에 적고 다시 평가해야 하고, holdout은 이미 본 문장이 된다.
7. **낮은 버튼 한계:** 관찰 자세로는 풀 수 없다고 확인됐다(작업 8). 카메라 위치나 인식 단계(끊긴 고리 처리)를 바꿀지는 [다음 일 후보]이고, 바꾸면 공식 결과 뒤의 변경이다.

## 지시 해석
- 지시문의 '작업 2의 /tmp 복제본'과 '작업 2의 임시 가상환경'은 복제본을 만드는 **작업 1**을 가리키는 것으로 보았다.
- 'SV024 재확인 문장은 작업 4의 발표 자료'는 발표 자료를 만드는 **작업 3**을 가리키는 것으로 보았다.

## 작업 0. 원격 확인과 push (03:32~03:33)

| 항목 | 값 |
|---|---|
| `git remote -v` | origin `https://github.com/chlwjddls0923/KW_VIP.git` (fetch·push 같음). URL에 토큰 없음 |
| 저장소 공개 여부 | **공개(public)**. 로그인 없이 `api.github.com/repos/chlwjddls0923/KW_VIP`가 `private: false`, `visibility: public`을 돌려줌. `gh`는 로그인되어 있지 않음 |
| `git fetch origin` | 성공. 원격에만 있는 커밋 없음(두 브랜치 모두) |

fetch 전 원격 상태:

| 브랜치 | 원격 마지막 커밋 | 날짜 | 작성자 | 메시지 | 로컬이 앞선 커밋 | 원격에만 있는 커밋 |
|---|---|---|---|---|---|---|
| origin/main | 2ba9361 | 2026-11-24 03:28:40 +0900 | chlwjddls0923 | docs/EXPLAIN.md: SV024 재확인 반영 (알려진 한계, 영상 확대 화면 설명) | 0 | 0 |
| origin/exp/llm-fallback | 66f1017 | 2026-11-24 00:03:00 +0900 | chlwjddls0923 | LLM 실험 2단계: adv_dev 33문장, 게이트(τ=0.5), 게이트 결과 | 4 (31724dc, 44f25b5, cc151c8, 201ed5b) | 0 |

- 참고: 로컬 reflog를 보면 `origin/main`은 2026-11-24 03:31:55에 이 컴퓨터에서 push로 2ba9361이 되었다(그 전에는 00:46:56에 29db4bd).
  `origin/exp/llm-fallback`은 00:46:59에 66f1017로 push되었다. 이 두 push는 이 세션이 한 것이 아니다. [누가 했는지 확인 필요]

push 전 검사(범위 `origin/<브랜치>..<브랜치>`):
- 검사 항목: 경로에 `models/`·`.venv*`, 확장자 `.gguf`·`.safetensors`·`.pem`·`.key`, 파일 `.env`, 100 MB 넘는 blob, `git log -p`에서 토큰·API 키처럼 보이는 문자열
  (ghp_/github_pat_/hf_/sk-/AKIA/개인 키/api_key=… 형태).
- 검사 스크립트는 저장소 밖 scratchpad에 두었다. 가짜 비밀 문자열 2개를 넣어 시험했고 둘 다 잡았다.

| 브랜치 | 커밋 | 바뀐 파일 | 가장 큰 blob | 검사 | push |
|---|---|---|---|---|---|
| main | 0 | 0 | - | 통과 | `git push origin main` → Everything up-to-date (push할 것 없음, 인증 문제 없음) |
| exp/llm-fallback | 4 | 78 | 80,399 B (`results/exp_llm/raw_qwen35-4b_B.jsonl`) | 통과 | **push함**: `66f1017..201ed5b`, 03:33 |

- 로그인·비밀번호 요구는 없었다(GIT_TERMINAL_PROMPT=0으로 실행).
- 작업 6에서는 두 브랜치 모두 'push한 브랜치'로 본다(main은 작업 0에서 push 명령이 성공했고 바뀐 것이 없었을 뿐이다).

## 추가 지시 (03:35 받음)
- 10:00까지. 작업 5 다음에 작업 7~9를 하고, 10:00이 지나면 새 작업을 시작하지 않고 작업 6으로 마무리한다.
- 탐색 시드는 9001~9999를 쓴다. 작업 8·9는 main에서 만든 새 브랜치에서만 코드를 바꾸고, 병합·push하지 않는다.

## 작업 1. 깨끗한 복제본에서 재현 (03:33~03:35)

`git clone --branch main <로컬 저장소> /tmp/mojuco_clone`(커밋 255fd06) → `/opt/homebrew/bin/python3.11 -m venv .venv` → `pip install -r requirements.txt`.
README의 명령을 그대로 실행했다.

| 명령 | 결과 | 시간 |
|---|---|---|
| clone | 성공 | 1초 미만 |
| venv + `pip install -r requirements.txt` | 성공. mujoco 4.0.1, kiwipiepy 0.24.1(+kiwipiepy_model 0.24.0), numpy 2.4.6, scipy 1.17.1, pillow 13.0.0, imageio 2.38.2, imageio-ffmpeg 0.8.1, psutil 7.2.2, pytest 9.2.0 | 7초 (**이 컴퓨터의 pip 캐시를 씀**. 처음 받는 PC는 [더 걸림, 미측정]) |
| `scripts/check_env.py` | check_env OK (nq 16, nv 15, nu 7, out/check_head.png, 형태소 분석) | 9초 |
| `python -m pytest` | **42 passed** (36.7초) | 37초 |
| `demo.py --text "3층 버튼을 눌러줘"` | 3층 눌림 확인 15.1 mm, 보이는 층 1~6 (README 출력 예와 같음) | 1초 |
| `demo.py --text "엘리베이터 3층을 선택해 줘"` | 3층 눌림 확인 15.1 mm | 2초 |
| `demo.py --text "버튼은 누르지 말고 대기해"` | 대기합니다 (WAIT) | 1초 |
| `demo.py --text "3층 누르지 마"` | 대기합니다 (WAIT) | 1초 |
| `demo.py --text "현재 장면에 없는 7층 버튼을 눌러줘"` | 7층 버튼이 보이지 않아 수행할 수 없습니다 (REJECT) | 1초 |
| `demo.py --text "4층으로 가자" --seed 5001` | 4층 눌림 확인 15.3 mm (보이는 층 1, 2, 4, 6) | 1초 |
| `demo.py` (입력에 빈 줄) | '명령>' 뒤 바로 끝남, 종료 코드 0 | - |
| `eval.py nlu` (복제본의 results/nlu에 씀) | dev 78/78, 기준선 22/78. holdout 29/30은 README대로 **기존 결과 재사용(다시 실행하지 않음)** | 2초 |

- 원본 `results/nlu`와 비교: dev.csv 78행, holdout.csv 30행 모두 `parse_ms`를 뺀 모든 열이 같다. 원본 폴더에는 쓰지 않았다.
- README대로 되지 않은 곳: 없음 → README 수정 없음.
- 공식·기준선·추가 평가(`eval.py official/baseline/supplementary`)는 지시 범위 밖이라 실행하지 않았다.
- `/tmp/mojuco_clone`은 03:35에 지웠다.

## 작업 2. 팀원 PC 안내서 (03:35~03:37)
- main `docs/TEAM_SETUP.md` (커밋 f4cd6ce)
  - push에 성공했으므로 `git clone https://github.com/chlwjddls0923/KW_VIP.git` 기준으로 썼다.
  - macOS·Windows 설치, 확인 명령(check_env, pytest 42개, 명령 점검 5문장, 시드 5001 데모, eval.py nlu)과 기대 출력, 자주 나는 오류를 적었다.
  - 작업 1에서 확인한 것은 ✅, Windows는 모두 [미확인]으로 구분했다.
- exp/llm-fallback `experiments/llm/TEAM_SETUP_LLM.md` (커밋 166c763): llama-cpp-python 소스 빌드 주의점(Windows C++ 빌드 도구 [확인 필요]), 모델 받는 법(download.py, 후보 표).
- 안내서의 `eval.py nlu`는 `results/nlu/dev.csv`를 다시 쓴다. 그래서 팀원 PC에서는 커밋하지 말라고 적었다.

## 작업 3. 발표 재료 (03:37~03:40)
- main `docs/PRESENTATION_NOTES.md`
  - 5분 구성 6절과 절마다 표·수치·출처 경로를 적었다. 네 질문에는 한 문단씩 답하고 코드 위치를 붙였다(지금 코드와 줄 번호를 확인함).
  - 실패 사례 절에 SV024 재확인 문장, SV060·SV094, link1 투명 반사실을 넣었다.
  - LLM 수치는 `git show exp/llm-fallback:...`로 읽었다. adv_dev '개발용, 낙관적', holdout '모델 때문에 바뀐 문장 0', adv_test '미실시', '아래로 내려가자' 사례를 넣었다.
- 그림 `docs/figures/`
  - `success_bar.png`: matplotlib이 없어(설치 금지) pillow로 그렸다. 스크립트 `experiments/figures/make_success_bar.py`, 수치는 trials.csv에서 셈: 20/20 vs 6/20, 10/10 vs 6/10, 10/10 vs 0/10.
  - `sv024_link1_occlusion.png`: `results/diag/SV024_zoom_raw.png`를 복사했다.

## 작업 4. LLM 실험 보고서 (03:38~03:39)
- exp/llm-fallback `experiments/llm/REPORT.md` (커밋 ba83cde)
  - 목적, 3단계 후보 표, 고른 조합과 이유, 4단계 결과를 적었다.
  - 알게 된 것: 병목은 게이트, 모델 단독 위험 사례, Metal·CPU 차이, kanana 템플릿.
  - 한계: adv_dev는 낙관적, adv_test 미실시. adv_test를 넣으면 실행할 명령(freeze → run → report)도 적었다.
- 수치는 `results/exp_llm/summary.md`, `step4.md`, `combos*.csv`에서 옮겼다. 'G-model dev 위험 2~6건'은 combos.csv에서 최소·최대를 다시 확인했다.

## 작업 5. 정리 (03:40)
- `docs/PROGRESS.md`
  - 고정 사항의 'git push·원격 설정 안 함'을 지금 운영(원격 설정 변경 없음, push는 사용자 지시 조건에서만)에 맞게 고쳤다.
  - '단계 7 이후' 절을 추가하고 '다음 할 일'을 갱신했다: adv_test 수집·실행, 팀원 PC 확인, 발표.
- 이 파일 맨 위에 요약 표와 '내가 정해야 할 것'을 넣었다.

## 작업 7. 가림 한계 지도 (03:41~03:46, 제한 1.5시간 안)
- `experiments/diag/occlusion_map.py`(새 파일, src/assist는 import만), 결과 `results/diag/occlusion_map/`(grid.csv, by_height.csv, by_occlusion.csv, 그림 2장, README.md)
- 격자 189장면 × 6버튼 = 1,134버튼, 18.5초. 격자 값이 정해져 있어 시드는 쓰지 않았다.
- **검출률이 떨어지기 시작하는 높이: 0.86~0.87 m(78%)**. 0.85 m 44%, 0.84 m 33%, 0.83 m 28%. 0.87 m 이상 1,062버튼은 모두 검출.
- **미검출 39건은 모두 link1 가림이 있었다.** link1 가림 0인 버튼은 1,081/1,081 검출. 고리 가림 20% 이상이면 0/38 검출. 화면 밖 0건.
- 계획서 3절 '약 0.86 m 아래 가림'과 높이 경계는 일치한다. 다만 같은 높이라도 화면에서 link1과 겹치는 가로 위치(u 549~655 px)일 때만 빠진다.

## 작업 7~9의 진행 방식
- 작업 9는 작업 8의 1차 평가(백그라운드, 약 27분)가 도는 동안 별도 git worktree `~/mojuco/KW_VIP_rulev2`(브랜치 exp/rule-v2)에서 병행했다.
  같은 폴더에서 nlu.py를 바꾸면 작업 8의 2차 평가가 바뀐 규칙을 불러올 수 있어서 폴더를 나눴다. 작업 8 2차 평가는 main 규칙(exp/observe-pose 브랜치)으로 돌았다.
- 그래서 끝난 순서는 7 → 9 → 8이다.

## 작업 8. 관찰 자세 탐색 (03:42~04:13, 브랜치 exp/observe-pose, 커밋 90314ac, push 안 함)
- src/assist의 `Q_OBSERVE` 상수는 고치지 않았다. 실험 스크립트(`experiments/observe_pose/explore.py`) 안에서만 `assist.scene.Q_OBSERVE`와 `assist.pipeline.Q_OBSERVE`를 바꿨다(지시 범위보다 좁게).
- 미리 확인한 사실: 미검출을 만드는 link1은 joint1 축과 같은 축의 원기둥(반지름 0.065 m)이라, 어떤 관찰 자세에서도 카메라에 보이는 모양이 같다.
- **1차**(후보 100, 1개는 접촉으로 제외): 원래 자세보다 격자 검출률이 높은 후보 0개(최고 1,095/1,134 동률 8개). 상위 3개는 동률 중 팔 픽셀 비율이 작은 순서로 골랐다: [−0.4, 0, −2.6], [−0.8, 0, −2.1], [0, 0, −2.6].
- **2차**(시드 9001~9100, 누르기 포함): 네 자세 모두 97/100. 실패 3건(E9085·E9089·E9096, 목표 0.848~0.852 m, 인식 미검출)이 같고, 보인 층도 모든 시행에서 같다. t_task 중앙값 9.88 s, 접근 IK 실패 0.
- 결과: 그 브랜치의 `results/explore_observe_pose/README.md`(첫 줄 '사후 탐색, 공식 결과 아님, 병합하지 않음').

## 작업 9. 규칙 보강 후보 (03:42~03:46, 브랜치 exp/rule-v2, 커밋 e5dc1fe, push 안 함)
- nlu.py만 고쳤다. 보강 7개를 `RULE_V2`로 켜고 끈다: F1 대과거 '었었', F2 망설임 '누를까 말까', F3 '뻔', F4 '생각 없', F5 '농담·장난', F6 '3, 4층', F8 '치다'.
- 각 보강은 표적 문장 하나만 바꿨고, 7개 모두 조건을 통과했다(dev 78/78, 공식 35 불변, 눌러선 안 되는 PRESS 증가 없음). 합쳐도 통과했고 pytest 42개도 통과했다.
- v1 → v2 → (참고) gemma4-e2b·A·G-floor

  | 문장 집합 | v1 | v2 | gemma4-e2b·A·G-floor |
  |---|---|---|---|
  | dev | 78/0/0 | 78/0/0 | 77/0/1 |
  | adv_dev | 14/7/12 | 20/2/11 | 24/0/9 |
  | holdout (이미 본 문장, 일반화 근거 아님) | 29/0/1 | 30/0/0 | 29/0/1 |
- 하지 않은 것
  - '누르고 와'('오'를 점수 없는 용언으로): '누르고 오지 마'를 PRESS로 만들 위험이 있어 판단으로 뺐다.
  - 상대 층·최고층·나열·이중 부정: 한두 줄로 고칠 수 없어 뺐다.
- adv_dev 파일은 `git show exp/llm-fallback:data/commands_adv_dev.tsv`로 읽었다. 이 브랜치의 data/에는 넣지 않았다.
- 결과: 그 브랜치의 `results/explore_rule_v2/README.md`(첫 줄 '사후 탐색, 병합하지 않음').

## 사후 탐색 → 발표 자료 (04:14)
- `docs/PRESENTATION_NOTES.md` 6절 '한계와 다음 일'에 '사후 탐색 (공식 결과 아님)' 표와 말할 것 2줄을 덧붙였다.
