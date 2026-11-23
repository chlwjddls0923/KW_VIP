# 진행 상황

계획서: `생활보조로봇_ClaudeCode_계획프롬프트.md` (이 파일만 보고 이어받을 수 있게 쓴다)

## 고정 사항
- 실행 PC: Mac mini (Apple M4, 16 GB, 10코어), macOS 26.7.1, GPU 없음
- Python 3.11.13, 가상환경 `.venv` (Homebrew python3.11로 생성. 3.14는 쓰지 않음)
- 성공 기준 변위 10 mm. 팀명·팀원 [ ], 발표·제출일 [ ]
- macOS: MUJOCO_GL 설정 안 함, viewer 쓰지 않음, git push·원격 설정 안 함
- `data/commands_holdout.tsv`, `data/commands_team.tsv`는 사용자가 단계 6에 넣는다. 그 전에는 찾거나 만들지 않는다. `.gitignore`에 들어 있다.

## 계획과 다르게 한 것 (사용자 승인, 유지)
1. `.gitignore`에 `data/commands_holdout.tsv`, `data/commands_team.tsv`를 넣었다(사용자 지시). 계획서 4절은 `data/` 전체 커밋이지만 이 두 파일은 커밋하지 않는다.
2. 경로 상수 모음 `src/assist/paths.py`를 추가했다(계획서 5절 목록에 없는 보조 파일).
3. `requirements.txt`는 mujoco·kiwipiepy 외 패키지도 설치된 버전으로 고정했다(재현성).
4. `tests/test_model_facts.py`에 단계 0의 (a)(b) 외에 3절 구조 항목 테스트 4개(모델 크기, 관절 범위, 버튼·패널, 도구 축·충돌 위치)를 더 넣었다.

## 단계별 상태
| 단계 | 상태 | 비고 |
|---|---|---|
| 0 환경과 모델 확인 | 완료 | check_env OK, test_model_facts 6/6 |
| 1 장면 생성기 | 완료 | test_scene 6/6 |
| 2 IK와 누르기 | 완료 | test_control 3/3 |
| 3 인식 | 완료 | test_perception 2/2 |
| 4 명령 해석 | 완료 | test_nlu 22/22, dev 78/78 |
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

## 단계 1 기록
- `scene.py`: `build_scene(layout, shuffle_seed, radius)` → `build/scene.xml`, `build/digit_{n}.png`. `Scene(...)`, `reset(dpos, yaw_deg, light)`, `truth()`, `slides()`, `arm_q()`, `renderer`(1280×960, 지연 생성), `close()`
- 수정 장면: nq 21, nv 20, nu 7. button_target site 삭제, `wrist_collider` 충돌, 오프스크린 1280×960, `overview` 카메라(pos 1.35 0.35 1.55 → 0.25 −0.50 0.92 바라봄, fovy 55)
- 숫자 텍스처는 뒤집지 않아도 정면에서 바로 읽힌다(MuJoCo 4.0.1, macOS). 정면에서 아래부터 '1 2 / 3 4 / 5 6'
- `truth()`의 라벨 중심은 slide 0 기준(패널 자세 + (x, 0.081, z))이다. 법선 = 패널 +y축
- 대기 1.2초: slide 최대 0 mm, 관절 변화 최대 9.3e−8 rad
- `layout_string(layout)`: P1~P6에 놓인 층 문자열(평가 기록용)

