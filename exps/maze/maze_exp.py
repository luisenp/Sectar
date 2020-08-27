import argparse
from os import getcwd

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import traj2vec.config as config
from doodad.easy_sweep.hyper_sweep import Sweeper
from sklearn.model_selection import train_test_split
import traj2vec.launchers.config as launcher_config
from traj2vec.algos.ppo import PPO
from traj2vec.algos.vae_bc import TrajVAEBC
from traj2vec.algos.vaepdentropy import VAEPDEntropy
from traj2vec.algos.vpg import VPG
from traj2vec.datasets.dataset import MazeContDataset
from traj2vec.envs.env_utils import make_env
from traj2vec.models.baselines.baseline import ZeroBaseline
from traj2vec.models.baselines.linear_feature_baseline import LinearFeatureBaseline
from traj2vec.models.baselines.nn_baseline import NNBaseline
from traj2vec.models.containers.categorical_network import RecurrentCategoricalPolicy, CategoricalNetwork, LSTMPolicy
from traj2vec.models.containers.gaussian_network import GaussianNetwork, GaussianRecurrentNetwork, \
    GaussianRecurrentPolicy, GaussianBidirectionalNetwork
from traj2vec.models.containers.mixed_network import MixedRecurrentNetwork
from traj2vec.nn.mlp import MLP
from traj2vec.nn.parameter import Parameter
from traj2vec.nn.rnn import RNN
from traj2vec.launchers.launcher_util_lep import run_experiment
from traj2vec.nn.running_stat import ObsNorm
from traj2vec.utils.torch_utils import set_gpu_mode
from traj2vec.envs.maze import reward_fn, init_rstate
import os
import sys
import json



