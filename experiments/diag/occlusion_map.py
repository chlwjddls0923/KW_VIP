"""가림 한계 지도 (사후 탐색, 확인만. src/assist는 import만 한다).

  .venv/bin/python experiments/diag/occlusion_map.py

- 누르기 없이 관찰 자세에서 촬영·인식만 한다(파이프라인이 인식하는 시점과 같은 reset 직후).
- 격자: 패널 dz −0.10~+0.10 m(0.01 간격) × 회전 −10, 0, +10° × dx −0.10, 0, +0.10 m. 기본 숫자 배치, 조명 1.0, dy 0.
  격자 값이 정해져 있어 난수 시드는 쓰지 않는다.
- 버튼마다: 라벨 중심 높이, 화면 안 여부, 검출 여부(점수·여유), 파란 고리 표본 96점 중 link1이 가린 비율
  (카메라에서 각 점으로 쏜 mj_ray의 첫 충돌이 link1의 geom인 점), 깊이로 본 전체 가림 비율, 라벨 면 81점 중 link1 가림 비율.
출력: results/diag/occlusion_map/ (grid.csv, by_height.csv, 그림, README.md는 따로 작성)
"""
import csv
import sys
import tempfile
import time
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
from assist.camera import capture  # noqa: E402
from assist.perception import detect, make_templates  # noqa: E402
from assist.scene import Scene  # noqa: E402
from sv024 import face_samples  # noqa: E402  (같은 표본점 정의를 쓴다)

OUT = ROOT / "results" / "diag" / "occlusion_map"
DZ = [round(-0.10 + 0.01 * i, 2) for i in range(21)]
YAW = [-10.0, 0.0, 10.0]
DX = [-0.10, 0.0, 0.10]
OCC_TOL = 0.002


