"""명령 해석과 층 확인 (계획서 부록 D).

kiwipiepy로 형태소를 나눈 뒤 토큰의 form과 tag만 보고 규칙으로 판단한다(학습 없음).
  parse(text)  → {intent, floor, scores, events, floors, tokens}
  ground(parsed, seen_floors) → {action, floor, reason}
한국어는 마지막 서술어가 주절이라 뒤쪽 사건에 큰 가중치를 준다.
"""
import re
import time

from kiwipiepy import Kiwi

# ---- 사전 (form이 정확히 같은지로 비교) ----
PRESS_WORDS = {"누르", "선택", "찍", "터치", "클릭", "부탁"}
GO_WORDS = {"가", "올라가", "내려가", "이동", "올라오", "내려오"}
WAIT_WORDS = {"대기", "기다리", "멈추", "정지", "가만히", "스톱", "그만", "잠깐", "취소", "중지", "그만두"}
NEUTRAL_VERBS = {"하", "되", "있", "주", "드리", "싶", "보", "좋", "이", "아니", "없", "같"}
DIRECTION_WORDS = {"위", "아래", "위쪽", "아래쪽", "위층", "아래층", "올라가", "내려가", "올라오", "내려오"}
COND_ENDINGS = {"면", "으면"}
HONORIFIC = {"시", "으시"}
PAST = {"었", "았", "였"}
CANCEL_SINGLE = {"아니", "대신", "제외"}
CANCEL_PAIR = {"말", "빼"}           # 뒤에 '고'
NEG_AUX = {"말", "않", "마"}

