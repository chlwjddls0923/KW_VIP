새 작업: '규칙 + 작은 LLM' 실험. 측정만 하고 본 시스템은 바꾸지 않는다.
먼저 이 메시지 전문을 experiments/llm/PLAN.md로 저장하고, 대화가 길어지면 그 파일을 다시 읽어.

목표
- 처음 보는 표현에 가장 잘 대응하는 조합(모델 × 프롬프트 변형 × 결합 방식)을 찾는다.
- 자원 조건: 맥미니 M4 16 GB. 최종 추론은 CPU만 쓴다고 가정한다(팀원 PC).
- 지킬 조건: 위험한 실패 0건, 공식 문장 35개의 결과가 규칙만일 때와 같음.

용어
- 위험한 실패: 누르면 안 되는 문장에서 PRESS가 나오거나, 기대와 다른 층을 PRESS.
- 안전한 실패: 그 밖의 오답.
- 공식 문장 35개: 계획서 부록 E의 점검 5문장 + 문장 틀 5개 × 1~6층.
- 보이는 층은 1~6으로 둔다.

범위와 금지
- 브랜치 exp/llm-fallback에서만 작업한다. push와 원격 설정은 하지 마.
- 수정 금지: src/assist/, scripts/, tests/, 기존 data/ 파일, 기존 results/ 폴더. src/assist/nlu.py는 import만 한다. 규칙은 고치지 않는다.
- 새 코드는 experiments/llm/, 결과는 results/exp_llm/에 둔다.
- 가상환경: 기존 .venv는 건드리지 말고 /opt/homebrew/bin/python3.11로 .venv-llm을 만든다(.gitignore에 추가).
- 허용 패키지: llama-cpp-python, huggingface_hub, kiwipiepy==0.24.1(규칙 import용), numpy, psutil, pytest. 그 밖은 먼저 물어봐.
- 실행 도구는 llama-cpp-python + GGUF로 고정한다. mlx 계열은 쓰지 않는다(팀원 PC가 Windows일 수 있다).
- llama-cpp-python은 PyPI에 소스만 있어서 설치 중에 컴파일된다. 컴파일러가 없어 실패하면 시스템에 아무것도 설치하지 말고 오류와 함께 멈춰. 설치한 버전과 방법(소스 빌드 / 미리 빌드된 휠)을 기록해.
- 모델 파일은 models/에만 받는다(local_dir=models/, HF_HOME=models/.hf). models/는 .gitignore에 넣는다. 프로젝트 폴더 밖에는 쓰지 않는다.
- holdout 30문장과 adv_test는 4단계 전에는 실행하지도 참고하지도 않는다.
- 지식 증류, 가지치기, 본 시스템 연결은 하지 않는다.

1단계: 후보 확인 (끝나면 보고하고 멈춰)
- 아래 후보의 저장소, 파일 이름, 크기, 라이선스, sha256을 Hugging Face에서 확인해 표로 적는다. 양자화는 Q4_K_M. 공식 GGUF가 없으면 누가 변환한 파일인지 적는다.
  A. Qwen3.5-4B (Apache-2.0)
  B. Qwen3.5-2B (Apache-2.0)
  C. kanana-2-3b-instruct (Kanana Open License, 한국어 특화). GGUF를 못 구하거나 로드가 안 되면 EXAONE-4.0-1.2B(공식 GGUF, 비상업 라이선스)로 대체
  D. Qwen3.5-9B: 상한 확인용이다. 최종 선택 대상이 아니다
- 더 나은 후보가 있으면 이유와 함께 제안만 한다(예: Gemma 4 E2B·E4B). 최종 목록은 내가 정한다.
- 남은 디스크 용량, 다운로드 합계, 예상 실행 시간을 적는다.
- llama-cpp-python을 설치하고 B만 받아서 로드와 JSON 스키마 강제 출력이 되는지 확인한다. 로드되지 않으면(구조 미지원 등) 오류를 그대로 보고하고 대안을 제안만 한다.

2단계: 데이터와 '확신 없음' 판정 (1단계 확인 후)
- 맨 아래 '개발용 적대적 문장'으로 data/commands_adv_dev.tsv를 만든다. 열: text, expected_action, expected_floor, type, debatable. expected_action이 NOMOVE이면 WAIT·REJECT·CLARIFY 모두 정답이다.
- experiments/llm/gate.py: gate(text)는 걸린 기준 번호 목록을 돌려준다. nlu.parse 결과와 kiwipiepy 토큰만 쓴다.
  (1) 사건이나 층이 있는 문장에서 1위와 2위 점수 차이 < τ. τ는 dev 78문장만 보고 정한다
  (2) 층이 읽혔거나 누르기·이동 사건이 있는 문장에, 부록 D의 사전(누르기, 이동, 대기, 점수 없는 용언)과 부정·층 취소 규칙의 낱말(말, 않, 마, 빼, 싫) 어디에도 없는 VV·VA 토큰이 있음
  (3) 부정 표지(용언 말·않·마, 부사 안·못, 형용사 없·싫, 아니)가 2개 이상이거나, 부정 표지가 있고 '적' 또는 '취소'가 있음
  (4) 취소되지 않은 층 후보가 2개 이상, 바로 뒤가 '층'·'번'·F가 아닌 숫자(SN), 또는 위·아래·위쪽·아래쪽·위층·아래층·제일·가장·맨·바로·다음·'보다'(조사)·'중'(의존 명사)이 있음
  (5) 규칙이 PRESS인데 과거 어미(었·았·였이 든 EP)가 있음, 누르기·이동 낱말 뒤에 문장 부호가 오고 그 뒤에 명사·용언·부사가 더 있음, 또는 뻔·생각·적·척·농담·장난이 있음
  (6) 영문 토큰(층 표시 F·B 제외)이나 분석 불능 토큰이 있음
