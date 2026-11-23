"""텍스트 명령 데모.

  python scripts/demo.py --text "3층 눌러줘"            기준 위치
  python scripts/demo.py --text "3층 눌러줘" --seed 5001  부록 E 변화 조건 규칙으로 장면 생성
  python scripts/demo.py                                 문장을 입력받는다(빈 줄이면 끝)
  python scripts/demo.py --text "3층 눌러줘" --record out.mp4   실행하며 mp4로 저장
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from assist.pipeline import Assistant  # noqa: E402
from assist.protocol import variation_trial  # noqa: E402
from assist.record import Recorder  # noqa: E402
from assist.scene import Scene  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="텍스트 명령 엘리베이터 버튼 누르기 데모")
    ap.add_argument("--text", help="명령 문장. 없으면 입력받는다")
    ap.add_argument("--seed", type=int, help="변화 조건 시드 (없으면 기준 위치)")
    ap.add_argument("--record", help="mp4로 저장할 경로 (--text와 함께 쓴다)")
    args = ap.parse_args()
    if args.record and not args.text:
        ap.error("--record는 --text와 함께 쓴다")

    if args.seed is not None:
        tr = variation_trial("DEMO", args.seed)
        scene = Scene(layout=tr.layout)
        cond = dict(dpos=tr.dpos, yaw_deg=tr.yaw_deg, light=tr.light)
        print(f"[장면] 시드 {args.seed}: 패널 이동 ({tr.dpos[0]:+.3f}, {tr.dpos[1]:+.3f}, {tr.dpos[2]:+.3f}) m, "
              f"회전 {tr.yaw_deg:+.1f}°, 조명 {tr.light:.2f}배, 숫자 배치 {tr.layout_str}")
    else:
        scene = Scene()
        cond = {}
        print("[장면] 기준 위치")
    assistant = Assistant(scene, say=lambda m: print(f"[로봇] {m}"))

    def run(text):
        scene.reset(**cond)                       # 매 명령을 관찰 자세에서 시작
        if args.record:
            where = f"seed {args.seed}" if args.seed is not None else "reference position"
            recorder = Recorder(assistant, f"Demo ({where}) | layout {''.join(str(n) for n in range(1, 7)) if args.seed is None else tr.layout_str}")
            rec = recorder.run(text)
            n = recorder.save(Path(args.record))
            print(f"[녹화] {args.record} ({n} 프레임)")
        else:
            rec = assistant.run(text)
        print(f"[판단] 해석 {rec['parsed_intent']}({rec['parsed_floor']}) → 행동 {rec['action']}, "
              f"보이는 층 {rec['seen_floors']}, 해석 {rec['t_parse_ms']:.2f} ms"
              + (f", 인식 {rec['t_perception_ms']:.0f} ms" if rec["t_perception_ms"] else "")
              + (f", 작업 {rec['t_task']:.2f} s(시뮬레이션)" if rec["t_task"] else ""))

    try:
        if args.text:
            run(args.text)
        else:
            while True:
                try:
                    text = input("명령> ").strip()
                except EOFError:
                    break
                if not text:
                    break
                run(text)
    finally:
        scene.close()


if __name__ == "__main__":
    main()
