"""'확신 없음' 판정(게이트). gate(text) → 걸린 기준 번호 목록.

nlu.parse 결과와 kiwipiepy 토큰(form, tag)만 쓴다. 규칙(nlu.py)은 import만 한다.
기준 (1)의 τ는 dev 78문장만 보고 정했다(results/exp_llm/gate_summary.md).
기준 (2)~(6)은 개발용 적대적 문장(adv_dev)을 보고 만들었다.
"""
from common import nlu

TAU = 0.5    # 기준 (1): 1위와 2위 점수 차이 < TAU. dev만 보고 정함: dev 점수 차이는 {0, 1.0, 1.6, 2.0, ...}로 띄엄띄엄하고, 동점(0)만 거르도록 0과 1.0의 가운데를 씀

DICT_ALL = nlu.PRESS_WORDS | nlu.GO_WORDS | nlu.WAIT_WORDS | nlu.NEUTRAL_VERBS
NEG_CANCEL_WORDS = {"말", "않", "마", "빼", "싫"}
REL_WORDS = {"위", "아래", "위쪽", "아래쪽", "위층", "아래층", "제일", "가장", "맨", "바로", "다음"}
UNREAL_WORDS = {"뻔", "생각", "적", "척", "농담", "장난"}
PUNCT_TAGS = {"SF", "SP", "SS", "SE", "SO"}


def _neg_markers(toks):
    """부정 표지 개수: 용언 말·않·마, 부사 안·못, 형용사 없·싫, 아니."""
    n = 0
    for form, tag in toks:
        if form in ("말", "않", "마") and tag.startswith("V"):
            n += 1
        elif form in ("안", "못") and tag == "MAG":
            n += 1
        elif form in ("없", "싫") and tag[:2] == "VA":
            n += 1
        elif form == "아니":
            n += 1
    return n


def gate(text, parsed=None, tau=TAU):
    p = parsed or nlu.parse(text)
    toks = p["tokens"]
    forms = [t[0] for t in toks]
    events = p["events"]                       # (form, kind, w)
    has_floor = bool(p["floors"])
    press_go_event = any(e[0] in nlu.PRESS_WORDS | nlu.GO_WORDS for e in events)
    hit = []

    # (1) 사건이나 층이 있는 문장에서 1위와 2위 점수 차이 < τ
    if events or has_floor:
        s = sorted(p["scores"].values(), reverse=True)
        if s[0] - s[1] < tau - 1e-9:
            hit.append(1)

    # (2) 층이 읽혔거나 누르기·이동 사건이 있는 문장에, 사전·부정/취소 낱말에 없는 VV·VA
    if has_floor or press_go_event:
        if any(t[1][:2] in ("VV", "VA") and t[0] not in DICT_ALL | NEG_CANCEL_WORDS for t in toks):
            hit.append(2)

    # (3) 부정 표지 2개 이상, 또는 부정 표지 + '적'/'취소'
    nneg = _neg_markers(toks)
    if nneg >= 2 or (nneg >= 1 and ("적" in forms or "취소" in forms)):
        hit.append(3)

    # (4) 취소되지 않은 층 2개 이상 / 바로 뒤가 층·번·F가 아닌 SN / 상대·최상 표현
    uncancelled = [v for v, c in p["floors"] if not c]
    bare_sn = False
    for i, (form, tag) in enumerate(toks):
        if tag == "SN":
            nxt = toks[i + 1] if i + 1 < len(toks) else ("", "")
            if not (nxt[0] in ("층", "번") or nxt[0].lower() == "f"):
                bare_sn = True
    rel = any(f in REL_WORDS for f in forms) or any(t == ("보다", "JKB") for t in toks) \
        or any(t == ("중", "NNB") for t in toks)
    if len(uncancelled) >= 2 or bare_sn or rel:
        hit.append(4)

    # (5) 규칙 PRESS + 과거 EP / 누르기·이동 낱말 뒤 문장 부호 뒤에 내용어 / 뻔·생각·적·척·농담·장난
    c5 = False
    if p["intent"] == "PRESS" and any(t[1] == "EP" and any(x in t[0] for x in ("었", "았", "였")) for t in toks):
        c5 = True
    pg = [i for i, t in enumerate(toks) if t[0] in nlu.PRESS_WORDS | nlu.GO_WORDS and t[1][:1] in ("V", "N")]
    if pg:
        for s_i in range(pg[0] + 1, len(toks)):
            if toks[s_i][1] in PUNCT_TAGS and any(t[1][:1] in ("N", "V") or t[1][:2] == "MA" for t in toks[s_i + 1:]):
                c5 = True
                break
    if any(f in UNREAL_WORDS for f in forms):
        c5 = True
    if c5:
        hit.append(5)

    # (6) 영문 토큰(층 표시 F·B 제외)이나 분석 불능 토큰
    if any((t[1] == "SL" and t[0].lower() not in ("f", "b")) or t[1] == "UN" for t in toks):
        hit.append(6)
    return hit