def frac_link1(m, d, frame, pts, link1_geoms):
    """표본점 중 (화면 안, link1에 가림, 깊이로 가림) 수."""
    w, h = frame.size
    n_in = n_l1 = n_dep = 0
    gid = np.array([-1], dtype=np.int32)
    for p in pts:
        u, v = (float(x) for x in frame.project(p))
        if not (0 <= u <= w - 1 and 0 <= v <= h - 1):
            continue
        n_in += 1
        vec = p - frame.cam_xpos
        dist = float(np.linalg.norm(vec))
        hit = mujoco.mj_ray(m, d, frame.cam_xpos, vec / dist, None, 1, -1, gid)
        if int(gid[0]) in link1_geoms and hit < dist - OCC_TOL:
            n_l1 += 1
        q = (p - frame.cam_xpos) @ frame.cam_xmat
        if frame.depth[int(round(v)), int(round(u))] < -q[2] - OCC_TOL:
            n_dep += 1
    return n_in, n_l1, n_dep


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        scene = Scene(out_dir=Path(tmp))                   # 기본 숫자 배치
        m, d = scene.model, scene.data
        l1 = m.body("link1").id
        link1_geoms = {g for g in range(m.ngeom) if m.geom_bodyid[g] == l1}
        templates = make_templates(scene.floors)
        for dx in DX:
            for yaw in YAW:
                for dz in DZ:
                    scene.reset((dx, 0.0, dz), yaw, 1.0)
                    frame = capture(scene.renderer, m, d)
                    dets = {r["floor"]: r for r in detect(frame, templates)}
                    truth = scene.truth()
                    w, h = frame.size
                    for n in scene.floors:
                        c = truth[n]["center"]
                        u, v = (float(x) for x in frame.project(c))
                        ring = face_samples(scene, n, "ring")
                        lab = face_samples(scene, n, "label")
                        r_in, r_l1, r_dep = frac_link1(m, d, frame, ring, link1_geoms)
                        l_in, l_l1, _ = frac_link1(m, d, frame, lab, link1_geoms)
                        det = dets.get(n)
                        rows.append({"dx": dx, "dz": dz, "yaw": yaw, "floor": n, "label_z": round(float(c[2]), 4),
                                     "u": round(u, 1), "v": round(v, 1),
                                     "center_in_frame": int(0 <= u <= w - 1 and 0 <= v <= h - 1),
                                     "ring_in_frame_frac": round(r_in / len(ring), 3),
                                     "ring_link1_frac": round(r_l1 / len(ring), 3),
                                     "ring_depth_occ_frac": round(r_dep / len(ring), 3),
                                     "label_link1_frac": round(l_l1 / len(lab), 3),
                                     "detected": int(det is not None),
                                     "score": round(det["score"], 3) if det else "",
                                     "margin": round(det["margin"], 3) if det else ""})
        scene.close()
    cols = list(rows[0])
    with open(OUT / "grid.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # 높이별(0.01 m 구간) 검출률
    bins = {}
    for r in rows:
        b = np.floor(r["label_z"] / 0.01 + 1e-9) * 0.01
        bins.setdefault(round(b, 2), []).append(r)
    by = []
    for b in sorted(bins):
        rs = bins[b]
        occ = [r for r in rs if r["ring_link1_frac"] > 0]
        by.append({"z_bin_from": f"{b:.2f}", "z_bin_to": f"{b + 0.01:.2f}", "n": len(rs),
                   "detected": sum(r["detected"] for r in rs),
                   "det_rate": round(sum(r["detected"] for r in rs) / len(rs), 3),
                   "n_ring_link1_gt0": len(occ),
                   "mean_ring_link1_frac": round(float(np.mean([r["ring_link1_frac"] for r in rs])), 3),
                   "max_ring_link1_frac": round(max(r["ring_link1_frac"] for r in rs), 3),
                   "n_center_out_of_frame": sum(1 - r["center_in_frame"] for r in rs)})
    with open(OUT / "by_height.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(by[0]))
        w.writeheader()
        w.writerows(by)

    # 가림 비율 구간별 검출률
    edges = [0, 1e-9, 0.05, 0.10, 0.20, 0.30, 0.40, 0.60, 1.01]
    by_occ = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        rs = [r for r in rows if lo <= r["ring_link1_frac"] < hi]
        if rs:
            by_occ.append({"ring_link1_frac_from": lo, "to": hi, "n": len(rs),
                           "detected": sum(r["detected"] for r in rs),
                           "det_rate": round(sum(r["detected"] for r in rs) / len(rs), 3)})
    with open(OUT / "by_occlusion.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(by_occ[0]))
        w.writeheader()
        w.writerows(by_occ)
    plot_height(by, OUT / "det_rate_by_height.png")
    plot_scatter(rows, OUT / "occlusion_vs_height.png")
    print(f"{len(rows)} buttons, {time.time() - t0:.1f}s")


def plot_height(by, path):
    """높이 구간별 검출률(막대)과 link1 평균 가림 비율(점선)."""
    W, H, L, B, T = 1000, 520, 80, 90, 60
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    f, fs = ImageFont.load_default(size=18), ImageFont.load_default(size=13)
    dr.text((L, 18), "Detection rate by label-center height (bars) / mean ring fraction hidden by link1 (red)", fill="black", font=f)
    ph, pw = H - B - T, W - L - 40
    for k in range(0, 101, 25):
        y = H - B - ph * k / 100
        dr.line([L, y, L + pw, y], fill=(225, 225, 225))
        dr.text((L - 45, y - 8), f"{k}%", fill="black", font=fs)
    bw = pw / len(by)
    pts = []
    for i, b in enumerate(by):
        x = L + i * bw
        y = H - B - ph * b["det_rate"]
        dr.rectangle([x + 1, y, x + bw - 1, H - B], fill=(40, 110, 200))
        pts.append((x + bw / 2, H - B - ph * b["mean_ring_link1_frac"]))
        if i % 3 == 0:
            dr.text((x, H - B + 8), b["z_bin_from"], fill="black", font=fs)
    dr.line(pts, fill=(220, 40, 40), width=2)
    dr.text((L, H - B + 30), "label-center height bin (m, lower edge)", fill="black", font=fs)
    img.save(path)


def plot_scatter(rows, path):
    """x = 라벨 중심 높이, y = link1이 가린 고리 비율. 파랑 = 검출, 빨강 = 미검출."""
    W, H, L, B, T = 1000, 560, 80, 80, 60
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    f, fs = ImageFont.load_default(size=18), ImageFont.load_default(size=13)
    zs = [r["label_z"] for r in rows]
    z0, z1 = min(zs) - 0.01, max(zs) + 0.01
    ph, pw = H - B - T, W - L - 40
    dr.text((L, 18), "Each button: height vs ring fraction hidden by link1 (blue = detected, red = missed)", fill="black", font=f)
    for k in range(0, 101, 20):
        y = H - B - ph * k / 100
        dr.line([L, y, L + pw, y], fill=(230, 230, 230))
        dr.text((L - 45, y - 8), f"{k}%", fill="black", font=fs)
    z = np.ceil(z0 * 20) / 20
    while z <= z1:
        x = L + pw * (z - z0) / (z1 - z0)
        dr.line([x, T, x, H - B], fill=(235, 235, 235))
        dr.text((x - 14, H - B + 8), f"{z:.2f}", fill="black", font=fs)
        z += 0.05
    x86 = L + pw * (0.86 - z0) / (z1 - z0)
    dr.line([x86, T, x86, H - B], fill=(120, 120, 120), width=1)
    dr.text((x86 + 4, T + 4), "0.86 m (plan sec.3)", fill=(90, 90, 90), font=fs)
    for r in sorted(rows, key=lambda r: r["detected"], reverse=True):
        x = L + pw * (r["label_z"] - z0) / (z1 - z0)
        y = H - B - ph * r["ring_link1_frac"]
        col = (40, 110, 200) if r["detected"] else (220, 40, 40)
        dr.ellipse([x - 3, y - 3, x + 3, y + 3], outline=col, width=2)
    dr.text((L, H - B + 30), "label-center height (m)", fill="black", font=fs)
    img.save(path)


if __name__ == "__main__":
    main()
