"""단계 5 통과 기준: 통합."""
from collections import Counter

import pytest

from assist.pipeline import Assistant, SceneCache, run_trial
from assist.protocol import STILL_JOINT, Trial, check_trials, dev_trials, judge
from assist.scene import Scene

EXTRA = [
    Trial("X01", "check", None, "큐브를 집어서 옮겨줘", "REJECT", None),
    Trial("X02", "check", None, "버튼 눌러줘", "CLARIFY", None),
    Trial("X03", "check", None, "3층 말고 4층 눌러", "PRESS", 4),
]


@pytest.fixture(scope="module")
def cache():
    c = SceneCache()
    yield c
    c.close()


def test_eight_commands_at_reference(cache):
    """점검 5종 + 큐브(REJECT) + '버튼 눌러줘'(CLARIFY) + '3층 말고 4층 눌러'(4층 누름). 기준 위치."""
    results = []
    for tr in check_trials() + EXTRA:
        row, rec = run_trial(tr, cache)
        results.append((tr.trial_id, tr.text, row["action"], row["success"], row["failure_type"],
                        row["max_slide_target_mm"], row["max_joint_motion_rad"]))
    for r in results:
        print(r)
    assert all(r[3] == "1" for r in results), results
    # 움직이면 안 되는 명령은 관절 최대 변화 < 0.02 rad
    for r in results:
        tr = next(t for t in check_trials() + EXTRA if t.trial_id == r[0])
        if tr.expected_action != "PRESS":
            assert float(r[6]) < STILL_JOINT


def test_single_button_scene():
    """버튼 1개 장면: '3층 눌러줘'는 성공, '4층 눌러줘'는 움직이지 않고 거부."""
    sc = Scene(layout={3: (0.0, 0.0)}, radius=0.045)
    a = Assistant(sc, say=lambda m: None)
    sc.reset()
    rec = a.run("3층 눌러줘")
    ok3, f3 = judge(Trial("S1", "check", None, "3층 눌러줘", "PRESS", 3), rec)
    sc.reset()
    rec4 = a.run("4층 눌러줘")
    ok4, f4 = judge(Trial("S2", "check", None, "4층 눌러줘", "REJECT", None), rec4)
    print(f"\nsingle: 3층 {rec['max_slide'][3] * 1000:.1f} mm {rec['messages']}; "
          f"4층 {rec4['action']} {rec4['messages']} joint {rec4['max_joint_motion']:.2e}")
    sc.close()
    assert ok3, f3
    assert ok4 and rec4["action"] == "REJECT", (f4, rec4["messages"])


def test_dev_seeds_variation(cache):
    """개발용 시드 5001~5020(변화 조건). 목표 버튼 높이 0.90 m 이상에서 실패하면 안 된다."""
    rows = [run_trial(tr, cache)[0] for tr in dev_trials()]
    fails = [r for r in rows if r["success"] != "1"]
    print(f"\ndev {len(rows) - len(fails)}/{len(rows)}; failures: {Counter(r['failure_type'] for r in fails)}")
    for r in rows:
        print(f"{r['trial_id']} {r['text']} -> {r['action']} ok={r['success']} {r['failure_type']} "
              f"target {r['max_slide_target_mm']} mm z={r['target_z']} seen={r['seen_floors']} "
              f"tilt={r['tilt_deg']} t_press={r['t_press_s']} perc={r['t_perception_ms']} ms")
    high_fail = [r for r in fails if float(r["target_z"]) >= 0.90]
    assert not high_fail, high_fail
