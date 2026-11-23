"""SV024 실패 원인 재확인 (확인만, 본 코드·문서는 고치지 않는다).

  .venv/bin/python experiments/diag/sv024.py [시드]    (기본 4024 = SV024. 예: 4060 = SV060, 4094 = SV094)

- 추가 시험 SV024와 같은 조건(시드 4024)으로 장면을 만들고 reset 직후 head_rgb RGB·깊이를 찍는다(파이프라인과 같은 시점).
- 6개 버튼 라벨 중심(truth, 채점용 정답)을 화면에 투영하고, 화면 안인지·가림인지 확인한다.
  가림: 그 픽셀의 깊이(광축 거리)가 라벨까지의 광축 거리보다 짧으면 가림. 가린 geom은 카메라에서 라벨 중심으로 쏜 mj_ray로 찾는다.
- 인식은 src/assist/perception.detect를 그대로 부르고(debug), 4층·5층이 어느 단계에서 빠졌는지 같은 상수로 따져 본다.
출력: results/diag/SV{번호}_rgb.png, _depth.png, _zoom.png, _zoom_raw.png, SV{번호}.json, SV024_supp_low.csv(공통)
집중해서 보는 층은 검출되지 않은 층이다(없으면 목표 층).
"""
import csv
import json
import sys
import tempfile
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from assist import perception as P  # noqa: E402
from assist.camera import capture  # noqa: E402
from assist.perception import detect, make_templates, rgb_to_hsv  # noqa: E402
from assist.protocol import variation_trial  # noqa: E402
from assist.scene import BUTTON_Y, Scene  # noqa: E402

OUT = ROOT / "results" / "diag"
OCC_TOL = 0.002           # 깊이 비교 여유 2 mm
PAD = 260                 # 화면 밖 투영점을 그리려고 영상 둘레에 둔 여백(px)


def geom_label(m, gid):
    if gid < 0:
        return "없음"
    g = m.geom(gid)
    return f"{g.name or '(이름 없음)'} [body {m.body(m.geom_bodyid[gid]).name}]"


def point_status(m, d, frame, p, own_geoms):
    """점 p(월드)의 투영 좌표, 화면 안 여부, 깊이 가림, mj_ray 첫 충돌 geom."""
    w, h = frame.size
    u, v = (float(x) for x in frame.project(p))
    q = (p - frame.cam_xpos) @ frame.cam_xmat
    zc = float(-q[2])                                       # 라벨까지 광축 거리
    inside = 0 <= u <= w - 1 and 0 <= v <= h - 1
    depth = float(frame.depth[int(round(v)), int(round(u))]) if inside else None
    occluded = (depth < zc - OCC_TOL) if inside else None
    vec = p - frame.cam_xpos
    dist = float(np.linalg.norm(vec))
    gid = np.array([-1], dtype=np.int32)
    hit = mujoco.mj_ray(m, d, frame.cam_xpos, vec / dist, None, 1, -1, gid)
    hit_g = int(gid[0])
    ray_block = hit_g >= 0 and hit_g not in own_geoms and hit < dist - OCC_TOL
    return {"u": round(u, 1), "v": round(v, 1), "in_frame": inside, "label_axis_dist_m": round(zc, 4),
            "depth_at_pixel_m": None if depth is None else round(depth, 4), "occluded_by_depth": occluded,
            "ray_first_geom": geom_label(m, hit_g), "ray_hit_m": round(float(hit), 4), "ray_to_label_m": round(dist, 4),
            "ray_blocked": bool(ray_block)}


def face_samples(scene, n, kind):
    """라벨 앞면(정사각형) 또는 버튼 앞면 고리(파란 부분)의 점들(월드)."""
    m, d = scene.model, scene.data
    pid = scene.panel_id
    p0, r = d.xpos[pid], d.xmat[pid].reshape(3, 3)
    x, z = scene.layout[n]
    rad = scene.radius
    pts = []
    if kind == "label":
        s = np.linspace(-0.58 * rad, 0.58 * rad, 9)
        for a in s:
            for b in s:
                pts.append(p0 + r @ np.array([x + a, BUTTON_Y + 0.016, z + b]))
    else:                                                   # 파란 고리: 라벨 밖, 반지름 안
        for ang in np.linspace(0, 2 * np.pi, 48, endpoint=False):
            for rr in (0.75 * rad, 0.95 * rad):
                pts.append(p0 + r @ np.array([x + rr * np.cos(ang), BUTTON_Y + 0.015, z + rr * np.sin(ang)]))
    return np.array(pts)


