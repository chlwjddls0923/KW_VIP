# 진행 상황

계획서: `생활보조로봇_ClaudeCode_계획프롬프트.md` (이 파일만 보고 이어받을 수 있게 쓴다)

## 고정 사항
- 실행 PC: Mac mini (Apple M4, 16 GB, 10코어), macOS 26.7.1, GPU 없음
- Python 3.11.13, 가상환경 `.venv` (Homebrew python3.11로 생성. 3.14는 쓰지 않음)
- 성공 기준 변위 10 mm. 팀명·팀원 [ ], 발표·제출일 [ ]
- macOS: MUJOCO_GL 설정 안 함, viewer 쓰지 않음, git push·원격 설정 안 함
- `data/commands_holdout.tsv`, `data/commands_team.tsv`는 사용자가 단계 6에 넣는다. 그 전에는 찾거나 만들지 않는다. `.gitignore`에 들어 있다.

## 단계별 상태
| 단계 | 상태 | 비고 |
|---|---|---|
| 0 환경과 모델 확인 | 완료 | check_env OK, test_model_facts 6/6 |
| 1 장면 생성기 | 대기 | |
| 2 IK와 누르기 | 대기 | |
| 3 인식 | 대기 | |
| 4 명령 해석 | 대기 | |
| 5 통합 | 대기 | |
| 6 평가 | 대기 | |
| 7 영상과 문서 | 대기 | |

## 단계 0 기록
- 설치: mujoco 4.0.1, kiwipiepy 0.24.1 (+kiwipiepy_model 0.24.0), numpy 2.4.6, scipy 1.17.1, pillow 13.0.0, imageio 2.38.2, imageio-ffmpeg 0.8.1, psutil 7.2.2, pytest 9.2.0
- 원본 모델: nq 16, nv 15, nu 7, timestep 0.002. 3절의 구조 항목(관절 범위, 버튼·패널 위치, slide 축·범위·stiffness, button_target 25 mm, 충돌 geom, 도구 축, link6 캡슐 앞끝 +12 mm, finger_pad 앞면 −56 mm) 모두 일치
- 주의: link6 캡슐은 geom z축이 fromto 방향과 반대다. 앞끝은 양 끝 중 ee_site z축 방향으로 더 앞인 쪽으로 계산한다.
- 원본의 오프스크린 버퍼는 640×480 (1280×960은 단계 1에서 build/scene.xml에 추가)
- `mujoco.mj_geomDistance` 있음 (단계 2 거리 시험에 사용)
- 렌더링: macOS 기본 백엔드로 `mujoco.Renderer` 정상 동작

## 다음 할 일
- 단계 1: `src/assist/scene.py` (부록 A), `tests/test_scene.py`
