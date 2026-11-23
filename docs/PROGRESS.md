# 진행 상황

계획서: `생활보조로봇_ClaudeCode_계획프롬프트.md` (이 파일만 보고 이어받을 수 있게 쓴다)

## 고정 사항
- 실행 PC: Mac mini (Apple M4, 16 GB, 10코어), macOS 26.7.1, GPU 없음
- Python 3.11.13, 가상환경 `.venv` (Homebrew python3.11로 생성. 3.14는 쓰지 않음)
- 성공 기준 변위 10 mm. 팀명·팀원 [ ], 발표·제출일 [ ]
- macOS: MUJOCO_GL 설정 안 함, viewer 쓰지 않음, git push·원격 설정 안 함
- `data/commands_holdout.tsv`, `data/commands_team.tsv`는 사용자가 단계 6에 넣는다. 그 전에는 찾거나 만들지 않는다. `.gitignore`에 들어 있다.

## 계획과 다르게 한 것 (사용자 승인, 유지)
1. `.gitignore`에 `data/commands_holdout.tsv`, `data/commands_team.tsv`를 넣었다(사용자 지시). holdout은 평가가 끝난 뒤 사용자 지시로 `.gitignore`에서 빼고 커밋했다. `data/commands_team.tsv`는 계속 커밋하지 않는다.
2. 경로 상수 모음 `src/assist/paths.py`를 추가했다(계획서 5절 목록에 없는 보조 파일).
3. `requirements.txt`는 mujoco·kiwipiepy 외 패키지도 설치된 버전으로 고정했다(재현성).
4. `tests/test_model_facts.py`에 단계 0의 (a)(b) 외에 3절 구조 항목 테스트 4개(모델 크기, 관절 범위, 버튼·패널, 도구 축·충돌 위치)를 더 넣었다.
5. (단계 5) 움직이지 않는 판단 뒤에도 1초 진행해 정지 상태를 기록한다. 이유는 단계 5 기록 참고.

## 단계별 상태
| 단계 | 상태 | 비고 |
|---|---|---|
| 0 환경과 모델 확인 | 완료 | check_env OK, test_model_facts 6/6 |
| 1 장면 생성기 | 완료 | test_scene 6/6 |
| 2 IK와 누르기 | 완료 | test_control 3/3 |
| 3 인식 | 완료 | test_perception 2/2 |
| 4 명령 해석 | 완료 | test_nlu 22/22, dev 78/78 |
| 5 통합 | 완료 | test_pipeline 3/3, dev 시드 20/20 |
| 6 평가 | 완료 | 공식 run1·run2 25/25(일치), rerun 일치, 기준선 6/20, 추가 199/200, dev 78/78, holdout 29/30 |
| 7 영상과 문서 | 완료 | 영상 8개(평가와 일치), EXPLAIN·MODEL_CHANGES·README |

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

## 단계 4 기록
- `nlu.py`: `parse(text)` → {intent, floor, scores, events, floors, candidates, tokens}, `ground(parsed, seen_floors)` → {action, floor, reason('ok'/'not_visible'/'wait'/'clarify'/'unsupported')}, `digits_only(text)`, `get_kiwi()`, `INIT_MS`
- `data/commands_dev.tsv`: 부록 F 78문장 (PRESS 28, WAIT 24, REJECT 19, CLARIFY 7)
- dev 78/78, 눌러선 안 되는 문장의 PRESS 0건. `digits_only` dev 22/78
- 문장당 해석 0.052 ms(중앙값), 최대 0.362 ms. 분석기 초기화(생성 + 첫 tokenize) 838 ms
- 부록 D 알려진 한계 9문장이 계획서 설명대로 재현됨(`test_known_limits_reproduce`). 고치지 않고 단계 7 EXPLAIN.md에 적는다
- 규칙은 dev 문장으로만 맞췄다(첫 구현에서 78/78이라 가중치 조정 없음). holdout은 열지 않았다

## 단계 5 기록
- `protocol.py`: `Trial`, `basic_trial`, `variation_trial`(부록 E 추출 순서 그대로), `check_trials`, `official_trials`, `baseline_trials`(FB/FV), `supplementary_trials`, `dev_trials`, `judge(trial, rec)`, `wilson`, 실패 유형 상수·한국어 이름
- `pipeline.py`: `Assistant(scene, mode='full'|'baseline_fixed', say)`.`run(text)`, `SceneCache`, `run_trial(trial, cache)` → trials.csv 한 줄, `CSV_COLUMNS`
- 움직이지 않는 판단(WAIT·CLARIFY·REJECT·층 없음·IK 불가) 뒤에도 1초 진행해 정지 상태를 기록한다(`STILL_HOLD_S`)
  - 이유(사용자 승인, 유지): 판단 직후 끝내면 '팔 관절 최대 변화 < 0.02 rad', '버튼 slide < 1 mm' 판정이 측정 시간 0으로 이루어진다. 실제로 정지해 있는지 1초 동안 기록해 판정 근거로 삼는다. 단계 6 `results/summary.md`의 평가 방법에도 적는다.
- 기준선 `baseline_fixed`는 인식 없이 보이는 층 = 1~6, 라벨 중심 = (0.43, −0.87, 0.99) + (x, 0.081, z), 법선 (0, 1, 0)
- 명령 8종 8/8, 움직이면 안 되는 명령 관절 최대 변화 0 rad(표시 자릿수 기준)
- 버튼 1개 장면: '3층 눌러줘' 15.3 mm 성공, '4층 눌러줘' 거부(관절 8.9e−8 rad)
- 개발용 시드 5001~5020: 20/20 (목표 높이 0.877, 0.882 m인 D15, D02도 성공). t_press 5.39~5.58 s, t_task 9.86~9.88 s, 인식 102~110 ms
- `scripts/demo.py --text … [--seed N]`, 인자 없으면 입력받기

