# 팀원 PC 설치·확인 안내

텍스트 명령 엘리베이터 버튼 누르기(룰기반 본 시스템)를 팀원 PC에서 실행하고 확인하는 방법이다.
LLM 실험은 본 시스템에 연결하지 않았으므로 여기서 다루지 않는다(`exp/llm-fallback` 브랜치의 `experiments/llm/TEAM_SETUP_LLM.md`).

**표시 규칙**
- ✅ 확인함: 2026-11-24에 macOS(Apple M4)에서 새로 복제한 저장소로 실제 실행했다(`docs/OVERNIGHT_REPORT.md` 작업 1).
- [미확인]: 실행해 보지 않았다. Windows 항목은 모두 [미확인]이다.

## 1. 준비물

| 항목 | macOS | Windows |
|---|---|---|
| Python | 3.11~3.13. 확인한 것은 Homebrew 3.11.13 ✅ | python.org 설치본 3.11~3.13 [미확인] |
| git | Xcode Command Line Tools 또는 Homebrew | Git for Windows [미확인] |
| GPU | 필요 없음 | 필요 없음 |
| 디스크 | 가상환경 포함 [약 몇백 MB, 미측정] | 같음 |

계획서 기준 Python은 3.11~3.13이다. 다른 버전에서는 `mujoco==4.0.1` 휠이 없을 수 있다 [확인 필요].

## 2. 받기

저장소는 GitHub에 공개되어 있다.

```bash
git clone https://github.com/chlwjddls0923/KW_VIP.git
cd KW_VIP
```

`main` 브랜치가 본 시스템이다. 다른 브랜치(`exp/...`)는 실험용이다.

## 3. 설치

### macOS ✅

```bash
/opt/homebrew/bin/python3.11 -m venv .venv          # 다른 경로의 python3.11~3.13이어도 된다
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/check_env.py
```

