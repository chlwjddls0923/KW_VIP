# 텍스트 명령 엘리베이터 버튼 누르기 (휠체어–PiPER, MuJoCo)

팀명·팀원: [ ] / 발표·제출일: [ ]

> 작성 중. 단계 7에서 완성한다.

## 실행 환경
- Mac mini (Apple M4, 16 GB), macOS 26.7.1, GPU 사용 안 함
- Python 3.11.13 (Homebrew `/opt/homebrew/bin/python3.11`)

## 설치
```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 환경 점검
```bash
.venv/bin/python scripts/check_env.py     # out/check_head.png 생성
.venv/bin/python -m pytest
```

## 렌더링 백엔드
- `mujoco.Renderer`(화면 없는 오프스크린 렌더링)를 OS 기본 백엔드로 쓴다. macOS에서는 `MUJOCO_GL`을 설정하지 않는다.
- 창이 없는 Linux에서만 `MUJOCO_GL=egl`을 설정한다.
- 창을 띄우는 viewer는 쓰지 않는다.