## 단계 2 기록
- `ik.py`: `IK(model).solve(p_des, z_des, q_seed, max_nfev=200)` → (q, 위치 오차 m, 방향 오차 도). FK 전용 MjData를 따로 쓴다. `Q_READY` 상수
- `motion.py`: `Controller(model, data)`. `tick/hold/move_joint/move_line`, `plan_press(center, normal)`(접근·누름 IK, 1 mm 넘으면 ok=False), `execute_press(plan, q_home)`, `press(...)`. `step_hooks`(mj_step마다, 채점 신호), `tick_hooks`(0.02초마다, 영상·거리). reset 뒤 `sync()` 필수
- IK 600개(시드 8001~8100 × 6): 위치 오차 최대 0.0013 mm, 기울기 중앙값 5.3°·최대 37.4°, 접근 IK 1.5~17.6 ms(중앙값 5.1)
- 누르기 20회(시드 6001~6020): 20/20, 목표 14.85~15.43 mm, 다른 버튼 0 mm
- 팔 링크(link2~8)–환경 최소 거리: 패널 27.5 mm, 다른 버튼 31.5 mm 이상, 오른쪽 팔걸이 87.2 mm, 등받이 71.4 mm (거리 계산 상한 200 mm)
- 원본 XML, ee_site → button_target(z_des (0,−1,0)) 1초 유지: button_3_slide 최대 0 mm
- 참고 측정: 원본 버튼 앞 10 cm 최소 기울기 약 11°(joint5가 한계 1.19에 닿음)

## 단계 3 기록
- `camera.py`: `Frame`(rgb, depth, fovy, cam_xpos, cam_xmat; `backproject`, `project`), `capture(renderer, model, data, camera)`
- `perception.py`: `detect(frame, templates, debug=None)` → `[{floor, score, margin, center, normal}]`, `make_templates(floors)`, `sample_patch`, `zncc_shift`, `save_debug`
- `scene.py`에 `layout_from_perm(perm)` 추가 (변화 조건의 `rng.permutation(6)` 결과로 배치를 만든다)
- 변화 40장면(시드 7001~7040): 높이 0.90 m 이상 검출 222/222, 0.90 m 미만 13/18, 받아들인 판독 235개 중 오독 0, 중심 오차 중앙값 0.46 mm·최대 1.28 mm, 법선 오차 최대 0.013°
- 라벨 방향(기준 위치): 원래 템플릿 0.873~0.927, 뒤집은 템플릿 최대 0.840(6층 좌우 반전). 모두 원래가 더 높다
- macOS 렌더링 경고: `ARB_clip_control unavailable while mjDEPTH_ZEROFAR requested, depth accuracy will be limited`. 깊이 정밀도가 제한된다는 뜻이지만 위 오차 기준은 통과
- 숫자 텍스처는 뒤집지 않는다(정면화 패치에서 바로 선 숫자로 보임, `out/perception_debug.png`)

## 뒤 단계에서 할 일 (사용자 지시)
- 단계 7: `docs/EXPLAIN.md`의 실행 환경에 macOS 깊이 정밀도 경고(`ARB_clip_control unavailable …`)와 단계 3 측정값(중심 오차 중앙값 0.46 mm·최대 1.28 mm, 법선 오차 최대 0.013°)을 적는다.

## 단계 4 기록
- `nlu.py`: `parse(text)` → {intent, floor, scores, events, floors, candidates, tokens}, `ground(parsed, seen_floors)` → {action, floor, reason('ok'/'not_visible'/'wait'/'clarify'/'unsupported')}, `digits_only(text)`, `get_kiwi()`, `INIT_MS`
- `data/commands_dev.tsv`: 부록 F 78문장 (PRESS 28, WAIT 24, REJECT 19, CLARIFY 7)
- dev 78/78, 눌러선 안 되는 문장의 PRESS 0건. `digits_only` dev 22/78
- 문장당 해석 0.052 ms(중앙값), 최대 0.362 ms. 분석기 초기화(생성 + 첫 tokenize) 838 ms
- 부록 D 알려진 한계 9문장이 계획서 설명대로 재현됨(`test_known_limits_reproduce`). 고치지 않고 단계 7 EXPLAIN.md에 적는다
- 규칙은 dev 문장으로만 맞췄다(첫 구현에서 78/78이라 가중치 조정 없음). holdout은 열지 않았다

## 다음 할 일
- 단계 5: `src/assist/protocol.py` (부록 E), `src/assist/pipeline.py`, `scripts/demo.py`, `tests/test_pipeline.py`