def coverage(m, d, frame, pts, own):
    st = [point_status(m, d, frame, p, own) for p in pts]
    n = len(st)
    inside = [s for s in st if s["in_frame"]]
    occ = [s for s in inside if s["occluded_by_depth"]]
    geoms = sorted({s["ray_first_geom"] for s in st if s["ray_blocked"]})
    return {"n_points": n, "in_frame": len(inside), "out_of_frame": n - len(inside),
            "in_frame_but_occluded": len(occ), "visible": len(inside) - len(occ), "blocking_geoms(ray)": geoms,
            "v_range": [round(min(s["v"] for s in st), 1), round(max(s["v"] for s in st), 1)]}


def stage_check(frame, debug, ring_px):
    """인식 단계별로 따라가 본다: 파란 영역 → 성분 크기(≥60) → 라벨 픽셀(≥25) → 판독 점수."""
    h, s, v = rgb_to_hsv(frame.rgb)
    blue, comp = debug["blue"], debug["comp"]
    H, W = blue.shape
    ring_in = [(int(round(vv)), int(round(uu))) for uu, vv in ring_px if 0 <= uu <= W - 1 and 0 <= vv <= H - 1]
    out = {"ring_points_in_frame": len(ring_in),
           "ring_points_blue": int(sum(blue[a, b] for a, b in ring_in))}
    ks = sorted({int(comp[a, b]) for a, b in ring_in if comp[a, b] > 0})
    out["components"] = []
    for k in ks:
        mask = comp == k
        size = int(mask.sum())
        sl = ndimage.find_objects(mask.astype(np.int32))[0]
        region = ndimage.binary_fill_holes(comp[sl] == k)
        inner = ndimage.binary_erosion(region, iterations=2)
        cand = inner & ~blue[sl] & (s[sl] < P.LABEL_S)
        lab, nlab = ndimage.label(cand)
        biggest = int(ndimage.sum_labels(np.ones_like(lab), lab, index=np.arange(1, nlab + 1)).max()) if nlab else 0
        ys, xs = np.nonzero(mask)
        c = {"comp": k, "size_px_after_dilation": size, "pass_min_blue_px(60)": size >= P.MIN_BLUE_PX,
             "holes_filled_px": int(region.sum() - (comp[sl] == k).sum()),     # 0이면 고리가 닫히지 않아 라벨 구멍이 안 채워짐
             "bbox_uv": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
             "touches_bottom_edge": bool(ys.max() >= H - 1), "touches_side_edge": bool(xs.min() <= 0 or xs.max() >= W - 1),
             "label_blob_px": biggest, "pass_min_label_px(25)": biggest >= P.MIN_LABEL_PX}
        lb = [x for x in debug["labels"] if x["comp"] == k]
        if lb:
            r = [x for x in debug["results"] if np.array_equal(x["u"], lb[0]["u"]) and np.array_equal(x["v"], lb[0]["v"])]
            if r:
                c.update(read_floor=int(r[0]["floor"]), score=round(float(r[0]["score"]), 3),
                         margin=round(float(r[0]["margin"]), 3), accepted=bool(r[0]["accepted"]))
            else:
                c["read"] = "판독 전에 빠짐(평면 이상점 제거 뒤 점 < 3)"
        out["components"].append(c)
    if not ring_in:
        out["dropped_at"] = "화면 밖(파란 고리가 화면에 없음)"
    elif not ks or out["ring_points_blue"] == 0:
        out["dropped_at"] = "파란 영역(화면 안 고리 점에 파란 픽셀 없음)"
    else:
        c = max(out["components"], key=lambda c: c["size_px_after_dilation"])
        if not c["pass_min_blue_px(60)"]:
            out["dropped_at"] = "파란 영역(성분 < 60 px)"
        elif not c["pass_min_label_px(25)"]:
            out["dropped_at"] = "라벨 픽셀(가장 큰 라벨 덩어리 < 25 px)"
        elif "accepted" in c and not c["accepted"]:
            out["dropped_at"] = f"판독 점수(점수 {c['score']}, 여유 {c['margin']}, 기준 0.5 / 0.03)"
        elif c.get("accepted"):
            out["dropped_at"] = f"빠지지 않음(받아들임, 읽은 층 {c['read_floor']})"
        else:
            out["dropped_at"] = c.get("read", "[불명]")
    return out