## 단계 6 기록
- `data/eval_protocol.json` 작성 후 커밋(9b64b7f)하고 실행. `eval.py official/baseline`은 커밋된 파일과 조건이 같은지 확인한 뒤에만 돈다
- `scripts/eval.py {protocol|official|baseline|supplementary|nlu|summary} [--out DIR]`. 결과 폴더가 있으면 덮어쓰지 않고 멈춘다. 폴더마다 `trials.csv`, `details.jsonl`(메시지·검출·예외), `run_info.json`
- `scripts/sysinfo.py` → `results/sysinfo.json`
- 공식 `results/official_run1/`(1회 실행): 25/25. 기본 10/10, 변화 10/10, 점검 5/5. t_press 중앙값 5.45 s, t_task 9.87 s. V02는 목표 변위 13.7 mm(다른 시행 약 15 mm)
- 재현 `results/rerun/`: success 열 25/25 일치. 첫 실행 때 `--out`의 상대 경로 때문에 마지막 출력 줄에서 오류가 났다(결과 파일 25행과 run_info는 모두 기록됨). `--out`을 절대 경로로 바꾸게 고쳤고 재현 결과는 그대로 썼다
- 기준선 `results/baseline_run1/`: 6/20 (기본 6/10, 변화 0/10). 실패 14건 모두 '접촉 10 mm 미달'
- 추가 `results/supplementary/`: 199/200 (기본 100/100, 변화 99/100). SV024 목표 높이 0.83 m 미검출
- 해석 `results/nlu/`: dev 78/78(digits_only 22/78, 눌러선 안 되는 문장의 PRESS 0 / 29). holdout은 사용자가 `~/Desktop/mojuco/`에 둔 파일을 사용자 지시로 `data/`에 옮긴 뒤 1회 실행: 29/30(digits_only 12/30), 눌러선 안 되는 문장의 PRESS 0 / 2. 틀린 1건 '3층 누를까 말까'는 기대 CLARIFY, 결과 REJECT(움직이지 않음). 규칙은 고치지 않았다. team 없음
- 요약: `results/summary.md`, `results/summary.json` (`eval.py summary`로 다시 만든다). 평가 방법에 정지 판단 뒤 1초 기록의 이유를 적었다
- 공식 결과를 본 뒤 코드(판단·동작)를 고치지 않았다. `eval.py`의 경로 처리와 요약 표기만 고쳤다
- 사용자 지시: `eval.py` 수정도 공식 결과를 본 뒤 고친 코드이므로 `results/CHANGELOG.md`에 적고(커밋 2926bc8) `results/official_run2/`에 공식 25회를 다시 실행했다. run2 25/25, success 열 run1과 25/25 일치(목표 변위·실패 유형 열도 같음). `summary.md`에 run1·run2를 모두 적고 비교 표를 넣었다
- 사용자 지시: holdout 평가가 끝났으므로 `.gitignore`에서 `data/commands_holdout.tsv`를 빼고 `data/commands_holdout.tsv`, `results/nlu/holdout.csv`를 커밋했다(97ae11a). `data/commands_team.tsv` 줄은 그대로

## 단계 7 기록
- `src/assist/record.py`(`Recorder`): 판단·동작 코드를 고치지 않고 say 콜백·tick_hooks·녹화 중 pipeline의 detect/parse 감싸기로 화면을 만든다. 왼쪽 overview, 오른쪽 head_rgb(검출 원, 목표 노란색, 2배 확대 화면), 아래 글자(명령 영문 풀이, 판단, 목표 변위, 시뮬레이션 경과 시간). 앞뒤 1초 정지 화면은 물리 진행 없이 같은 프레임을 반복
- 영상 글자는 영문이다. 한글 글꼴 파일이 프로젝트 폴더 밖(macOS 시스템 글꼴)에 있어 쓰지 않았다(계획서 단계 7의 대안)
- `scripts/record.py --trial ID` → `results/video/{ID}_{결과}[_seed{시드}].mp4`, `results/video/videos.json`, `results/video/index.md`. 녹화 결과가 해당 trials.csv(success·실패 유형·목표 변위)와 같은지 기록
- `scripts/demo.py --text … --record out.mp4`
- 영상 8개(모두 평가와 일치): V03 성공, C01~C05, SV024 실패(추가 시험, 공식 20회 밖, 인식 미검출, 시드 4024), FB03 기준선 실패(비교용 보조, 접촉 10 mm 미달 7.0 mm, 시드 1003). 사용자 지시대로 일부러 실패를 만들지 않았다
- 문서: `docs/EXPLAIN.md`(실행 환경과 macOS 깊이 경고·단계 3 측정값, 네 가지 질문과 코드 위치, CLARIFY 경우, 알려진 한계와 추가로 확인한 점, 영상 목록), `docs/MODEL_CHANGES.md`, `README.md`
- README의 데모 명령 5개를 그대로 실행해 확인. pytest 42/42
- 추가로 확인한 한계(규칙은 고치지 않음): '기다렸다가 3층 눌러' → PRESS(3) 즉시 누름

## 다음 할 일
- 전체 완료. 사람이 확인할 것: 영상(results/video/), 숫자 방향(out/scene_head.png, out/perception_debug.png), 발표에 밝힐 모델 수정(docs/MODEL_CHANGES.md), 팀명·팀원·발표일 [대괄호]