- 공식 문장 35개는 하나도 걸리지 않아야 한다(이 문장들의 점수 차이는 1.6 이상이다). 걸리면 기준을 조정한다.
- 기준 (2)~(6)은 개발용 적대적 문장을 보고 만들었다. 이 문장들에서의 포착률은 낙관적인 값이라고 summary에 적는다.
- dev 78문장과 adv_dev 33문장에서 걸린 수, 규칙이 틀린 문장 중 걸린 수, 기준별 걸린 수를 적는다.
- 비교 기준(다른 구현으로 잰 값): 규칙만으로 adv_dev는 정답 14, 위험한 실패 7(누르면 안 되는데 누름 4, 다른 층 2, 되물어야 하는데 누름 1), 안전한 실패 12. 게이트는 규칙이 틀린 19문장을 모두 잡았고 dev에서는 7~11문장이 걸렸다. 크게 다르면 원인을 확인하되 규칙은 고치지 않는다.

3단계: 모델 실행과 비교
- 모델은 게이트와 무관하게 dev 78 + adv_dev 33 = 111문장 전부에 실행하고, 원시 출력을 results/exp_llm/raw_{모델}_{변형}.jsonl에 저장한다. 결합 방식은 저장한 출력으로 비교하고 모델을 다시 돌리지 않는다.
- 설정: temperature 0, 시드 고정, thinking 모드 끔(끄는 방법은 모델 카드에서 확인해 기록), JSON 스키마로 출력 강제, 같은 Llama 객체 재사용. n_ctx와 n_threads 값을 기록한다.
- 출력 스키마:
  {"intent": "press_now|wait|not_command|unclear", "floor_type": "number|highest|lowest|relative|none", "base": 정수, "offset": 정수}
  number면 base가 층이다. relative면 base + offset이다(위는 +, 아래는 −). 쓰지 않는 값은 0이다.
- 프롬프트 변형 2개를 모두 측정한다.
  A: 위 스키마만 (최대 96토큰)
  B: 맨 앞에 "reason"(한 문장) 필드 추가 (최대 192토큰). 출력에서 reason이 실제로 맨 앞에 오는지 확인한다
- 시스템 프롬프트는 한국어로 쓴다. 엘리베이터 안에서 로봇팔에게 하는 말이라는 상황, intent 네 가지의 정의, 예시 8~12개를 넣는다. 예시는 새로 쓰고 평가 파일(dev, adv_dev, holdout, adv_test)의 문장을 그대로 쓰지 않는다. 프롬프트 전문을 experiments/llm/prompts/에 저장한다.
- 모델 답을 행동으로 바꾸기: press_now는 층을 코드로 계산해(highest·lowest는 보이는 층의 최대·최소, relative는 base + offset) ground를 거친다. 층을 못 정하면 CLARIFY. wait는 WAIT, not_command는 REJECT, unclear는 CLARIFY. JSON 오류는 CLARIFY. 시간 제한은 두지 않고 시간만 기록한다.
- 비교할 결합 방식:
  R        규칙만
  M        모델만 (모든 문장)
  A-safe   모든 문장에 G-safe의 결합을 적용 (게이트가 필요한지 확인용)
  G-safe   게이트에 걸린 문장만 모델을 본다. 모델은 누르기를 막을 수만 있다. 규칙 움직이지 않음 + 모델 PRESS → CLARIFY / 규칙 PRESS + 모델 움직이지 않음 → 모델의 분류 / 둘 다 PRESS인데 층이 다름 → CLARIFY / 둘 다 움직이지 않음 → 규칙의 분류
  G-floor  G-safe에 한 가지를 더 허용한다. 규칙이 누르기로 판단한 문장의 층은 모델이 정할 수 있다. (a) 규칙이 PRESS(n)이고 기준 (4)가 걸렸는데 모델의 층이 다름 → 모델의 층 (b) 규칙이 누르기로 판단했지만 층을 하나로 못 정한 CLARIFY(PRESS 점수 0.4 이상, 판정 2·3단계에 안 걸림, 후보 층이 1개가 아님) + 모델 PRESS → 모델의 층. 규칙의 WAIT·REJECT는 모델이 누르기로 바꾸지 못한다
  G-model  게이트에 걸린 문장은 모델 답을 그대로 쓰고 나머지는 규칙