def draw(frame, img, truth, status, debug, path, zoom=None, inset=None):
    W, H = frame.size
    canvas = Image.new("RGB", (W + 2 * PAD, H + 2 * PAD), (40, 40, 40))
    canvas.paste(img, (PAD, PAD))
    dr = ImageDraw.Draw(canvas)
    dr.rectangle([PAD - 1, PAD - 1, PAD + W, PAD + H], outline=(255, 255, 0), width=3)       # 화면 경계
    dr.text((PAD, PAD + H + 8), "yellow = image border (head_rgb 1280x960)", fill=(255, 255, 0))
    if inset:                                                                              # 녹화 영상의 확대 화면 범위
        x0, y0, x1, y1 = inset["crop_uv"]
        dr.rectangle([PAD + x0, PAD + y0, PAD + x1, PAD + y1], outline=(255, 255, 255), width=1)
        dr.text((PAD, PAD + H + 24), "white = zoom inset area used in the recorded video (record.py)", fill=(255, 255, 255))
    for r in debug["results"]:
        col = (0, 255, 0) if r["accepted"] else (255, 60, 60)
        dr.rectangle([PAD + r["u"].min() - 6, PAD + r["v"].min() - 6, PAD + r["u"].max() + 6, PAD + r["v"].max() + 6],
                     outline=col, width=2)
    for n, st in status.items():
        u, v = st["center"]["u"] + PAD, st["center"]["v"] + PAD
        occ = st["center"]["occluded_by_depth"]
        col = (255, 0, 255) if not st["center"]["in_frame"] else ((255, 140, 0) if occ else (0, 220, 255))
        for (uu, vv) in st["ring_px"]:
            dr.point((uu + PAD, vv + PAD), fill=col)
        dr.line([u - 12, v, u + 12, v], fill=col, width=2)
        dr.line([u, v - 12, u, v + 12], fill=col, width=2)
        tag = "OUT" if not st["center"]["in_frame"] else ("OCCLUDED" if occ else "visible")
        dr.text((u + 14, v - 18), f"F{n} z={truth[n]['center'][2]:.3f}m {tag}", fill=col)
    if zoom:
        canvas = canvas.crop(zoom).resize(((zoom[2] - zoom[0]) * 2, (zoom[3] - zoom[1]) * 2), Image.NEAREST)
    canvas.save(path)