def run_task(vv):
    set_gpu_mode(vv['gpu'])
    env_name = vv['env_name']
    env = make_env(env_name, 1, 0, '/tmp/gym')
    obs_dim = int(env().observation_space.shape[0])
    action_dim = int(env().action_space.shape[0])
    print(obs_dim, action_dim)

    vv['block_config'] = [vv['starts_goals'][0], vv['starts_goals'][1]]
    path_len = vv['path_len']
    data_path = None
    # True so that behavioral cloning has access to actions
    use_actions = True

    #create a dummy datset since we initialize with no data
    dummy = np.zeros((1, path_len+1, obs_dim + action_dim))
    train_data, test_data = dummy, dummy
    if vv['load_models_dir'] is not None:
        dir = getcwd() + "/research/lang/traj2vecv3_jd/" + vv['load_models_dir']
        train_data = np.load(dir + "/traindata.npy").reshape((-1, path_len+1, obs_dim + action_dim))
        print('train_data', train_data.shape)

    train_dataset = MazeContDataset(data_path=data_path, raw_data=train_data, obs_dim=obs_dim, action_dim=action_dim, path_len=path_len,
                          env_id='Playpen', normalize=False, use_actions=use_actions, batch_size=vv['batch_size'],
                                      buffer_size=vv['buffer_size'])
    #validation set for vae training
    test_dataset = MazeContDataset(data_path=data_path, raw_data=train_data, obs_dim=obs_dim, action_dim=action_dim, path_len=path_len,
                          env_id='Playpen', normalize=False, use_actions=use_actions, batch_size=vv['batch_size'],
                                      buffer_size=vv['buffer_size'])

    #this holds the data from the latest iteration for joint training
    dummy_dataset = MazeContDataset(data_path=data_path, raw_data=train_data, obs_dim=obs_dim, action_dim=action_dim, path_len=path_len,
                          env_id='Playpen', normalize=False, use_actions=use_actions, batch_size=vv['batch_size'],
                                      buffer_size=vv['buffer_size'])

    train_dataset.clear()
    test_dataset.clear()
    dummy_dataset.clear()

    latent_dim = vv['latent_dim']
    rnn_hidden_dim = vv['decoder_rnn_hidden_dim']

    step_dim = obs_dim

    # build encoder
    if vv['encoder_type'] == 'mlp':
        encoder = GaussianNetwork(
            mean_network=MLP((path_len+1)*step_dim, latent_dim, hidden_sizes=vv['encoder_hidden_sizes'], hidden_act=nn.ReLU),
            log_var_network=MLP((path_len+1)*step_dim, latent_dim)
        )
    elif  vv['encoder_type'] == 'lstm':
        encoder = GaussianBidirectionalNetwork(
            input_dim=step_dim,
            hidden_dim=rnn_hidden_dim,
            num_layers=2,
            mean_network=MLP(2 * rnn_hidden_dim, latent_dim),
            log_var_network=MLP(2 * rnn_hidden_dim, latent_dim)
        )

    # build state decoder
    if vv['decoder_var_type'] == 'param':
        decoder_log_var_network = Parameter(latent_dim, step_dim, init=np.log(0.1))
    else:
        decoder_log_var_network = MLP(rnn_hidden_dim, step_dim)
    if vv['decoder_type'] == 'grnn':
        decoder = GaussianRecurrentNetwork(
            recurrent_network=RNN(nn.LSTM(step_dim + latent_dim, rnn_hidden_dim), rnn_hidden_dim),
            mean_network=MLP(rnn_hidden_dim, step_dim, hidden_sizes=vv['decoder_hidden_sizes'], hidden_act=nn.ReLU),
            #log_var_network=Parameter(latent_dim, step_dim, init=np.log(0.1)),
            log_var_network=decoder_log_var_network,
            path_len=path_len,
            output_dim=step_dim,
            min_var=1e-4,
        )
    elif vv['decoder_type'] == 'gmlp':
        decoder = GaussianNetwork(
            mean_network=MLP(latent_dim, path_len*step_dim, hidden_sizes=vv['decoder_hidden_sizes'],
                             hidden_act=nn.ReLU),
            log_var_network=Parameter(latent_dim, path_len*step_dim, init=np.log(0.1)),
            min_var=1e-4
        )
    elif vv['decoder_type'] == 'mixedrnn':
        gauss_output_dim = 10
        cat_output_dim = 5
        decoder = MixedRecurrentNetwork(
            recurrent_network=RNN(nn.LSTM(step_dim + latent_dim, rnn_hidden_dim), rnn_hidden_dim),
            mean_network=MLP(rnn_hidden_dim, gauss_output_dim, hidden_sizes=vv['decoder_hidden_sizes'], hidden_act=nn.ReLU),
            prob_network=MLP(rnn_hidden_dim, cat_output_dim, final_act=nn.Softmax),
            log_var_network=Parameter(latent_dim, gauss_output_dim, init=np.log(0.1)),
            path_len=path_len,
            output_dim=step_dim,
            min_var=1e-4,
            gaussian_output_dim=gauss_output_dim,
            cat_output_dim=cat_output_dim
        )

    policy = GaussianNetwork(
        mean_network=MLP(obs_dim+latent_dim, action_dim, hidden_sizes=vv['policy_hidden_sizes'],
                         hidden_act=nn.ReLU),
        log_var_network=Parameter(obs_dim+latent_dim, action_dim, init=np.log(1))
    )
    policy_ex = GaussianNetwork(
        mean_network=MLP(obs_dim, action_dim, hidden_sizes=vv['policy_hidden_sizes'],
                         hidden_act=nn.ReLU),
        log_var_network=Parameter(obs_dim, action_dim, init=np.log(20))
    )

    # vae with behavioral cloning
    vae = TrajVAEBC(encoder=encoder, decoder=decoder, latent_dim=latent_dim, step_dim=step_dim,
                  feature_dim=train_dataset.obs_dim, env=env, path_len=train_dataset.path_len,
                  init_kl_weight=vv['kl_weight'], max_kl_weight=vv['kl_weight'], kl_mul=1.03,
                  loss_type=vv['vae_loss_type'], lr=vv['vae_lr'], obs_dim=obs_dim,
                  act_dim=action_dim, policy=policy, bc_weight=vv['bc_weight'])

    # 0 baseline due to constantly changing rewards
    baseline = ZeroBaseline()
    # policy opt for policy decoder
    policy_algo = PPO(env, env_name, policy, baseline=baseline, obs_dim=obs_dim,
                             action_dim=action_dim, max_path_length=path_len, center_adv=True,
                     optimizer=optim.Adam(policy.get_params(), vv['policy_lr'], eps=1e-5), #vv['global_lr']),
                      use_gae=vv['use_gae'], epoch=10, ppo_batch_size=200)

    # baseline for the explorer
    baseline_ex = ZeroBaseline()
    # policy opt for the explorer
    policy_ex_algo = PPO(env, env_name, policy_ex, baseline=baseline_ex, obs_dim=obs_dim,
                             action_dim=action_dim, max_path_length=path_len, center_adv=True,
                     optimizer=optim.Adam(policy_ex.get_params(), vv['policy_lr'], eps=1e-5), #vv['global_lr']),
                      use_gae=vv['use_gae'], epoch=10, ppo_batch_size=200,
                      entropy_bonus = vv['entropy_bonus'])

    # for loading the model from a saved state
    if vv['load_models_dir'] is not None:
        dir = getcwd() + "/research/lang/traj2vecv3_jd/" + vv['load_models_dir']
        itr = vv['load_models_idx']
        encoder.load_state_dict(torch.load(dir + '/encoder_%d.pkl' % itr))
        decoder.load_state_dict(torch.load(dir + '/decoder_%d.pkl' % itr))
        policy.load_state_dict(torch.load(dir + '/policy_%d.pkl' % itr))
        policy_ex.load_state_dict(torch.load(dir + '/policy_ex_%d.pkl' % itr))
        adam_state = torch.load(dir + '/vae_optimizer_%d.pkl' % itr)
        adam_state['param_groups'][0]['eps'] = 1e-5
        vae.optimizer.load_state_dict(adam_state)
        policy_algo.optimizer.load_state_dict(torch.load(dir + '/policy_optimizer_%d.pkl' % itr))

    # waypoints for the agent
    goals = np.array(vv['starts_goals'][1])
    # reward function for MPC
    rf = lambda obs, rstate: reward_fn(obs, rstate, goals)

    # main algorithm launcher, includes mpc controller and exploration
    vaepd = VAEPDEntropy(env, env_name, policy, policy_ex, encoder, decoder,
        path_len, obs_dim, action_dim, step_dim, policy_algo, policy_ex_algo,
                  train_dataset, latent_dim, vae,
                  batch_size=400,
                  block_config=vv['block_config'],
                  plan_horizon = vv['mpc_plan'], 
                  max_horizon = vv['mpc_max'], 
                  mpc_batch = vv['mpc_batch'],
                  rand_per_mpc_step = vv['mpc_explore_step'],
                  mpc_explore = 2048, 
                  mpc_explore_batch = 5,
                  reset_ent = vv['reset_ent'],
                  vae_train_steps = vv['vae_train_steps'],
                  mpc_explore_len=vv['mpc_explore_len'],
                  true_reward_scale=vv['true_reward_scale'],
                  discount_factor=vv['discount_factor'],
                  reward_fn=(rf, init_rstate)
                  )


    vaepd.train(train_dataset, test_dataset=test_dataset, dummy_dataset=dummy_dataset, plot_step=10, max_itr=vv['max_itr'], record_stats=True, print_step=1000,
                             save_step=2,
               start_itr=0, train_vae_after_add=vv['train_vae_after_add'],
                joint_training=vv['joint_training'])