- 완벽한 모델을 가정한 adv_dev 정답 상한은 G-safe 19, G-floor 24, G-model 33이다(다른 구현으로 계산).
- 모델 × 변형 × 결합 방식마다 dev와 adv_dev의 정답, 위험한 실패, 안전한 실패 수를 표로 낸다. adv_dev는 type별 수치와 debatable을 뺀 수치도 낸다. 공식 문장 35개의 결과가 R과 같은지도 적는다.
- 전체 실행은 Metal(n_gpu_layers=-1)로 한다. 상위 2개 조합은 CPU만(n_gpu_layers=0)으로 111문장을 다시 실행해 출력이 Metal과 같은지 보고 문장당 시간을 잰다. 최종 표는 CPU 출력으로 만든다. 같은 설정으로 한 번 더 실행해 출력이 같은지도 확인한다.
- 자원: 문장당 시간 중앙값·최대(첫 호출 제외), 모델 로드 시간, 최대 메모리, 파일 크기.
- 추천 순서: ① dev와 adv_dev의 위험한 실패 0 ② 공식 문장 35개 결과가 R과 같음 ③ dev 정답 78 그대로 ④ adv_dev 정답 수 최대 ⑤ 같으면 더 작고 빠른 모델, 모델에 덜 맡기는 방식(G-safe, G-floor, G-model 순). D는 추천에서 빼고 상한으로만 적는다.
- 여러 조합 중에서 고른 것이므로 adv_dev 수치는 낙관적이라고 summary에 적는다.
- results/exp_llm/summary.md에 정리하고 보고한 뒤 멈춘다.

4단계: 한 번만 하는 최종 확인 (3단계 보고 후 내가 조합을 정하면)
- 내가 고른 조합 1개와 R을 holdout 30문장과 data/commands_adv_test.tsv에 한 번씩 실행해 적는다. adv_test는 내가 넣는다. 없으면 '미실시'로 적는다.
- 결과를 본 뒤 게이트와 프롬프트를 고치지 않는다. adv_test 파일은 이 단계가 끝난 뒤 커밋한다.

보고
- 1단계, 3단계, 4단계가 끝날 때 계획서 9절 형식으로 보고하고 기다려.
- 모르는 값은 추측하지 말고 [대괄호]로 남겨.

개발용 적대적 문장 (text / expected_action / expected_floor / type / debatable)
3층을 누르지 않으면 안 돼 / PRESS / 3 / neg2 / 0
4층은 누르지 말라고 한 적 없어 / PRESS / 4 / neg2 / 0
3층 누르지 말라는 말은 취소할게 / PRESS / 3 / neg2 / 0
절대 5층은 누르면 안 되는 건 아니야 / PRESS / 5 / neg2 / 0
5층 누르지 말고 대기하지도 말고 6층 눌러 / PRESS / 6 / neg2 / 0
3층 누를 뻔했네 / NOMOVE / - / unreal / 0
어제 3층 갔었어 / NOMOVE / - / unreal / 0
3층 눌러, 농담이야 / NOMOVE / - / unreal / 0
3층 누를 생각 없어 / NOMOVE / - / unreal / 0
3층 누르고 싶은데 참을게 / NOMOVE / - / unreal / 0
3층 누르면 죽어 / NOMOVE / - / unreal / 0
6층 눌러 아니 잠깐만 / NOMOVE / - / unreal / 0
누르지 마! 3층! / NOMOVE / - / unreal / 0
2층 바로 위층 눌러줘 / PRESS / 3 / floor / 0
5층보다 한 층 아래 눌러 / PRESS / 4 / floor / 0
제일 높은 층 눌러줘 / PRESS / 6 / floor / 0
맨 아래 버튼 눌러 / PRESS / 1 / floor / 1
3층 4층 5층 중에 4층 / PRESS / 4 / floor / 0
3, 4층 눌러줘 / CLARIFY / - / floor / 0
일곱층 눌러줘 / NOMOVE / - / floor / 0
3층 버튼을 세게 쳐 / PRESS / 3 / vocab / 0
3층 버튼 꾹 눌러 / PRESS / 3 / vocab / 0
4층에서 내릴게 / PRESS / 4 / vocab / 1
3층에 사는 친구 만나러 가 / PRESS / 3 / vocab / 1
3층 누르고 와 / PRESS / 3 / vocab / 0
2층이나 누르든가 / PRESS / 2 / vocab / 0
3층ㄱㄱ / PRESS / 3 / vocab / 0
삼층누르지마 / NOMOVE / - / vocab / 0
press 3 / PRESS / 3 / vocab / 1
방금 3층 누른 거 맞지? / NOMOVE / - / meta / 0
3층 누르는 방법 알려줘 / NOMOVE / - / meta / 0
3층 버튼이 고장 났어 / NOMOVE / - / meta / 0
너 3층 누를 줄 알아? / NOMOVE / - / meta / 0
