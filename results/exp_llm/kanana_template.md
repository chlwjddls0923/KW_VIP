# kanana-2-3b 대화 템플릿 수정 기록 (3단계 재시도, 2026-11-24)

## 왜
- 첫 실행(00:21)에서 로드 실패: `TemplateSyntaxError: Encountered unknown tag 'generation'`.
  GGUF(`mradermacher/kanana-2-3b-instruct-GGUF`, rev 45a8a3e592) 안의 `tokenizer.chat_template`에
  `{%- generation -%}`…`{%- endgeneration -%}`가 있다. 이 태그는 학습할 때 assistant 답의 손실 구간을 표시하는
  transformers 전용 태그이고, 기본 jinja2에는 없다.
- 첫 실패 기록은 `run_kanana2-3b_metal_loadfail.json`에 남겼다.

## 무엇을 했나
- `experiments/llm/extract_template.py`: GGUF 머리말에서 `tokenizer.chat_template`만 읽어
  `experiments/llm/templates/kanana_original.jinja`로 저장(가중치·어휘는 불러오지 않음).
- `kanana_fixed.jinja`: 원본에서 `{%- generation -%}`(123행)와 `{%- endgeneration -%}`(156행) **두 태그 문자열만** 지웠다.
  각 문자열이 원본에 정확히 1번 있음을 확인하고 바꿨다. 그 줄의 들여쓰기 공백 12칸은 남았다.
- diff: `experiments/llm/templates/kanana_fixed.diff`. 바뀐 줄은 `-` 2줄, `+` 2줄(공백만 남은 줄)뿐이고 줄 수는 210행으로 같다.
- sha256: 원본 `b8ee6b31…cae3e3`, 수정본 `66baa0b9…acedbd`.
- `run_model.py`에 `--template 파일`(GGUF 템플릿 대신 파일을 씀, 파일 sha256을 run json에 기록)과
  `--sanity-only`(정상 출력·토큰 확인만 함) 옵션을 더했다. 다른 모델의 기본 동작은 바뀌지 않는다.

## 렌더링 확인: 무엇과 무엇을 비교했나
- 비교 대상
  - (가) **원본 템플릿**을 `run_model.py`의 `GenerationTag` 확장(태그 본문을 그대로 출력, transformers와 같은 방식)으로 렌더링한 문자열
  - (나) **수정 템플릿**을 확장 없이 렌더링한 문자열
  - 두 경우 모두 `run_model.py`와 같은 jinja 설정(ImmutableSandboxedEnvironment, trim_blocks, lstrip_blocks, loopcontrols)과
    같은 인자(enable_thinking=False, bos/eos 자리 표시 문자열, tools=None)를 썼다. 모델은 불러오지 않았다.
- 경우 3개 × add_generation_prompt(True/False) 2개 = 6가지. **6가지 모두 같은 문자열**이었다.
  1. system(실제 `prompts/system_A.txt`) + user 1개
  2. user 1개(system 없음)
  3. system + user + assistant + user + assistant(`<think>` 포함). generation 블록 안쪽이 실제로 실행되는 경우
- 태그 앞뒤가 모두 공백 제거 표시(`{{- … -}}`, `{#- … -#}`, `{%- else`)로 둘러싸여 있어서 남은 공백 줄은 출력에 나오지 않는다.
- 평가에서 쓰는 형태(system + user 1개)는 generation 블록을 지나지 않으므로, 이 수정은 평가 프롬프트 문자열에 영향이 없다.

## thinking
- kanana 템플릿은 `enable_thinking`이 아니라 `thinking_mode`를 쓰고 기본값이 `'no_think'`이다.
  생성 프롬프트 끝에 `<think>\n\n</think>\n\n`가 붙는다. 따로 넘기는 값은 없다(`enable_thinking=False`는 이 템플릿에서 쓰이지 않음).
