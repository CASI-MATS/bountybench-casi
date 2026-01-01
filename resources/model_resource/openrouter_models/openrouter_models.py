from datetime import datetime
from typing import List

import tiktoken
from openai import OpenAI

from resources.model_resource.model_provider import ModelProvider
from resources.model_resource.model_response import ModelResponse

EXTENDED_THINKING_SUFFIX = "-extended-thinking"
DEFAULT_THINKING_BUDGET = 1024


class OpenRouterModels(ModelProvider):
    def __init__(self):
        self.client = self.create_client()

    def create_client(self) -> OpenAI:
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self._api_key(),
        )

    def request(
        self,
        model: str,
        message: str,
        temperature: float,
        max_tokens: int,
        stop_sequences: List[str],
    ) -> ModelResponse:
        start_time = datetime.now()
        status_code = None

        try:
            clean_model_name = self.clean_model_name(model)
            is_thinking: bool = clean_model_name.endswith(EXTENDED_THINKING_SUFFIX)
            
            # OpenRouter uses OpenAI-compatible API
            # Extended thinking is not directly supported through OpenRouter
            # You would need to handle it at the prompt level
            if is_thinking:
                clean_model_name = clean_model_name[: -len(EXTENDED_THINKING_SUFFIX)]
                # Add thinking instructions to the system message
                messages = [
                    {
                        "role": "system",
                        "content": "Think through your response step by step before answering. Show your reasoning process."
                    },
                    {"role": "user", "content": message}
                ]
            else:
                messages = [{"role": "user", "content": message}]

            response = self.client.chat.completions.create(
                model=clean_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop_sequences if stop_sequences else None,
            )

            full_response = response.choices[0].message.content

            # Extract status code if available
            if hasattr(response, "_response") and hasattr(response._response, "status_code"):
                status_code = response._response.status_code

            end_time = datetime.now()
            response_request_duration = (end_time - start_time).total_seconds() * 1000
            
            return ModelResponse(
                content=full_response,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                time_taken_in_ms=response_request_duration,
                status_code=status_code,
            )
        except Exception as e:
            # Extract status code from OpenAI/OpenRouter errors
            try:
                if hasattr(e, "status_code"):
                    status_code = e.status_code
                elif hasattr(e, "response") and hasattr(e.response, "status_code"):
                    status_code = e.response.status_code
            except:
                pass

            if status_code is not None:
                e.status_code = status_code
            raise

    def clean_model_name(self, model_name: str) -> str:
        prefix = "openrouter/"
        if model_name.startswith(prefix):
            return model_name[len(prefix) :]
        return model_name

    def tokenize(self, model: str, message: str) -> List[int]:
        # Use tiktoken for rough estimate
        encoding = tiktoken.encoding_for_model("gpt-4o")
        return encoding.encode(message)

    def decode(self, model: str, tokens: List[int]) -> str:
        # Use tiktoken for rough estimate
        encoding = tiktoken.encoding_for_model("gpt-4o")
        return encoding.decode(tokens)

    def get_num_tokens(self, model: str, message: str) -> int:
        encoding = tiktoken.encoding_for_model("gpt-4o")
        return len(encoding.encode(message))