parser = argparse.ArgumentParser()

variant_group = parser.add_argument_group('variant')
# this is just a name for the saving directory
variant_group.add_argument('--algo', default='entropy')
# useful for debugging a trained loaded model
variant_group.add_argument('--debug', default='None')
variant_group.add_argument('--gpu', default="True")
# name for exploration directory
variant_group.add_argument('--exp_dir', default='tmp')
# where to run, can be ec2, local_docker, local
variant_group.add_argument('--mode', default='local')
# params for loading the model
variant_group.add_argument('--load_models_dir', default=None)
variant_group.add_argument('--load_models_idx', default=None, type=int)
# name of gym env
variant_group.add_argument('--env_name', default='MazeEnv-v0')
variant_group.add_argument('--max_itr', default=1000, type=int)
variant_group.add_argument('--goal_index', default=0, type=int)

v_command_args = parser.parse_args()
command_args = {k.dest:vars(v_command_args)[k.dest] for k in variant_group._group_actions}

starts_goals = np.load('/private/home/lep/code/Sectar/goals/maze.npy').tolist()

params = {
    'path_len': [19],
    'starts_goals': starts_goals,
    'mpc_plan': [20],
    'mpc_max': [50],
    'add_frac': [100],
    'vae_train_steps': [30],
    'reset_ent': [0],
    'mpc_batch': [40],
    'mpc_explore_step': [400],
    'mpc_explore_len': [10],
    'sparse_reward': [True],
    'joint_training': [True],
    'true_reward_scale': [0],
    'discount_factor': [0.99],
    'policy_type': ['gmlp'],
    'policy_rnn_hidden_dim': [128],
    'policy_hidden_sizes': [(400, 300, 200)],
    'random_action_p': [0],
    'encoder_type': ['lstm'],
    'latent_dim': [8],
    'use_actions': [True],
    'encoder_hidden_sizes': [(128, 128, 128)],
    'decoder_hidden_sizes': [(128, 128, 128)],
    'decoder_rnn_hidden_dim': [512],
    'decoder_type': ['grnn'],
    'decoder_var_type': ['param'],
    'initial_data_size': [9000],
    'buffer_size': [1000000],
    'dummy_buffer_size': [1800*5],

    'vae_lr': [1e-3],
    'policy_lr': [3e-4],
    'entropy_bonus': [1e-3],
    'use_gae': [True],
    'batch_size': [300],
    'seed': [111],
    'bc_weight': [100],
    'kl_weight': [2],
    'vae_loss_type': ['ll'],
    'train_vae_after_add': [10],
}

