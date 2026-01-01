from typing import Tuple

import requests
import uuid

REASONING_MODELS = ["o1", "o3", "o4"]
EXTENDED_THINKING_SUFFIX = "-extended-thinking"

# Authentication helpers


## Bulk providers
def _auth_helm_api_key(
    api_key: str, model_name: str = None, verify_model: bool = False
) -> Tuple[bool, str]:
    auth_url = f"https://crfm-models.stanford.edu/api/account?auth=%7B%22api_key%22%3A%22{api_key}%22%7D"
    response = requests.get(auth_url)
    if response.status_code == 200:
        if "error" in response.json():
            return False, response.json()["error"]

        if not verify_model or model_name is None:
            return True, ""

        model_url = "https://crfm-models.stanford.edu/api/general_info"
        response = requests.get(model_url)
        try:
            valid_models = [model["name"] for model in response.json()["all_models"]]
            if model_name not in valid_models:
                raise ValueError(
                    f"Model {model_name} not found.\n\nAvailable models from Helm: {valid_models}"
                )
            return True, ""
        except Exception as e:
            return False, str(e)

    return False, response.text


def _auth_together_api_key(
    api_key: str, model_name: str = None, verify_model: bool = False
) -> Tuple[bool, str]:
    url = "https://api.together.xyz/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            if not verify_model or model_name is None:
                return True, ""

            valid_models = [model["id"] for model in response.json()]

            if model_name not in valid_models:
                raise ValueError(
                    f"Model {model_name} not found.\n\nAvailable models from together.ai: {valid_models}"
                )
            return True, ""
        except Exception as e:
            return False, str(e)

    return False, response.text


## Individual providers
def _auth_openai_api_key(
    api_key: str, model_name: str = None, verify_model: bool = False
) -> Tuple[bool, str]:
    url = "https://api.openai.com/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        try:
            if not verify_model or model_name is None:
                return True, ""

            valid_models = [model["id"] for model in response.json()["data"]]

            model_id = model_name.split("/")[-1]

            # Strip -high-reasoning-effort or -low-reasoning-effort suffixes from openai reasoning models
            if any(model_id.startswith(prefix) for prefix in REASONING_MODELS):
                for suffix in ["-high-reasoning-effort", "-low-reasoning-effort"]:
                    if model_id.endswith(suffix):
                        model_id = model_id[: -len(suffix)]
                        break

            if model_id not in valid_models:
                error_msg = f"Model {model_name} not found.\n\nAvailable models from OpenAI: {valid_models}"
                raise ValueError(error_msg)

            return True, ""
        except Exception as e:
            return False, str(e)

    return False, response.text


def _auth_anthropic_api_key(
    api_key: str, model_name: str = None, verify_model: bool = False
) -> Tuple[bool, str]:
    # Remove custom "-extended-thinking" suffix from model names
    if model_name and model_name.endswith(EXTENDED_THINKING_SUFFIX):
        model_name = model_name[: -len(EXTENDED_THINKING_SUFFIX)]

    url = "https://api.anthropic.com/v1/models"
    headers = {"x-api-key": f"{api_key}", "anthropic-version": "2023-06-01"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            if not verify_model or model_name is None:
                return True, ""

            valid_models = [model["id"] for model in response.json()["data"]]

            if model_name.split("/")[-1] not in valid_models:
                raise ValueError(
                    f"Model {model_name} not found.\n\nAvailable models from Anthropic: {valid_models}"
                )

            return True, ""
        except Exception as e:
            return False, str(e)

    return False, response.text


def _auth_google_api_key(
    api_key: str, model_name: str = None, verify_model: bool = False
) -> Tuple[bool, str]:
    url = "https://generativelanguage.googleapis.com/v1/models"
    params = {"key": api_key}

    response = requests.get(url, params=params)
    if response.status_code == 200:
        try:
            if not verify_model or model_name is None:
                return True, ""

            valid_models = [
                model["name"].split("/")[-1] for model in response.json()["models"]
            ]

            if model_name.split("/")[-1] not in valid_models:
                raise ValueError(
                    f"Model {model_name} not found.\n\nAvailable models from Google: {valid_models}"
                )
            return True, ""
        except Exception as e:
            return False, str(e)

    return False, response.text


def _auth_xai_api_key(
    api_key: str, model_name: str = None, verify_model: bool = False
) -> Tuple[bool, str]:
    url = "https://api.x.ai/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    model_name = model_name.split("/")[-1] if model_name else None

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            if not verify_model or model_name is None:
                return True, ""

            valid_models = [model["id"] for model in response.json()["data"]]

            if model_name not in valid_models:
                raise ValueError(
                    f"Model {model_name} not found.\n\nAvailable models from X.ai: {valid_models}"
                )
            return True, ""
        except Exception as e:
            return False, str(e)

    return False, response.text

def _auth_openrouter_api_key(
    api_key: str, model_name: str = None, verify_model: bool = False) -> Tuple[bool, str]:
    # OpenRouter's models endpoint
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        try:
            if not verify_model or model_name is None:
                return True, ""

            # Get list of available models
            models_data = response.json()["data"]
            valid_models = [model["id"] for model in models_data]

            # Extract the actual model ID from the full path
            # e.g., "openrouter/anthropic/claude-3-5-sonnet-20241022" -> "anthropic/claude-3-5-sonnet-20241022"
            model_id = "/".join(model_name.split("/")[1:])

            if model_id not in valid_models:
                error_msg = (
                    f"Model {model_name} not found.\n\n"
                    f"Available models from OpenRouter: {valid_models[:10]}... "
                    f"(showing first 10 of {len(valid_models)} models)\n\n"
                    f"Visit https://openrouter.ai/models for the full list."
                )
                raise ValueError(error_msg)

            return True, ""
        except Exception as e:
            return False, str(e)

    # Handle authentication errors
    if response.status_code == 401:
        return False, "Invalid OpenRouter API key"
    elif response.status_code == 403:
        return False, "OpenRouter API key does not have permission to access models"
    
    return False, response.text

def _auth_casi_api_key(
    api_key: str, model_name: str = None, verify_model: bool = False) -> Tuple[bool, str]:
    if not api_key:
        return False, "API key is required"
    if not api_key.startswith("rt_"):
        return False, "API key must start with 'rt_'"
    parts = api_key.split("_", 2)
    if len(parts) < 3:
        return False, "API key format invalid. Expected format: rt_<user_id>_sk-or-..."
    
    if not parts[2].startswith("sk-or-"):
        return False, "OpenRouter key portion must start with 'sk-or-'"
    return True, ""