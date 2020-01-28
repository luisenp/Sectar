#!/bin/bash

CURDIR=`pwd`

for ENV in swimmer swimmer_large block block_large wheeled wheeled_large waypoint waypoint_large; do
    CHECKPOINT_DIR=$1/${ENV}
    for GOAL in 0 1 2 3 4; do
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
        echo "#SBATCH --output=${SUBDIR}/stdout" >> ${SLURM}
        echo "#SBATCH --error=${SUBDIR}/stderr" >> ${SLURM}
        echo "#SBATCH --partition=priority" >> ${SLURM}
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
        sbatch ${SLURM}

        sleep 5
    done
done