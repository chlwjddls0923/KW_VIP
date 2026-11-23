"""버튼 검출, 3D 위치, 숫자 판독 (계획서 부록 B).

입력은 Frame(RGB, 깊이, fovy, 해상도, 카메라 자세)과 후보 숫자뿐이다. 시뮬레이터 정답은 쓰지 않는다.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

from .scene import render_digit

# 1) 파란 버튼 HSV 범위
BLUE_H = (0.52, 0.68)
BLUE_S = 0.40
BLUE_V = 0.15
LABEL_S = 0.30            # 라벨 픽셀: 파랗지 않고 채도 < 0.30
MIN_BLUE_PX = 60          # 팽창 후 성분 최소 크기
MIN_LABEL_PX = 25
PLANE_OUTLIER = 0.004     # 법선 방향 중앙값에서 4 mm 넘게 벗어나면 버림
PATCH = 32
PATCH_SPAN = 0.82         # 중심 ± 0.82 × 반폭
ACCEPT_SCORE = 0.5
ACCEPT_MARGIN = 0.03
UP = np.array([0.0, 0.0, 1.0])


def rgb_to_hsv(rgb):
    """uint8 RGB → H, S, V (모두 0~1)."""
    x = rgb.astype(np.float64) / 255.0
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    v = x.max(axis=-1)
    mn = x.min(axis=-1)
    c = v - mn
    s = np.where(v > 0, c / np.where(v > 0, v, 1), 0.0)
    safe = np.where(c > 0, c, 1)
    h = np.zeros_like(v)
    h = np.where(v == r, ((g - b) / safe) % 6, h)
    h = np.where(v == g, (b - r) / safe + 2, h)
    h = np.where(v == b, (r - g) / safe + 4, h)
    h = np.where(c > 0, h / 6.0, 0.0)
    return h, s, v


def make_template(img):
    """숫자 그림 → 회색, 가운데 82%를 잘라 32x32로 줄인다(쌍선형)."""
    gray = Image.fromarray(np.asarray(img, dtype=np.float64).mean(axis=-1).astype(np.float32), mode="F")
    w, h = gray.size
    mx, my = w * (1 - PATCH_SPAN) / 2, h * (1 - PATCH_SPAN) / 2
    small = gray.resize((PATCH, PATCH), Image.BILINEAR, box=(mx, my, w - mx, h - my))
    return np.asarray(small, dtype=np.float64)


def make_templates(floors):
    """후보는 장면에 쓴 숫자의 템플릿이다."""
    return {int(n): make_template(render_digit(n)) for n in floors}


def zncc_shift(patch, tmpl):
    """가로·세로 ±1 px 이동 9가지에서 겹치는 영역만으로 ZNCC를 계산해 최댓값을 돌려준다."""
    best = -np.inf
    n = patch.shape[0]
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            a = patch[max(0, dy):n + min(0, dy), max(0, dx):n + min(0, dx)]
            b = tmpl[max(0, -dy):n + min(0, -dy), max(0, -dx):n + min(0, -dx)]
            sa, sb = a.std(), b.std()
            if sa < 1e-9 or sb < 1e-9:
                continue
            best = max(best, float(np.mean((a - a.mean()) / sa * (b - b.mean()) / sb)))
    return best


def plane_axes(normal):
    """e2 = 위쪽을 평면에 투영, e1 = e2 × n (패널을 마주 볼 때 오른쪽)."""
    e2 = UP - (UP @ normal) * normal
    e2 /= np.linalg.norm(e2)
    e1 = np.cross(e2, normal)
    return e1, e2


def sample_patch(frame, gray, center, normal, half):
    """중심 ± 0.82 × 반폭을 32x32 격자로 잡아 회색 영상을 쌍선형으로 뽑는다. 첫 행 = 위(+e2), 첫 열 = 왼쪽(−e1)."""
    e1, e2 = plane_axes(normal)
    s = np.linspace(-PATCH_SPAN * half, PATCH_SPAN * half, PATCH)
    cols = s[None, :, None] * e1                       # 왼쪽(−) → 오른쪽(+)
    rows = s[::-1][:, None, None] * e2                 # 위(+) → 아래(−)
    pts = center + rows + cols                         # (32, 32, 3)
    u, v = frame.project(pts)
    return ndimage.map_coordinates(gray, [v, u], order=1, mode="nearest")


def detect(frame, templates, debug=None):
    """받아들인 버튼마다 {floor, score, margin, center, normal}. debug에 dict를 주면 중간 결과를 담는다."""
    h, s, v = rgb_to_hsv(frame.rgb)
    gray = frame.rgb.astype(np.float64).mean(axis=-1)
    blue = (h > BLUE_H[0]) & (h < BLUE_H[1]) & (s > BLUE_S) & (v > BLUE_V)

    # 2) 팽창 후 연결 성분
    grown = ndimage.binary_dilation(blue, iterations=2)
    comp, ncomp = ndimage.label(grown)
    sizes = ndimage.sum_labels(np.ones_like(comp), comp, index=np.arange(1, ncomp + 1))

    # 3) 성분 안의 라벨 픽셀
    labels = []
    for k in range(1, ncomp + 1):
        if sizes[k - 1] < MIN_BLUE_PX:
            continue
        sl = ndimage.find_objects((comp == k).astype(np.int32))[0]
        region = ndimage.binary_fill_holes(comp[sl] == k)
        inner = ndimage.binary_erosion(region, iterations=2)
        cand = inner & ~blue[sl] & (s[sl] < LABEL_S)
        lab, nlab = ndimage.label(cand)
        if nlab == 0:
            continue
        lsz = ndimage.sum_labels(np.ones_like(lab), lab, index=np.arange(1, nlab + 1))
        big = int(np.argmax(lsz)) + 1
        if lsz[big - 1] < MIN_LABEL_PX:
            continue
        vv, uu = np.nonzero(lab == big)
        vv = vv + sl[0].start
        uu = uu + sl[1].start
        labels.append({"comp": k, "u": uu, "v": vv})
    if debug is not None:
        debug.update(blue=blue, comp=comp, labels=labels, results=[])
    if not labels:
        return []

    # 4) 라벨 픽셀을 역투영하고 모든 라벨 점으로 평면을 맞춘다(SVD)
    for lb in labels:
        lb["pts"] = frame.backproject(lb["u"], lb["v"], frame.depth[lb["v"], lb["u"]])
    allp = np.concatenate([lb["pts"] for lb in labels])
    mean = allp.mean(axis=0)
    normal = np.linalg.svd(allp - mean, full_matrices=False)[2][-1]
    if normal @ (frame.cam_xpos - mean) < 0:            # 카메라 쪽을 향하게
        normal = -normal
    e1, e2 = plane_axes(normal)

    results = []
    for lb in labels:
        p = lb["pts"]
        # 6) 법선 방향 이상점 제거 → e1·e2 방향 2~98 백분위로 중심과 반폭
        dn = p @ normal
        keep = np.abs(dn - np.median(dn)) <= PLANE_OUTLIER
        p = p[keep]
        if len(p) < 3:
            continue
        a, b = p @ e1, p @ e2
        a_lo, a_hi = np.percentile(a, [2, 98])
        b_lo, b_hi = np.percentile(b, [2, 98])
        half = ((a_hi - a_lo) + (b_hi - b_lo)) / 2 / 2
        center = e1 * (a_lo + a_hi) / 2 + e2 * (b_lo + b_hi) / 2 + normal * np.median(p @ normal)
        # 7~10) 정면화 패치 → 템플릿 ZNCC → 받아들이기
        patch = sample_patch(frame, gray, center, normal, half)
        scores = sorted(((zncc_shift(patch, t), n) for n, t in templates.items()), reverse=True)
        best, floor = scores[0]
        margin = best - scores[1][0] if len(scores) > 1 else best
        accepted = best >= ACCEPT_SCORE and margin >= ACCEPT_MARGIN
        if debug is not None:
            debug["results"].append({"u": lb["u"], "v": lb["v"], "floor": floor, "score": best, "margin": margin,
                                     "accepted": accepted, "patch": patch, "center": center, "half": half})
        if accepted:
            results.append({"floor": int(floor), "score": float(best), "margin": float(margin),
                            "center": center, "normal": normal.copy()})

    # 같은 층이 두 번 읽히면 점수가 높은 것만 남긴다
    by_floor = {}
    for r in results:
        if r["floor"] not in by_floor or r["score"] > by_floor[r["floor"]]["score"]:
            by_floor[r["floor"]] = r
    return [by_floor[n] for n in sorted(by_floor)]


def save_debug(frame, debug, path):
    """검출 영역, 읽은 숫자, 정면화 패치를 한 장에 그린다."""
    from PIL import ImageDraw

    img = Image.fromarray(frame.rgb.copy())
    draw = ImageDraw.Draw(img)
    for r in debug.get("results", []):
        color = (0, 255, 0) if r["accepted"] else (255, 60, 60)
        x0, x1, y0, y1 = r["u"].min(), r["u"].max(), r["v"].min(), r["v"].max()
        draw.rectangle([x0 - 6, y0 - 6, x1 + 6, y1 + 6], outline=color, width=2)
        draw.text((x1 + 10, y0 - 6), f"{r['floor']} {r['score']:.2f}/{r['margin']:.2f}", fill=color)
    # 오른쪽 위에 정면화 패치를 4배로 늘려 나란히 붙인다
    for i, r in enumerate(debug.get("results", [])):
        p = r["patch"]
        p = (255 * (p - p.min()) / max(np.ptp(p), 1e-9)).astype(np.uint8)
        tile = Image.fromarray(p).resize((PATCH * 4, PATCH * 4), Image.NEAREST).convert("RGB")
        x = img.width - (i + 1) * (PATCH * 4 + 8)
        img.paste(tile, (x, 8))
        draw.text((x, PATCH * 4 + 12), f"{r['floor']}", fill=(255, 255, 0))
    img.save(path)
