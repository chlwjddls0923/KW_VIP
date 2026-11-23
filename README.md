# 텍스트 명령 엘리베이터 버튼 누르기 (휠체어–PiPER, MuJoCo)

팀명·팀원: [ ] / 발표·제출일: [ ]

휠체어에 단 AgileX PiPER 팔이 한국어 텍스트 명령('3층 버튼을 눌러줘')을 해석하고, head 카메라 RGB-D로 버튼을 찾아 스스로 누른다.
명령 해석은 kiwipiepy 형태소 분석과 규칙, 인식은 색 분할·깊이·숫자 템플릿 매칭, 동작은 최소자승 IK와 위치 제어로 한다. 모든 계산은 이 컴퓨터에서 하고 외부 서버를 쓰지 않는다.

- 동작 설명(관측, 텍스트의 영향, 관절 명령, 성공률 계산): `docs/EXPLAIN.md`
- 원본 모델 대비 바꾼 것: `docs/MODEL_CHANGES.md`
- 평가 결과: `results/summary.md`, 영상: `results/video/`(목록 `results/video/index.md`)
- 진행 기록: `docs/PROGRESS.md`

## 실행 환경

- Mac mini (Apple M4, 16 GB), macOS 26.7.1, GPU 사용 안 함
- Python 3.11 (확인한 버전 3.11.13, Homebrew `/opt/homebrew/bin/python3.11`). 계획서 기준 3.11~3.13

## 설치

프로젝트 폴더에서 실행한다. 패키지는 프로젝트 안 가상환경 `.venv`에만 설치한다.

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/check_env.py      # 버전, 모델 로드, out/check_head.png, 형태소 분석 확인
```

## 실행 (데모)

```bash
.venv/bin/python scripts/demo.py --text "3층 버튼을 눌러줘"                 # 기준 위치
.venv/bin/python scripts/demo.py --text "4층으로 가자" --seed 5001          # 부록 E 변화 조건 규칙으로 만든 장면
.venv/bin/python scripts/demo.py --text "3층 누르지 마"                     # 움직이지 않고 '대기합니다'
.venv/bin/python scripts/demo.py --text "3층 눌러줘" --record out/demo.mp4   # 실행하며 mp4로 저장
.venv/bin/python scripts/demo.py                                            # 문장을 입력받는다(빈 줄이면 끝)
```

출력 예:

```
[장면] 기준 위치
[로봇] 3층 버튼을 누릅니다
[로봇] 3층 버튼 눌림 확인 (15.1 mm)
[판단] 해석 PRESS(3) → 행동 PRESS, 보이는 층 [1, 2, 3, 4, 5, 6], 해석 0.15 ms, 인식 182 ms, 작업 9.88 s(시뮬레이션)
```

## 테스트

```bash
.venv/bin/python -m pytest          # 단계 0~5 통과 기준 (약 30초)
```

## 평가 재현

공식 조건은 `data/eval_protocol.json`에 있다. 결과 폴더가 이미 있으면 `eval.py`는 덮어쓰지 않고 멈추므로, 다시 실행할 때는 `--out`으로 새 폴더를 준다.

```bash
.venv/bin/python scripts/sysinfo.py                                  # results/sysinfo.json
.venv/bin/python scripts/eval.py official --out results/rerun2       # 공식 25회 (원본: results/official_run1)
.venv/bin/python scripts/eval.py baseline --out results/baseline_x   # 고정 좌표 기준선 (원본: results/baseline_run1)
.venv/bin/python scripts/eval.py supplementary --out results/supp_x  # 추가 200회 (원본: results/supplementary)
.venv/bin/python scripts/eval.py nlu                                 # dev 해석 정확도 (holdout은 기존 결과를 다시 쓴다)
.venv/bin/python scripts/eval.py summary                             # results/summary.md 다시 만들기
.venv/bin/python scripts/record.py --trial V03                       # 시행 녹화 → results/video/
```

## 렌더링 백엔드

- `mujoco.Renderer`(화면 없는 오프스크린 렌더링)를 OS 기본 백엔드로 쓴다. macOS에서는 `MUJOCO_GL`을 설정하지 않는다.
- 창이 없는 Linux에서만 `MUJOCO_GL=egl`을 설정한다.
- 창을 띄우는 viewer는 쓰지 않는다.
- macOS에서는 깊이 렌더링 때 `ARB_clip_control unavailable ... depth accuracy will be limited` 경고가 나온다. 오류가 아니다. 이 환경에서 잰 인식 오차는 `docs/EXPLAIN.md` 0절에 있다.

## 외부 도구와 사전 학습 모델의 출처

| 이름 | 쓰는 곳 | 출처 |
|---|---|---|
| MuJoCo 4.0.1 | 물리 시뮬레이션, 렌더링 | Google DeepMind, https://github.com/google-deepmind/mujoco |
| MuJoCo Menagerie AgileX PiPER | 팔의 관절 구조·범위·액추에이터 설정. 과제 모델 `wheelchair_piper_lite.xml`이 이 모델에서 옮겨 적었다고 파일 머리말에 밝힘(MIT 라이선스, RosenYin 2024) | https://github.com/google-deepmind/mujoco_menagerie (agilex_piper) |
| kiwipiepy 0.24.1, kiwipiepy_model 0.24.0 | 한국어 형태소 분석. 들어 있는 사전 학습 모델을 형태소 분리에만 쓰고 판단은 규칙으로 한다 | Kiwi (bab2min), https://github.com/bab2min/kiwipiepy |
| numpy, scipy, pillow, imageio, imageio-ffmpeg, psutil, pytest | 계산, 최소자승(scipy.optimize.least_squares), 영상 처리(scipy.ndimage), 그림·영상 저장, 사양 기록, 시험 | PyPI 각 패키지 |

직접 학습한 모델은 없다.