### Windows (PowerShell) [미확인]

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\check_env.py
```

이후 명령에서 `.venv/bin/python`은 Windows에서 `.venv\Scripts\python`으로 바꿔 쓴다.

**기대 출력** (`check_env.py`, macOS에서 확인 ✅): 마지막 줄이 `check_env OK`이고 `out/check_head.png`가 생긴다.

```
mujoco     4.0.1
...
model      nq=16 nv=15 nu=7 timestep=0.002
render     out/check_head.png (480, 640, 3) mean=22.8
kiwi init  364 ms, tokenize 417.88 ms
tokens     '3층 버튼을 눌러줘': 3/SN 층/NNG 버튼/NNG 을/JKO 누르/VV 어/EC 주/VX 어/EF
check_env OK
```

시간은 PC마다 다르다. 설치는 macOS에서 7초였는데, 이 PC에 pip 캐시가 있었기 때문이다. 처음 받는 PC는 [더 걸림, 미측정].

## 4. 확인 명령

### 4-1. 테스트 ✅

```bash
.venv/bin/python -m pytest
```

기대 출력: `42 passed` (macOS에서 36.7초).

### 4-2. 데모: 명령 점검 5문장 ✅

```bash
.venv/bin/python scripts/demo.py --text "3층 버튼을 눌러줘"
.venv/bin/python scripts/demo.py --text "엘리베이터 3층을 선택해 줘"
.venv/bin/python scripts/demo.py --text "버튼은 누르지 말고 대기해"
.venv/bin/python scripts/demo.py --text "3층 누르지 마"
.venv/bin/python scripts/demo.py --text "현재 장면에 없는 7층 버튼을 눌러줘"
```

| 문장 | 기대 행동 | 기대 출력 (macOS 확인) |
|---|---|---|
| 3층 버튼을 눌러줘 | PRESS 3 | `[로봇] 3층 버튼 눌림 확인 (15.1 mm)` |
| 엘리베이터 3층을 선택해 줘 | PRESS 3 | `[로봇] 3층 버튼 눌림 확인 (15.1 mm)` |
| 버튼은 누르지 말고 대기해 | WAIT, 움직이지 않음 | `[로봇] 대기합니다` |
| 3층 누르지 마 | WAIT, 움직이지 않음 | `[로봇] 대기합니다` |
| 현재 장면에 없는 7층 버튼을 눌러줘 | REJECT, 움직이지 않음 | `[로봇] 7층 버튼이 보이지 않아 수행할 수 없습니다` |

전체 출력 예(첫 문장):

```
[장면] 기준 위치
[로봇] 3층 버튼을 누릅니다
[로봇] 3층 버튼 눌림 확인 (15.1 mm)
[판단] 해석 PRESS(3) → 행동 PRESS, 보이는 층 [1, 2, 3, 4, 5, 6], 해석 0.17 ms, 인식 176 ms, 작업 9.88 s(시뮬레이션)
```

- 눌림 값(mm)과 '작업 9.88 s'는 시뮬레이션 값이라 PC가 달라도 같아야 한다.
  다르면 알려 달라: 렌더러·라이브러리 차이일 수 있다 [Windows 미확인].
- '해석 … ms', '인식 … ms'는 계산 시간이라 PC마다 다르다.

### 4-3. 변화 조건 데모 ✅

```bash
.venv/bin/python scripts/demo.py --text "4층으로 가자" --seed 5001
```

기대 출력: `시드 5001: 패널 이동 (-0.054, +0.027, -0.087) m, 회전 +1.7°, 조명 1.06배, 숫자 배치 356142`, `4층 버튼 눌림 확인 (15.3 mm)`.

### 4-4. 해석 평가 ✅

```bash
.venv/bin/python scripts/eval.py nlu
```

기대 출력: dev `correct 78 / n 78`, holdout `29/30`.
holdout은 기존 결과를 다시 쓰고 다시 실행하지 않는다. 이 명령은 `results/nlu/dev.csv`와 `nlu_summary.json`을 다시 쓰므로, 팀원 PC에서는 커밋하지 않는다.

## 5. 자주 나는 오류와 대처

| 증상 | 원인 | 대처 |
|---|---|---|
| `ARB_clip_control unavailable … depth accuracy will be limited` | macOS 렌더러 경고 | 오류 아님. 그대로 진행 ✅ |
| `pip install`에서 mujoco 버전을 못 찾음 | Python 버전이 3.11~3.13이 아님 | Python 3.11로 가상환경을 다시 만든다 [Windows 미확인] |
| 첫 실행이 1~2초 느림 | kiwipiepy가 처음 호출할 때 모델을 읽음 | 정상 ✅ |
| 한글 출력이 깨짐 (Windows 콘솔) | 콘솔 인코딩 | `chcp 65001` 또는 `$env:PYTHONUTF8=1` 뒤에 다시 실행 [미확인] |
| 렌더링 오류 (창 없는 Linux) | OpenGL 백엔드 없음 | `MUJOCO_GL=egl` 설정(README 참고). macOS·Windows에서는 설정하지 않는다 |
| `results/... 이미 있음: 덮어쓰지 않고 멈춘다` | `eval.py official` 등은 기존 결과를 덮어쓰지 않음 | `--out results/새폴더`로 실행한다 |
| `python` 명령을 찾지 못함 (Windows) | PATH 미설정 | `py -3.11`을 쓰거나 설치 때 'Add to PATH'를 켠다 [미확인] |

## 6. 확인한 것과 확인하지 못한 것

| 항목 | macOS (Apple M4) | Windows |
|---|---|---|
| clone → venv → requirements 설치 | ✅ | [미확인] |
| check_env.py | ✅ | [미확인] |
| pytest 42개 | ✅ | [미확인] |
| demo 명령 점검 5문장 + 시드 5001 | ✅ | [미확인] |
| eval.py nlu (dev 78/78, 원본과 같음) | ✅ | [미확인] |
| 공식 평가 재실행 (`eval.py official --out ...`) | 이번에는 실행하지 않음(이전 단계 6에서 rerun이 run1과 25/25 일치) | [미확인] |
| 녹화 (`--record`, imageio-ffmpeg) | 이번에는 실행하지 않음 | [미확인] |

팀원 PC에서 확인하면 OS, Python 버전, 4절 명령의 결과를 알려 달라. 이 표를 갱신한다.
