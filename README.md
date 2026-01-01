# BountyBench (CASI Modified)

## Installation
This should proceed exactly as the original BountyBench setup goes. Look at the original repository for everything, but following the steps below should at least let you manually set up correctly on WSL with Ubuntu with Administrator access.

#### 1. Ensure Python 3.11 is Installed

Verify that Python 3.11 is available on your system:

```bash
python3.11 --version
```

#### 2. Create a Virtual Environment

Set up a virtual environment to isolate dependencies:

```bash
python3.11 -m venv venv
```

#### 3. Activate and Set Up the Environment

Activate the virtual environment, install required dependencies (may take several minutes to tens of minutes to complete, please leave time for this installation):

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Initialize submodules (may take a few minutes to complete):

```bash
git submodule update --init
git submodule update --remote
cd bountytasks
git submodule update --init
```

Additionally, please install `tree`:

macOS (using Homebrew):

```bash
brew install tree
```

or Debian/Ubuntu (using APT):

```bash
sudo apt-get install tree
```

#### 4. Configure the .env File

Create and populate an .env file in `bountybench/` with the following keys:

```bash
ANTHROPIC_API_KEY={ANTHROPIC_API_KEY}
AZURE_OPENAI_API_KEY={AZURE_OPENAI_API_KEY}
AZURE_OPENAI_ENDPOINT={AZURE_OPENAI_ENDPOINT}
GOOGLE_API_KEY={GOOGLE_API_KEY}
HELM_API_KEY={HELM_API_KEY}
OPENAI_API_KEY={OPENAI_API_KEY}
TOGETHER_API_KEY={TOGETHER_API_KEY}
XAI_API_KEY={XAI_API_KEY}

# These two are most important!
OPENROUTER_API_KEY={OPENROUTER_API_KEY}
CASI_API_KEY={CASI_API_KEY}
```

Replace {KEY_NAME} with your actual API key values (make sure you don't include {} when adding the key, e.g. KEY=sk-proj...). You only need to fill in whichever keys you will use. **Make sure that for the CASI_API_KEY, that you include `rt_<user_id>_sk-or...`.**

#### 5. Setup Docker Desktop App

Make sure that you have started up your Docker Desktop App before proceeding with running a workflow.

##### Docker Setup

To get started with Docker, follow these installation instructions based on your operating system:

- **[Docker Desktop Installation for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)**
- **[Docker Desktop Installation for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)**

 **Verify Installation**  

- Open a terminal or command prompt and run the following command:  

     ```bash
     docker --version
     ```  

- Ensure Docker is installed and the version is displayed.

###### Ensure your Docker Desktop has proper sharing permissions

You want to ensure that Docker Desktop has mounting permissions for your current working directory. Run:
`docker run --rm -v "$(pwd)":/test alpine ls /test`
It should list the contents of your current working directory. If you encounter a mounting issue, please follow [Docker Mount Issue](#docker-mount-issue) for next steps.

## Usage

### Running Workflows

Make sure your Docker Desktop app is running.

Running workflows from CLI should use `runner.py` module. Each runnable workflow defines required and optional arguments. Important parameter interactions:

- `--model` and `--use_mock_model` are mutually exclusive. You cannot specify both simultaneously.
- If `--use_mock_model` is True, then `--use_helm` parameter is ignored
- The `--use_helm` parameter determines whether to use Helm as the model provider

```bash
python -m workflows.runner --workflow-type WORKFLOW_TYPE [OPTIONS]
```

Available workflow types:
- `detect_workflow`:
- `exploit_workflow`:
- `patch_workflow`:

Required flags vary by workflow type.

Examples:

1. **Detect Workflow**:
```bash
python -m workflows.runner --workflow-type detect_workflow \
    --task_dir bountytasks/lunary \
    --bounty_number 0 \
    --model anthropic/claude-3-5-sonnet-20241022 \
    --phase_iterations 3
```

2. **Exploit Workflow**:
```bash
python -m workflows.runner --workflow-type exploit_workflow \
    --task_dir bountytasks/django \
    --bounty_number 0 \
    --model anthropic/claude-3-sonnet-20240229 \
    --phase_iterations 2 \
    --use_helm
```

3. **Patch Workflow**:
```bash
python -m workflows.runner --workflow-type patch_workflow \
    --task_dir bountytasks/mlflow \
    --bounty_number 1 \
    --use_mock_model \
    --phase_iterations 5
```

Please be aware that there may be a brief delay between initiating the workflow and observing the first log outputs (typically a few seconds). This initial pause is primarily due to the time required for importing necessary Python packages and initializing the environment.

## Notes and Changes

### OpenRouter and CASI Functions
Use `openrouter/<model_provider>/<model_name>` to call an OpenRouter model.

Use `casiv<n>/<model_provider>/<model_name>` to call CASI API, replacing `<n>` with the version number 0, 1, 2.

All models on OpenRouter should be supported, although some may perform better than others. The CASI OpenAI and Anthropic APIs are not supported, everything must go through OpenRouter for now. 

### Quick Testing
A detect workflow script is setup with `run_detect_workflow.sh`, and should be able to be run directly on the `kedro` task. This will use the CASI v2 API.

You should expect some error along the lines of `"success" not found`, since the model is highly restricted on how many turns it has and detect is the most difficult bountybench category.

For CASI v0 and v1 APIs, there is a good chance that you can fail immediately (look at the debug terminal printout, there should be something along the lines of "you lost...") due to the CASI endpoint detecting adversarial intent (this happened for `gpt-4o-mini` on `kedro` at least). To fix a full lockout on v1, you can reset the endpoint using the web UI, then try again.

### Troubleshooting
If during setup there is privilege restriction, using `sudo` on Linux/WSL may fix the problem.

If quick testing fails due to some type of git commit issue, go to the `bountytasks/kedro/setup_repo_env.sh` file, and add the lines:
```
git config --global user.name "BountyBench Agent"
git config --global user.email "agent@localhost"
```
This can fix certain issues where the docker image is new and does not know what the Git users are, and thus providing a dummy fixes the error.