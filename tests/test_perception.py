"""단계 3 통과 기준: 인식. 정답(truth)은 채점에만 쓴다."""
import numpy as np
import pytest

from assist.camera import capture
from assist.paths import OUT
from assist.perception import detect, make_templates, sample_patch, save_debug, zncc_shift
from assist.scene import Scene, layout_from_perm, layout_string

SEEDS = range(7001, 7041)
MATCH_DIST = 0.02
HIGH_Z = 0.90


def _variation(seed):
    """변화 범위 + 조명 + 숫자 배치 섞기 (부록 E 변화 조건의 추출 순서, 층·문장 제외)."""
    rng = np.random.default_rng(seed)
    dpos = (rng.uniform(-0.10, 0.10), rng.uniform(-0.05, 0.05), rng.uniform(-0.10, 0.10))
    yaw = rng.uniform(-10.0, 10.0)
    light = rng.uniform(0.6, 1.2)
    perm = rng.permutation(6)
    return dpos, yaw, light, layout_from_perm(perm)


@pytest.fixture(scope="module")
def runs():
    """시드 40개를 한 번씩 촬영·인식해 결과를 모은다."""
    out = []
    for seed in SEEDS:
        dpos, yaw, light, layout = _variation(seed)
        sc = Scene(layout=layout)
        sc.reset(dpos, yaw, light)
        frame = capture(sc.renderer, sc.model, sc.data)
        res = detect(frame, make_templates(sc.floors))
        out.append({"seed": seed, "truth": sc.truth(), "res": res, "layout": layout_string(layout),
                    "light": light, "yaw": yaw, "dpos": dpos})
        sc.close()
    return out


def test_perception_variation(runs):
    n_high = det_high = n_low = det_low = 0
    misreads, errs, nerrs, missed = [], [], [], []
    for r in runs:
        truth, res = r["truth"], r["res"]
        for n, t in truth.items():
            hit = [x for x in res if x["floor"] == n and np.linalg.norm(x["center"] - t["center"]) <= MATCH_DIST]
            high = t["center"][2] >= HIGH_Z
            if high:
                n_high += 1
                det_high += bool(hit)
                if not hit:
                    missed.append((r["seed"], n, round(float(t["center"][2]), 3)))
            else:
                n_low += 1
                det_low += bool(hit)
            if hit:
                errs.append(np.linalg.norm(hit[0]["center"] - t["center"]))
        for x in res:
            nearest = min(truth, key=lambda k: np.linalg.norm(truth[k]["center"] - x["center"]))
            if nearest != x["floor"]:
                misreads.append((r["seed"], x["floor"], nearest))
            nerrs.append(np.degrees(np.arccos(np.clip(x["normal"] @ truth[nearest]["normal"], -1, 1))))
    errs = np.array(errs) * 1000
    n_acc = sum(len(r["res"]) for r in runs)
    print(f"\nhigh (z>={HIGH_Z}) detection {det_high}/{n_high} = {det_high / n_high:.1%}; "
          f"low detection {det_low}/{n_low}; accepted {n_acc}, misread {len(misreads)}")
    print(f"center err median {np.median(errs):.2f} mm, max {errs.max():.2f} mm; normal err max {max(nerrs):.3f} deg")
    print(f"missed high: {missed}")
    assert det_high / n_high >= 0.98
    assert not misreads, misreads
    assert np.median(errs) <= 2.0
    assert errs.max() <= 5.0
    assert max(nerrs) <= 1.0


def test_label_orientation_and_debug():
    """기준 위치에서 truth의 중심·법선으로 편 패치가 원래 템플릿과 ≥ 0.7이고 뒤집은 템플릿보다 높다."""
    sc = Scene()
    sc.reset()
    frame = capture(sc.renderer, sc.model, sc.data)
    gray = frame.rgb.astype(np.float64).mean(axis=-1)
    templates = make_templates(sc.floors)
    half = 0.58 * sc.radius
    rows = []
    for n, t in sc.truth().items():
        patch = sample_patch(frame, gray, t["center"], t["normal"], half)
        tm = templates[n]
        s = {"orig": zncc_shift(patch, tm), "lr": zncc_shift(patch, tm[:, ::-1]),
             "ud": zncc_shift(patch, tm[::-1, :]), "rot180": zncc_shift(patch, tm[::-1, ::-1])}
        rows.append((n, s))
    for n, s in rows:
        print(f"floor {n}: " + ", ".join(f"{k} {v:.3f}" for k, v in s.items()))
    # 사람이 볼 디버그 그림
    dbg = {}
    detect(frame, templates, dbg)
    OUT.mkdir(exist_ok=True)
    save_debug(frame, dbg, OUT / "perception_debug.png")
    sc.close()
    for n, s in rows:
        assert s["orig"] >= 0.7, (n, s)
        assert s["orig"] > max(s["lr"], s["ud"], s["rot180"]), (n, s)
