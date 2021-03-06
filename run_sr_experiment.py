#!/usr/bin/env python
import sys
import os
import datetime
import subprocess
import multiprocessing


DATASET_DIR = "/media/disk2/datasets/chesapeake_data/"
OUTPUT_DIR = "results/results_sr_epochs_100_0/"
TIMEOUT = 3600 * 12

_gpu_ids = [0,1,2]
num_gpus = len(_gpu_ids)
jobs_per_gpu = [[] for i in range(num_gpus)]

def run_jobs(jobs):
    print("Starting job runner")
    for (command, args) in jobs:
        print(datetime.datetime.now(), command)
        
        output_dir = os.path.join(args["output"], args["exp_name"])
        os.makedirs(output_dir, exist_ok=True)
        os.system(command + " > %s 2>&1" % (os.path.join(output_dir, args["log_name"])))

        # process = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
        # with open(os.path.join(output_dir, args["log_name"]), 'w') as f:
        #     while process.returncode is None:
        #         for line in process.stdout:
        #             f.write(line.decode('utf-8').strip() + "\n")
        #         process.poll()


train_state_list = [
    "de_1m_2013", "ny_1m_2013", "md_1m_2013", "pa_1m_2013", "va_1m_2014", "wv_1m_2014"
]
test_state_list = [
    "de_1m_2013", "ny_1m_2013", "md_1m_2013", "pa_1m_2013", "va_1m_2014", "wv_1m_2014"
]

gpu_idx = 0

for train_state in train_state_list:
    for test_state in test_state_list:

        if not os.path.exists(os.path.join(OUTPUT_DIR,"train-hr_%s_train-sr_%s/final_model.h5" % (train_state, test_state))):
            gpu_id = _gpu_ids[gpu_idx]

            args = {
                "output": OUTPUT_DIR,
                "exp_name": "train-hr_%s_train-sr_%s" % (train_state, test_state),
                "train_state_list": train_state,
                "val_state_list": train_state,
                "superres_state_list": test_state,
                "gpu": gpu_id, 
                "data_dir": DATASET_DIR,
                "log_name": "log.txt",
                "learning_rate": 0.001,
                "loss": "superres",
                "batch_size": 16,
                "time_budget": TIMEOUT,
                "model_type": "unet_large"
            }

            command_train = (
                "python train_model_landcover.py "
                "--output {output} "
                "--name {exp_name} "
                "--gpu {gpu} "
                "--verbose 2 "
                "--data_dir {data_dir} "
                "--training_states {train_state_list} "
                "--validation_states {val_state_list} "
                "--superres_states {superres_state_list} "
                "--model_type {model_type} "
                "--learning_rate {learning_rate} "
                "--loss {loss} "
                "--batch_size {batch_size} "
                "--time_budget {time_budget}"
            ).format(**args)
            jobs_per_gpu[gpu_idx].append((command_train, args))
            

            args = {
                "test_csv": "{}/{}_extended-test_tiles.csv".format(DATASET_DIR, test_state),
                "output": "{}/train-hr_{}_train-sr_{}/".format(OUTPUT_DIR, train_state, test_state),
                "exp_name": "test-output_{}".format(test_state),
                "gpu": gpu_id,
                "log_name": "log_test_{}.txt".format(test_state)
            }
            command_test = (
                "python test_model_landcover.py "
                "--input {test_csv} "
                "--output {output}/{exp_name}/ "
                "--model {output}/final_model.h5 "
                "--gpu {gpu} "
                "--superres"
            ).format(**args)
            jobs_per_gpu[gpu_idx].append((command_test, args))
            

            
            args = args.copy()
            args["log_name"] = "log_acc_{}.txt".format(test_state)
            command_acc = (
                "python compute_accuracy.py "
                "--input {test_csv} "
                "--output {output}/{exp_name}/"
            ).format(**args)
            jobs_per_gpu[gpu_idx].append((command_acc, args))


            gpu_idx = (gpu_idx + 1) % num_gpus
        else:
            print("Skipping %s-%s" % (train_state, test_state))


pool_sz = num_gpus
pool = multiprocessing.Pool(num_gpus + 1)
pool.map(run_jobs, jobs_per_gpu)
pool.close()
pool.join()
