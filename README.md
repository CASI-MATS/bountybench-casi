# BountyBench CASI Parallel Task Mining
This README walks you through task mining with BountyBench using AWS EC2 instances.

Follow these instructions precisely to achieve best results.

## EC2 Setup
Go to the AWS Console, and launch a new EC2 instance with the following specifications.
- Ubuntu Linux, with default AMI
- Change the Architecture to **64-bit (Arm)**
- Select an Instance Type with at least as much CPU as possible (i.e., c6g.4xlarge)
- Create a `.pem` login key if you don't already have one
- Allow SSH, HTTPS, and HTTP traffic from anywhere
- Configure storage to at least 200GB of gp3

Store the your `.pem` key into your system's `~/.ssh/` folder. Launch the instance, get the IP address, and SSH onto the instance with the following command in a terminal.
```bash
ssh -i "~/.ssh/<key_name>.pem" -o StrictHostKeyChecking=no ubuntu@<ip>
```

## Instance Setup
Ensure that Python 3.11 is installed on the image. If this is not done correctly, the future `setup.sh` script will fail.
```bash
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1
sudo update-alternatives --set python /usr/bin/python3.11
python --version
```

Ensure that docker is installed on the image and enable it without `sudo`. This **must** be done for proper execution.
```bash
sudo apt-get update -qq
sudo apt-get install -y -qq git python3-pip python3-venv docker.io jq

sudo usermod -aG docker ubuntu
sg docker -c "echo docker group active" || true
```

Now, restart the image once to ensure that installation has completed correctly, and that Docker is able to run.

## Repository Setup
Clone the `bountybench-casi` repository to the image.
```bash
git clone https://github.com/CASI-MATS/bountybench-casi.git
cd bountybench-casi
```

Checkout the `arm-parallel` branch.
```bash
git checkout arm-parallel
```

Modify the `setup.sh` script to include the desired tasks, and only the desired jobs. This can be done through any editor, but we'll use `nano` as an example.
```
nano setup.sh
```

Scroll until you see the following, and remove any lines with tasks that you don't want to run. **Including too many tasks will slow down execution significantly and increase storage requirements.** The parallel running works by creating multiple copies of the repository, so initializing too many submodules (tasks) will increase compute. Limit task choice to 1-3 tasks at most.
```bash
TEST_SUBMODULES=(
            "yaml"
            "zipp"
            "kedro"
            "curl"
            "vllm"
            "astropy"
            "gluon-cv"
            "llama_index"
            "parse-url"
            "setuptools"
            "langchain"
            "scikit-learn"
        )
```

Run the following commands to set up the repository. **DO NOT include the `--all` flag.**
```bash
./setup.sh
source venv/bin/activate
```

Then, configure the `.env` file with the correct API keys.
```bash
nano .env

# Delete all boilerplate and paste in
OPENAI_API_KEY=sk-proj-v1-dummy
OPENROUTER_API_KEY=sk-or-v1-<openrouter_key>
```

## Job Configuration
The parallelization systems by temporarily cloning the base repository to run multiple Kali-Linux Docker containers at once and ensure minimal Git interference between runs. Configure a run using a `.yaml` file. An `example_parallel_config.yaml` is provided for your reference, and some important parameters are shown below.
```yaml
workflow_type: exploit_workflow  # change to desired workflow
trials_per_config: 5             # repeated runs per task / model pair

tasks:
  - task_dir: bountytasks/zipp   # add or remove jobs
    bounty_number: "0"
  - task_dir: bountytasks/curl
    bounty_number: "0"
  - task_dir: bountytasks/yaml
    bounty_number: "0"

models:
  - name: openrouter/moonshotai/kimi-k2-thinking   # add or remove models

phase_iterations: 100            # number of phase iterations (model is queried half as many times)
```

Run a parallel run using a command below. **ENSURE the virtual environment is ACTIVE**. You **MUST** run with `sudo`, this solves most of the permissions and docker issues that really hamper BountyBench operation.
```bash
sudo -E env PATH=$PATH python run_parallel.py <config_name>.yaml
sudo -E env PATH=$PATH python run_parallel.py <config_name>.yaml --max-parallel <jobs_parallel>

python run_parallel.py example_parallel_config.yaml --max-parallel 10
```

All logs are saved to the `bountybench-casi/parallel_logs/` directory. You can `scp` this directory and put it on your local device as below, from a local terminal.
```bash
scp -r -i "~/.ssh/<key_name>.pem" ubuntu@<ip>:/home/ubuntu/bountybench-casi/parallel_logs/ <local_path>
```

Before this, it may be useful to do some data preprocessing on the instance to make the data more workable. Do this with the commands below.
```bash
python data_analysis/collect_jsons.py ./parallel_logs/logs/ ./logs/
python data_analysis/data_analysis.py -i ./logs/ -o ./logs
```

You can then `scp` these logs to local. The `summary.json` file should contain metrics on 
```bash
scp -r -i "~/.ssh/<key_name>.pem" ubuntu@<ip>:/home/ubuntu/bountybench-casi/logs/ <local_path>
```

## Useful Commands
Here are some useful commands to use when SSHing and working with the instances. You can try `tmux` to safely close SSH connections while keeping jobs running and running monitoring commands.
```bash
# TMUX setup
tmux new -n bb

# Monitor storage, memory, and system monitoring
df -h
free -h
docker ps
htop

# Check logs
cd ./parallel_logs/stdout/
cd ./parallel_logs/stderr/
cat <file_name>
```