exp_id = 0
command_args['gpu'] = command_args['gpu'] == 'True'
all_args = list(Sweeper(params, 1))
args = all_args[command_args['goal_index']]
env_name = command_args['env_name'].split('-')[0]
alg_name = command_args['algo']
exp_dir = command_args['exp_dir']
print("gpu", command_args['gpu'], type(command_args['gpu']))
with open('/private/home/lep/sectar/variant_wheeled.json', 'r') as f:
    loaded_args = json.loads(f.read())
for arg_name in loaded_args:
    if arg_name in args and arg_name not in ['block_config', 'border', 'debug', 'docker',
                                             'env_name', 'exp_dir', 'exp_id', 'goal_idx', 'gpu',
                                             'initial_data_path', 'load_models_dir',
                                             'load_models_idx', 'mode', 'seed', 'unique_id']:
        args[arg_name] = loaded_args[arg_name]
base_log_dir = getcwd() + '/data/%s/%s/%s' % (alg_name, env_name, exp_dir)
run_experiment(
    run_task,
    exp_id=exp_id,
    use_gpu=command_args['gpu'],
    mode=command_args['mode'],
    seed=args['seed'],
    prepend_date_to_exp_prefix=False,
    exp_prefix='%s-%s-%s' %(env_name, alg_name, exp_dir),
    base_log_dir=base_log_dir,
    variant={**args, **command_args},
)
if command_args['debug'] != 'None':
    sys.exit(0)
exp_id += 1
