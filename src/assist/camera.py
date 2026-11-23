"""RGB-D 촬영, 투영과 역투영 (계획서 부록 B).

카메라 좌표계: -z를 보고 +y가 위. 깊이는 mujoco.Renderer가 주는 광축 방향 거리(m)다.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class Frame:
    """인식 입력: RGB, 깊이, 내부 파라미터(fovy, 해상도), 카메라 자세. 시뮬레이터 정답은 없다."""
    rgb: np.ndarray          # (H, W, 3) uint8
    depth: np.ndarray        # (H, W) float, m
    fovy: float              # 도
    cam_xpos: np.ndarray     # (3,)
    cam_xmat: np.ndarray     # (3, 3) 열 = 카메라 x, y, z축(월드)

    @property
    def size(self):
        h, w = self.depth.shape
        return w, h

    def intrinsics(self):
        w, h = self.size
        f = (h / 2) / np.tan(np.radians(self.fovy) / 2)
        return f, (w - 1) / 2, (h - 1) / 2

    def backproject(self, u, v, d):
        """픽셀 (u, v)와 깊이 d → 월드 좌표 (N, 3)."""
        f, cx, cy = self.intrinsics()
        u, v, d = np.broadcast_arrays(np.asarray(u, float), np.asarray(v, float), np.asarray(d, float))
        p_cam = np.stack([(u - cx) / f * d, -(v - cy) / f * d, -d], axis=-1)
        return self.cam_xpos + p_cam @ self.cam_xmat.T

    def project(self, p_world):
        """월드 좌표 (..., 3) → 픽셀 (u, v). 카메라 앞(-z)에 있는 점만 의미가 있다."""
        f, cx, cy = self.intrinsics()
        q = (np.asarray(p_world, float) - self.cam_xpos) @ self.cam_xmat
        return cx + f * q[..., 0] / (-q[..., 2]), cy - f * q[..., 1] / (-q[..., 2])


def capture(renderer, model, data, camera="head_rgb"):
    """RGB와 깊이를 한 번씩 렌더링하고 카메라 자세를 함께 돌려준다."""
    cam_id = model.camera(camera).id
    renderer.update_scene(data, camera=camera)
    rgb = renderer.render().copy()
    renderer.enable_depth_rendering()
    renderer.update_scene(data, camera=camera)
    depth = renderer.render().copy()
    renderer.disable_depth_rendering()
    return Frame(rgb=rgb, depth=depth, fovy=float(model.cam_fovy[cam_id]),
                 cam_xpos=data.cam_xpos[cam_id].copy(), cam_xmat=data.cam_xmat[cam_id].reshape(3, 3).copy())