SINO = {"영": 0, "공": 0, "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9, "십": 10}
ORDINAL = {"첫째": 1, "둘째": 2, "셋째": 3, "넷째": 4, "다섯째": 5, "여섯째": 6}
NATIVE = {"첫": 1, "한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
NUM_WORD_TAGS = {"NR", "MM", "NNG", "NP", "MAG"}

# 사건 점수
SCORE = {"press": ("PRESS", 1.0), "go": ("PRESS", 0.8), "press_neg": ("WAIT", 1.2), "wait": ("WAIT", 1.0),
         "wait_neg": ("PRESS", 0.3), "other_neg": ("WAIT", 1.0), "other": ("OTHER", 1.0)}
EPS = 1e-9

_kiwi = None
INIT_MS = None


def get_kiwi():
    """분석기는 한 번만 만든다. 첫 tokenize에서 모델을 읽으므로 그것까지 초기화 시간에 넣는다."""
    global _kiwi, INIT_MS
    if _kiwi is None:
        t0 = time.perf_counter()
        _kiwi = Kiwi()
        _kiwi.tokenize("초기화")
        INIT_MS = (time.perf_counter() - t0) * 1000
    return _kiwi


# ---- 토큰 보조 함수 ----
def _p2(tok):
    return tok[1][:2]


def _is_V(tok):          # 동사 (VV, VV-R, VV-I ...)
    return _p2(tok) == "VV"


def _is_N(tok):
    return tok[1] in ("NNG", "NNP", "XR")


def _is_M(tok):
    return tok[1] == "MAG"


def _is_main_verb(tok):  # 본용언 VV·VA ('하' 제외)
    return _p2(tok) in ("VV", "VA") and tok[0] != "하"


def _is_particle(tok):
    return tok[1].startswith("J")


def _is_ending(tok):
    return tok[1].startswith("E")


def _is_cond(tok):
    return tok[0] in COND_ENDINGS and tok[1].startswith("E")


def _is_honor(tok):
    return tok[0] in HONORIFIC and tok[1] == "EP"


def _is_past(tok):
    return tok[0] in PAST and tok[1] == "EP"


def _at(toks, i):
    return toks[i] if 0 <= i < len(toks) else ("", "")


def _next_index(toks, i):
    """서술어 i의 '바로 뒤' 위치. 명사 서술어에 붙은 '하'(조사 하나 허용)와 높임은 건너뛴다."""
    j = i + 1
    if _is_N(toks[i]) or toks[i][1] == "NNB":
        if _at(toks, j)[0] == "하":
            j += 1
        elif _is_particle(_at(toks, j)) and _at(toks, j + 1)[0] == "하":
            j += 2
    while _is_honor(_at(toks, j)):
        j += 1
    return j


# ---- 층 읽기 ----
def _sino_value(parts):
    """한자어 수 나열 → 값. '십'이 있으면 십진 표기(십+이=12, 이+십+삼=23), 없으면 마지막 토큰."""
    if "십" not in parts:
        return SINO[parts[-1]]
    total, cur = 0, 0
    for p in parts:
        if p == "십":
            total += (cur or 1) * 10
            cur = 0
        else:
            cur = SINO[p]
    return total + cur


def _read_number(toks, k, ordinal_ok):
    """토큰 k(층 바로 앞, 또는 '번째' 앞)를 수로 읽는다. 반환: (값, 첫 수 토큰 위치) 또는 None."""
    form, tag = toks[k]
    if tag == "SN":
        return int(form), k
    if form in ORDINAL and tag in NUM_WORD_TAGS:
        return ORDINAL[form], k
    if ordinal_ok and form in NATIVE and tag in NUM_WORD_TAGS:
        return NATIVE[form], k
    if form in SINO and tag in NUM_WORD_TAGS:
        start = k
        if tag == "NR":                    # NR이 연달아 나오면 이어 붙인다
            while start - 1 >= 0 and toks[start - 1][1] == "NR" and toks[start - 1][0] in SINO:
                start -= 1
        parts = [toks[x][0] for x in range(start, k + 1)]
        return _sino_value(parts), start
    return None


def _read_floors(toks):
    """층 목록: [{value, idx(층 토큰 위치), used(층 관련 토큰 위치들)}]."""
    floors = []
    for j, (form, tag) in enumerate(toks):
        is_floor_tok = form == "층" or (form.lower() == "f" and tag == "SL")
        compound = (not is_floor_tok) and tag.startswith("NN") and len(form) > 1 and form.endswith("층")
        if compound:
            # '이층'처럼 한 명사: 앞부분을 한자어 수나 서수로 읽는다
            pre = form[:-1]
            if pre in ORDINAL:
                val = ORDINAL[pre]
            elif all(c in SINO for c in pre):
                val = _sino_value(list(pre))
            else:
                continue
            neg = _at(toks, j - 1)[0] == "지하" or (_at(toks, j - 1)[0].lower() == "b" and _at(toks, j - 1)[1] == "SL")
            used = {j} | ({j - 1} if neg else set())
            floors.append({"value": -val if neg else val, "idx": j, "used": used})
            continue
        if not is_floor_tok or j == 0:
            continue
        k = j - 1
        used = {j}
        ordinal_ok = False
        if toks[k][0] == "번째" or (toks[k][0] == "째" and _at(toks, k - 1)[0] == "번"):
            used |= {k} if toks[k][0] == "번째" else {k, k - 1}
            k = k - 1 if toks[k][0] == "번째" else k - 2
            ordinal_ok = True
        if k < 0:
            continue
        r = _read_number(toks, k, ordinal_ok)
        if r is None:
            continue
        val, start = r
        used |= set(range(start, k + 1))
        prev = _at(toks, start - 1)
        if prev[0] == "지하" or (prev[0].lower() == "b" and prev[1] == "SL"):
            val = -val
            used.add(start - 1)
        floors.append({"value": val, "idx": j, "used": used})
    return floors


def _cancel_tokens(toks, floor):
    """층 뒤의 취소 표현. 사이에 '버튼'과 조사 하나 허용. 반환: 취소에 쓰인 토큰 위치(없으면 None)."""
    k = floor["idx"] + 1
    if _at(toks, k)[0] == "버튼":
        k += 1
    if _is_particle(_at(toks, k)):
        k += 1
    form = _at(toks, k)[0]
    if form in CANCEL_PAIR and _at(toks, k + 1)[0] == "고":
        return {k}
    if form in CANCEL_SINGLE:
        return {k}
    return None


# ---- 부정 ----
def _negation(toks, i):
    """토큰 i가 부정되었는지. 반환: (부정 여부, (a)에 쓰인 보조 용언 위치 또는 None)."""
    # (a) 뒤 6토큰 안에 어미 '지' + (조사 하나) + '말'/'않'/'마'
    for k in range(i + 1, min(i + 7, len(toks))):
        if _is_main_verb(toks[k]):
            break
        if toks[k][0] == "지" and _is_ending(toks[k]):
            m = k + 1
            if _is_particle(_at(toks, m)):
                m += 1
            if _at(toks, m)[0] in NEG_AUX and _at(toks, m)[1].startswith("V"):
                return True, m
            break
    # (b) 바로 앞이 부사 '안'/'못' (누르기·이동 낱말이면 '그만'도)
    prev = _at(toks, i - 1)
    if _is_M(prev) and (prev[0] in ("안", "못") or
                        (prev[0] == "그만" and toks[i][0] in PRESS_WORDS | GO_WORDS)):
        return True, None
    # (c) 뒤 4토큰 안에 조건 어미 + '안' + '되'
    for k in range(i + 1, min(i + 5, len(toks))):
        if _is_cond(toks[k]):
            if _at(toks, k + 1)[0] == "안" and _at(toks, k + 2)[0] == "되":
                return True, None
            break
    # (d) 뒤 4토큰 안에 '싫', 또는 '필요' + (조사 하나) + '없'
    for k in range(i + 1, min(i + 5, len(toks))):
        if toks[k][0] == "싫" and _p2(toks[k]) == "VA":
            return True, None
        if toks[k][0] == "필요":
            m = k + 1
            if _is_particle(_at(toks, m)):
                m += 1
            if _at(toks, m)[0] == "없":
                return True, None
        if _is_main_verb(toks[k]):
            break
    return False, None


# ---- 해석 ----
def tokenize(text):
    return [(t.form, t.tag) for t in get_kiwi().tokenize(text)]


def parse(text):
    toks = tokenize(text)
    floors = _read_floors(toks)

    # 사건이 아닌 토큰: 층 토큰, 층 취소 낱말, (a)의 보조 용언
    skip = set()
    for f in floors:
        skip |= f["used"]
        c = _cancel_tokens(toks, f)
        f["cancelled"] = c is not None
        if c:
            skip |= c
    neg = {}
    for i in range(len(toks)):
        is_neg, aux = _negation(toks, i)
        neg[i] = is_neg
        if aux is not None:
            skip.add(aux)

    # 사건 만들기: 표에서 처음 맞는 줄
    events = []
    for i, tok in enumerate(toks):
        if i in skip:
            continue
        form = tok[0]
        V, N, M = _is_V(tok), _is_N(tok), _is_M(tok)
        kind = None
        if form in PRESS_WORDS and (V or N):
            kind = "press"
        elif form in GO_WORDS and (V or N):
            kind = "go"
        elif form in WAIT_WORDS and (V or N or M):
            kind = "wait"
        elif form == "금지" and N:
            kind = "press_neg"
        elif form == "되" and V and _is_past(_at(toks, _next_index(toks, i))):
            kind = "wait"                         # '됐어'는 사양
        elif V and form not in NEUTRAL_VERBS:
            kind = "other"
        elif form == "하" and V and neg[i]:
            kind = "other_neg"
        if kind:
            events.append({"i": i, "form": form, "kind": kind, "neg": neg[i]})

    for e in events:
        i = e["i"]
        nxt = _next_index(toks, i)
        # 1) 과거형 press·go는 명령이 아니다
        if e["kind"] in ("press", "go") and _is_past(_at(toks, nxt)):
            e["kind"] = "other"
            continue
        # 2) 부정
        if e["neg"]:
            e["kind"] = {"press": "press_neg", "go": "press_neg", "wait": "wait_neg",
                         "other": "other_neg"}.get(e["kind"], e["kind"])
            continue
        # 3) 조건형 press·go ('누르면 어떻게 돼?') → other. 뒤 3토큰 안에 '좋'이면 그대로
        if e["kind"] in ("press", "go"):
            c = None
            if _is_cond(_at(toks, nxt)):
                c = nxt
            elif _is_ending(_at(toks, nxt)) and _at(toks, nxt + 1)[0] == "주":
                k = nxt + 2
                while _is_honor(_at(toks, k)):
                    k += 1
                if _is_cond(_at(toks, k)):
                    c = k
            if c is not None and not any(_at(toks, x)[0] == "좋" for x in range(c + 1, c + 4)):
                e["kind"] = "other"

    # 4) 조건이 붙은 명령: 마지막 조건절 끝보다 뒤의 press·go → other
    last_end = -1
    for c, tok in enumerate(toks):
        if not _is_cond(tok):
            continue
        p = c - 1
        while _is_honor(_at(toks, p)):
            p -= 1
        pt = _at(toks, p)
        if _p2(pt) in ("VV", "VA") and pt[0] not in PRESS_WORDS | GO_WORDS and pt[0] != "주":
            last_end = c
        elif pt[0] == "하" and pt[1].startswith("XS") and _is_N(_at(toks, p - 1)) \
                and _at(toks, p - 1)[0] not in PRESS_WORDS | GO_WORDS:
            last_end = c
    if last_end >= 0:
        for e in events:
            if e["kind"] in ("press", "go") and e["i"] > last_end:
                e["kind"] = "other"

    # 점수: 순서 가중치 w = 1 + i/(m-1), m = 1이면 2.0
    scores = {"PRESS": 0.0, "WAIT": 0.0, "OTHER": 0.0}
    m = len(events)
    any_floor = bool(floors)
    for idx, e in enumerate(events):
        w = 2.0 if m == 1 else 1.0 + idx / (m - 1)
        e["w"] = w
        if e["kind"] == "go" and not any_floor:
            continue
        key, s = SCORE[e["kind"]]
        scores[key] += s * w

    # 층만 있는 문장: 사건 없음, 용언 없음(취소·부정에 쓰인 것 제외), 층 있음
    has_pred = any(_p2(t) in ("VV", "VA", "VX") for i, t in enumerate(toks) if i not in skip)
    if not events and not has_pred and any_floor:
        scores["PRESS"] += 1.0

    # 층 후보: 취소되지 않았고, 그 층 뒤 첫 사건이 press_neg·other_neg가 아닌 층
    cands = []
    for f in floors:
        if f["cancelled"]:
            continue
        after = [e for e in events if e["i"] > f["idx"]]
        if after and after[0]["kind"] in ("press_neg", "other_neg"):
            continue
        if f["value"] not in cands:
            cands.append(f["value"])

    # 판정
    P, W, O = scores["PRESS"], scores["WAIT"], scores["OTHER"]
    floor = None
    if max(P, W, O) < 0.4 - EPS:
        intent = "CLARIFY" if any(t[0] in DIRECTION_WORDS for t in toks) else "REJECT"
    elif W >= P - 0.3 - EPS and W >= O - EPS:
        intent = "CLARIFY" if P > W + EPS else "WAIT"
    elif O > P + EPS:
        intent = "REJECT"
    elif len(cands) == 1:
        intent, floor = "PRESS", cands[0]
    else:
        intent = "CLARIFY"
    return {"intent": intent, "floor": floor, "scores": scores,
            "events": [(e["form"], e["kind"], round(e["w"], 3)) for e in events],
            "floors": [(f["value"], f["cancelled"]) for f in floors], "candidates": cands, "tokens": toks}


def ground(parsed, seen_floors):
    """최종 행동. PRESS(n)의 n이 보이는 층 목록에 없으면 REJECT."""
    intent, floor = parsed["intent"], parsed.get("floor")
    if intent == "PRESS":
        if floor in set(seen_floors):
            return {"action": "PRESS", "floor": floor, "reason": "ok"}
        return {"action": "REJECT", "floor": floor, "reason": "not_visible"}
    reason = {"WAIT": "wait", "CLARIFY": "clarify", "REJECT": "unsupported"}[intent]
    return {"action": intent, "floor": None, "reason": reason}


_DIGITS = re.compile(r"(\d+)\s*층")


def digits_only(text):
    """비교용 기준선: '(\\d+)\\s*층'의 첫 일치가 있으면 PRESS(그 수), 없으면 REJECT."""
    m = _DIGITS.search(text)
    if m:
        return {"intent": "PRESS", "floor": int(m.group(1))}
    return {"intent": "REJECT", "floor": None}
