import os

import numpy as np
from gym import utils
from gym.envs.mujoco import mujoco_env


def reward_fn(obs, rstate, goals):
    goals_aug = np.concatenate((goals.reshape(1, 2), np.zeros((1, 2))))
    ngoals = goals.shape[0]
    cur_goal = goals_aug[rstate]
    reward = np.zeros(obs.shape[0])
    good = (np.linalg.norm(obs[:, :2] - cur_goal, axis=-1) < 0.01)
    reward[good] += 1
    reward[rstate == ngoals] = 0
    rstate[good] += 1
    rstate = np.minimum(rstate, ngoals)
    return reward, rstate


def init_rstate(size):
    return np.zeros(size, dtype=int)


class MazeEnv(mujoco_env.MujocoEnv, utils.EzPickle):
    def __init__(self, verbose=False):
        self.verbose = verbose
        utils.EzPickle.__init__(self)
        dir_path = os.path.dirname(os.path.realpath(__file__))
        mujoco_env.MujocoEnv.__init__(self, '%s/assets/maze.xml' % dir_path, 2)

    def step(self, a):
        self.do_simulation(a, self.frame_skip)
        self.set_state(self.sim.data.qpos, np.zeros_like(self.sim.data.qpos))

        ob = self._get_obs()
        pos = ob[0:2]
        # rew = -np.linalg.norm(ob - np.array([0.1, 0.2]))

        if self.verbose:
            print(pos, 0)
        done = False
        return ob, None, done, {}

    def reset_model(self):
        qpos = self.init_qpos + self.np_random.uniform(size=self.model.nq, low=-0.01, high=0.01)
        qvel = np.zeros_like(self.init_qvel)
        self.set_state(qpos, qvel)
        return self._get_obs()

    def reset(self, reset_args=None):
        obs = super().reset()
        if reset_args is not None:
            return self.set_agent_abs_pos(reset_args)
        return obs

    def _get_obs(self):
        return np.concatenate([self.sim.data.qpos]).ravel() + np.array([-0.1, 0.2])

    def viewer_setup(self):
        v = self.viewer

    def set_agent_abs_pos(self, pos):
        self.set_state(pos - np.array([-0.1, 0.2]), np.zeros_like(pos))
        return self._get_obs()
