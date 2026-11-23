# 야간 작업 보고 (2026-11-24, 03:32~)

> 요약 표와 '내가 정해야 할 것'은 작업 5에서 이 위에 채운다.

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
