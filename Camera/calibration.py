"""
"""

__author__ = "Liyan Chen"

import cv2
import numpy as np


class CameraSolverNonlinear:
    def __init__(self, init_f=(1125.0, 1125.0), init_c=(960.0, 540.0), img_size=(1920, 1080)):
        self.init_f = init_f
        self.init_c = init_c
        self.img_size = img_size

    def solve(self, p_world, q_truth, iterations=300, term_epsilon=1e-3):
        f = np.random.normal(self.init_f, 40.0, [2]).astype(np.float64)
        c = np.random.normal(self.init_c, 20.0, [2]).astype(np.float64)

        init_cam = np.array([
            [f[0], 0, c[0]],
            [0, f[1], c[1]],
            [0, 0, 1]])
        flags = cv2.CALIB_USE_INTRINSIC_GUESS + cv2.CALIB_FIX_K3 + cv2.CALIB_FIX_K4 + cv2.CALIB_FIX_K5 + \
            cv2.CALIB_FIX_K6 + cv2.CALIB_FIX_S1_S2_S3_S4
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, iterations, term_epsilon)
        retval, cam, dist, rvecs, tvecs = cv2.calibrateCamera(
            [p_world.T.astype(np.float32)], [q_truth.T.astype(np.float32)], self.img_size, init_cam, None, flags=flags,
            criteria=crit)

        self.cam = cam
        self.dist = dist
        self.theta = rvecs[0]
        self.t = tvecs[0]

        return self.cam, self.dist, self.theta, self.t

    def dump_params(self):
        return self.cam, self.dist, self.theta, self.t, self.img_size

    def load_params(self, var_tuple):
        self.cam, self.dist, self.theta, self.t, self.img_size = var_tuple

    def projection_errs(self, p_world, q_truth):
        proj_pts, _ = cv2.projectPoints(p_world.T, self.theta, self.t, self.cam, self.dist)
        return np.sqrt(np.sum((q_truth.T - proj_pts[:, 0, :]) ** 2, axis=1))

    def undistort_pts(self, dist_p):
        undist = cv2.undistortPoints(np.expand_dims(dist_p.T, 0), self.cam, self.dist, np.identity(3), self.cam)
        return undist[0, ...]

    def undistort_img(self, img):
        undist = cv2.undistort(img, self.cam, self.dist)
        return undist

    def project_linear(self, p_world):
        proj_pts, _ = cv2.projectPoints(p_world.T, self.theta, self.t, self.cam, None)
        return proj_pts[:, 0, :]

    def camera_coordinate(self, p_world):
        R = cv2.Rodrigues(self.theta)[0]
        return np.matmul(R, p_world.T) + self.t

    def world_coordinate_by_z_imgpt(self, imgpt, z):
        R = cv2.Rodrigues(self.theta)[0]
        K = self.cam
        cam_pts = np.concatenate(
            [(imgpt - K[:2, 2]) / K.diagonal()[:2], np.ones((imgpt.shape[0], 1))], 1) * z[:, np.newaxis]
        return np.matmul(R.T, cam_pts.T - self.t).T


def build_pt_correspondence(cam_proj, unlabeled_dict, cam):
    if -1 in cam_proj[cam]:
        del cam_proj[cam][-1]
    p_world, q_proj = np.zeros([len(cam_proj[cam]), 3], np.float32), np.zeros([len(cam_proj[cam]), 2], np.float32)
    for ind, pt in enumerate(cam_proj[cam].items()):
        mkr_id, proj_pt = pt
        q_proj[ind, :] = proj_pt
        p_world[ind, :] = unlabeled_dict[mkr_id]["mean"]

    return p_world, q_proj


def calibrate_params(p_world, q_proj):
    mask = ~np.any(np.isnan(p_world), axis=1)
    p_world, q_proj = p_world[mask].T, q_proj[mask].T
    csolver = CameraSolverNonlinear()
    csolver.solve(p_world.astype(np.float64), q_proj.astype(np.float64))
    return csolver.dump_params()