def main(seed=4024):
    OUT.mkdir(parents=True, exist_ok=True)
    tid = f"SV{seed - 4000:03d}"                      # 추가 변화 시행 ID (시드 4001~4100)
    trial = variation_trial(tid, seed, "supp_variation")
    with tempfile.TemporaryDirectory() as tmp:
        scene = Scene(layout=trial.layout, out_dir=Path(tmp))
        scene.reset(trial.dpos, trial.yaw_deg, trial.light)
        m, d = scene.model, scene.data
        frame = capture(scene.renderer, m, d)
        debug = {}
        dets = detect(frame, make_templates(scene.floors), debug)
        truth = scene.truth()
        # 집중해서 볼 층: 검출되지 않은 층 (없으면 목표 층)
        focus = tuple(n for n in scene.floors if n not in {r["floor"] for r in dets}) or (trial.expected_floor,)
        status = {}
        for n in scene.floors:
            own = {m.geom(f"label_{n}").id, m.geom(f"button_{n}_geom").id}
            c = truth[n]["center"]
            ring = face_samples(scene, n, "ring")
            ring_px = [tuple(float(x) for x in frame.project(p)) for p in ring]
            status[n] = {"center": point_status(m, d, frame, c, own), "ring_px": ring_px,
                         "label_face": coverage(m, d, frame, face_samples(scene, n, "label"), own),
                         "blue_ring": coverage(m, d, frame, ring, own)}
            if n in focus:
                status[n]["stages"] = stage_check(frame, debug, ring_px)
        # 화면 아래 경계(v = H-1)가 라벨 평면에서 어느 높이인지 (집중해서 보는 층의 라벨 u에서)
        W, H = frame.size
        bottom = {}
        for n in focus:
            c = truth[n]["center"]
            u = min(max(status[n]["center"]["u"], 0), W - 1)
            ray_w = frame.backproject(u, H - 1, 1.0) - frame.cam_xpos
            nrm = truth[n]["normal"]
            t = ((c - frame.cam_xpos) @ nrm) / (ray_w @ nrm)
            bottom[n] = round(float((frame.cam_xpos + t * ray_w)[2]), 4)
        # 녹화 영상(record.py)의 확대 화면: 검출 중심 평균을 가운데로 원본에서 300x240을 자른다(같은 계산)
        cu, cv = np.array([frame.project(r["center"]) for r in dets]).mean(axis=0)
        x0 = int(np.clip(cu - 150, 0, W - 300))
        y0 = int(np.clip(cv - 120, 0, H - 240))
        inset = {"crop_uv": [x0, y0, x0 + 300, y0 + 240]}
        for n in focus:
            vr = status[n]["blue_ring"]["v_range"]
            inset[n] = {"ring_v_range": vr, "inside_inset": bool(y0 <= vr[0] and vr[1] <= y0 + 240),
                        "px_below_inset_bottom": round(max(0.0, vr[1] - (y0 + 240)), 1)}
        # 반사실 확인: link1(팔 베이스)의 geom을 투명하게 하고 다시 찍어 인식 (메모리 안 모델만 바꿈)
        b1 = m.body("link1").id
        g1 = [g for g in range(m.ngeom) if m.geom_bodyid[g] == b1]
        rgba0 = m.geom_rgba[g1].copy()
        m.geom_rgba[g1, 3] = 0.0
        f2 = capture(scene.renderer, m, d)
        dbg2 = {}
        det2 = detect(f2, make_templates(scene.floors), dbg2)
        m.geom_rgba[g1] = rgba0
        counterfactual = {"hidden_geoms": [geom_label(m, g) for g in g1],
                          "seen_floors": [r["floor"] for r in det2],
                          "detections": [{"floor": r["floor"], "score": round(r["score"], 3), "margin": round(r["margin"], 3)}
                                         for r in det2]}
        dimg = np.clip((frame.depth - 0.3) / (2.0 - 0.3), 0, 1)
        dimg = Image.fromarray((255 * (1 - dimg)).astype(np.uint8)).convert("RGB")
        draw(frame, Image.fromarray(frame.rgb), truth, status, debug, OUT / f"{tid}_rgb.png", inset=inset)
        draw(frame, dimg, truth, status, debug, OUT / f"{tid}_depth.png", inset=inset)
        us = [status[n]["center"]["u"] + PAD for n in focus]
        vs = [status[n]["center"]["v"] + PAD for n in focus]
        zoom = (int(min(us) - 90), int(min(vs) - 70), int(max(us) + 90), int(max(vs) + 70))
        # 표시 없는 원본 확대(4배)와 표시 있는 확대를 따로 저장
        Image.fromarray(frame.rgb).crop((zoom[0] - PAD, zoom[1] - PAD, zoom[2] - PAD, zoom[3] - PAD)).resize(
            ((zoom[2] - zoom[0]) * 4, (zoom[3] - zoom[1]) * 4), Image.NEAREST).save(OUT / f"{tid}_zoom_raw.png")
        draw(frame, Image.fromarray(frame.rgb), truth, status, debug, OUT / f"{tid}_zoom.png", zoom=zoom, inset=inset)
        res = {"trial": trial.to_dict(), "focus_floors": list(focus), "seen_floors": [r["floor"] for r in dets],
               "detections": [{"floor": r["floor"], "score": round(r["score"], 3), "margin": round(r["margin"], 3)} for r in dets],
               "camera": {"pos": frame.cam_xpos.round(4).tolist(), "fovy": frame.fovy, "size": list(frame.size)},
               "image_bottom_edge_height_on_label_plane_m": bottom,
               "video_zoom_inset": inset, "counterfactual_link1_hidden": counterfactual,
               "floors": {n: {"label_center_z_m": round(float(truth[n]["center"][2]), 4),
                              **{k: v for k, v in st.items() if k != "ring_px"}} for n, st in status.items()}}
        (OUT / f"{tid}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        scene.close()

    # 추가 200회 중 목표 버튼 높이 ≤ 0.86 m
    rows = [r for r in csv.DictReader(open(ROOT / "results/supplementary/trials.csv", encoding="utf-8"))
            if r["target_z"] and float(r["target_z"]) <= 0.86]
    with open(OUT / "SV024_supp_low.csv", "w", encoding="utf-8", newline="") as f:
        cols = ["trial_id", "seed", "expected_floor", "target_z", "seen_floors", "success", "failure_type",
                "panel_dz", "yaw_deg", "layout"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print("low rows", len(rows))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4024)
