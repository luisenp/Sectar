CODE_DIRS_TO_MOUNT = [
    '/private/home/lep/code/rllab',
    '/home/jcoreyes/embed/traj2vecv3',
    '/private/home/lep/code/doodad'
]
DIR_AND_MOUNT_POINT_MAPPINGS = [
    dict(
        local_dir='/private/home/lep/.mujoco/',
        mount_point='/private/home/lep/stuff/.mujoco',
    ),
]
LOCAL_LOG_DIR = '/private/home/lep/traj2vecv3/data/local/'
RUN_DOODAD_EXPERIMENT_SCRIPT_PATH = (
    '/private/home/lep/traj2vecv3/scripts/run_experiment_from_doodad.py'
)
DOODAD_DOCKER_IMAGE = '/private/home/lep/traj2vecv3:latest'

# This really shouldn't matter and in theory could be whatever
OUTPUT_DIR_FOR_DOODAD_TARGET = '/tmp/doodad-output/'
# OUTPUT_DIR_FOR_DOODAD_TARGET = '/tmp/dir/from/railrl-config/'
