"""발표용 그림: 본 방법(official_run1)과 고정 좌표 기준선(baseline_run1)의 성공률 막대그래프 (pillow).

  .venv/bin/python experiments/figures/make_success_bar.py   → docs/figures/success_bar.png
수치는 각 폴더의 trials.csv에서 센다(결과 파일만 읽고 쓰지 않는다).
"""
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]


def rate(folder, sets):
    rows = [r for r in csv.DictReader(open(ROOT / "results" / folder / "trials.csv", encoding="utf-8")) if r["set"] in sets]
    return sum(r["success"] == "1" for r in rows), len(rows)


groups = [("All (20)", ("basic", "variation")), ("Basic (10)", ("basic",)), ("Variation (10)", ("variation",))]
data = [(g, rate("official_run1", s), rate("baseline_run1", s)) for g, s in groups]
W, H, L, B, T = 900, 520, 90, 90, 70
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
f = ImageFont.load_default(size=20)
fs = ImageFont.load_default(size=16)
d.text((L, 20), "Button press success: ours vs fixed-coordinate baseline (official 20 trials)", fill="black", font=f)
ph = H - B - T
for k in range(0, 101, 25):
    y = H - B - ph * k / 100
    d.line([L, y, W - 40, y], fill=(225, 225, 225))
    d.text((L - 50, y - 9), f"{k}%", fill="black", font=fs)
gw = (W - 40 - L) / len(data)
for i, (g, (k1, n1), (k2, n2)) in enumerate(data):
    x0 = L + i * gw + gw * 0.15
    bw = gw * 0.32
    for j, (k, n, col) in enumerate(((k1, n1, (40, 110, 200)), (k2, n2, (200, 120, 40)))):
        x = x0 + j * (bw + gw * 0.06)
        y = H - B - ph * k / n
        d.rectangle([x, y, x + bw, H - B], fill=col)
        d.text((x + 4, y - 22), f"{k}/{n}", fill="black", font=fs)
    d.text((L + i * gw + gw * 0.25, H - B + 10), g, fill="black", font=fs)
d.rectangle([W - 330, H - 50, W - 315, H - 35], fill=(40, 110, 200))
d.text((W - 308, H - 52), "ours (perception)", fill="black", font=fs)
d.rectangle([W - 170, H - 50, W - 155, H - 35], fill=(200, 120, 40))
d.text((W - 148, H - 52), "fixed baseline", fill="black", font=fs)
img.save(ROOT / "docs" / "figures" / "success_bar.png")
print(data)
