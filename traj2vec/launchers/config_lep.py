CODE_DIRS_TO_MOUNT = [
    '/private/home/lep/code/rllab',
    '/private/home/lep/code/Sectar',
    '/private/home/lep/code/baselines',
]
DIR_AND_MOUNT_POINT_MAPPINGS = [
    dict(
        local_dir='/private/home/lep/.mujoco/',
        mount_point='/checkpoint/lep/hmbrl/.mujoco',
    ),
]
LOCAL_LOG_DIR = '/checkpoint/lep/hmbrl/Sectar/data/local/'
RUN_DOODAD_EXPERIMENT_SCRIPT_PATH = (
    '/private/home/lep/code/Sectar/scripts/run_experiment_from_doodad.py'
)
DOODAD_DOCKER_IMAGE = 'wynd07/traj2vecv3-pytorch-0.4.0:latest'
# DOODAD_DOCKER_IMAGE = 'jcoreyes/traj2vecv3:latest'


# This really shouldn't matter and in theory could be whatever
OUTPUT_DIR_FOR_DOODAD_TARGET = '/checkpoint/lep/hmbrl/tmp/doodad-output/'
# OUTPUT_DIR_FOR_DOODAD_TARGET = '/tmp/dir/from/railrl-config/'
