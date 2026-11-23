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
