#!/bin/bash

CURDIR=`pwd`
ENV=${2:-waypoint}
CHECKPOINT_DIR=$1/${ENV}


for GOAL in 1 2 3 4 5; do
    SUBDIR=${CHECKPOINT_DIR}/goal_${GOAL}
    mkdir -p ${SUBDIR}
    mkdir -p ${SUBDIR}/jobscripts
    cp -r ${CURDIR}/* ${SUBDIR}
    SCRIPT=${SUBDIR}/jobscripts/run.sh
    SLURM=${SUBDIR}/jobscripts/run.slrm

    JOBNAME=sectar_${ENV}_${GOAL}

    echo "#!/bin/sh" > ${SCRIPT}
    echo "#!/bin/sh" > ${SLURM}
    echo "#SBATCH --job-name=${JOBNAME}" >> ${SLURM}
    echo "#SBATCH --output=${CHECKPOINT_DIR}/stdout" >> ${SLURM}
    echo "#SBATCH --error=${CHECKPOINT_DIR}/stderr" >> ${SLURM}
    echo "#SBATCH --partition=dev" >> ${SLURM}
    echo "#SBATCH --nodes=1" >> ${SLURM}
    echo "#SBATCH --time=4000" >> ${SLURM}
    echo "#SBATCH --ntasks-per-node=1" >> ${SLURM}
    echo "#SBATCH --signal=USR1" >> ${SLURM}
    echo "#SBATCH --gres=gpu:volta:1" >> ${SLURM}
    echo "#SBATCH --mem=150000" >> ${SLURM}
    echo "#SBATCH --comment=\"paper results for ICML\"" >> ${SLURM}
    echo "#SBATCH -c 1" >> ${SLURM}
    echo "srun sh ${SCRIPT}" >> ${SLURM}
    echo "echo \$SLURM_JOB_ID >> ${SUBDIR}/id" >> ${SCRIPT}
    echo "nvidia-smi" >> ${SCRIPT}
    echo "cd ${SUBDIR}/exps/${ENV}" >> ${SCRIPT}
    echo MKL_THREADING_LAYER=GNU python ${ENV}_exp.py --goal_index ${GOAL} >> ${SCRIPT}
#    sbatch ${SLURM}
done