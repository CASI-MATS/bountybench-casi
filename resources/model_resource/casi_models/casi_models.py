from datetime import datetime
from typing import List
import uuid
import re

import tiktoken
from openai import OpenAI

from resources.model_resource.model_provider import ModelProvider
from resources.model_resource.model_response import ModelResponse

EXTENDED_THINKING_SUFFIX = "-extended-thinking"
DEFAULT_THINKING_BUDGET = 1024


class CASIModels(ModelProvider):
    def __init__(self, variant: str = "v1"):
        self.variant = variant
        self.session_id = str(uuid.uuid4())
        self.client = self.create_client()

    def create_client(self) -> OpenAI:
        base_url = "http://98.91.36.205"
        if self.variant != "v0":
            full_base_url = f"{base_url}/{self.variant}/openrouter/v1"
        else:
            full_base_url = f"{base_url}/openrouter/v1"
        
        return OpenAI(
            base_url=full_base_url,
            api_key=self._api_key(),
            default_headers={
                "X-RedTeam-Session-ID": self.session_id,
            }
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

            if is_thinking:
                clean_model_name = clean_model_name[: -len(EXTENDED_THINKING_SUFFIX)]
                messages = [
                    {
                        "role": "system",
                        "content": "Think through your response step by step before answering. Show your reasoning process."
                    },
                    {"role": "user", "content": message}
                ]
            else:
                messages = [{"role": "user", "content": message}]

            print(f"[CASI DEBUG] About to make request - variant: {self.variant}, model: {clean_model_name}")

            response = self.client.chat.completions.create(
                model=clean_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop_sequences if stop_sequences else None,
            )

            print(f"[CASI DEBUG] Response type: {type(response)}")
            print(f"[CASI DEBUG] Response object: {response}")
            print(f"[CASI DEBUG] Has usage attr: {hasattr(response, 'usage')}")
            print(f"[CASI DEBUG] Usage value: {getattr(response, 'usage', 'NO ATTR')}")

            full_response = response.choices[0].message.content

            if hasattr(response, "_response") and hasattr(response._response, "status_code"):
                status_code = response._response.status_code

            if not hasattr(response, 'usage') or response.usage is None:
                print(f"[CASI] Warning: response.usage is missing or None")
                if hasattr(response, '_response'):
                    print(f"[CASI] Raw response: {response._response}")
                input_tokens = 0
                output_tokens = 0
            else:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens

            end_time = datetime.now()
            response_request_duration = (end_time - start_time).total_seconds() * 1000
            
            return ModelResponse(
                content=full_response,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                time_taken_in_ms=response_request_duration,
                status_code=status_code,
            )
        except Exception as e:
            print(f"[CASI] Request failed with exception: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"[CASI] Traceback: {traceback.format_exc()}")
            
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
        return re.sub(r"^casiv\d+/", "", model_name)

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