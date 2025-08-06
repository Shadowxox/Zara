import base64
from io import BytesIO
import config
import logging

import tiktoken
import openai

openai.api_key = config.openai_api_key
if config.openai_api_base:
    openai.api_base = config.openai_api_base

logger = logging.getLogger(__name__)

OPENAI_COMPLETION_OPTIONS = {
    "temperature": 0.7,
    "max_tokens": 1000,
    "top_p": 1,
    "frequency_penalty": 0,
    "presence_penalty": 0,
    "request_timeout": 60.0,
}

class ChatGPT:
    def __init__(self, model="gpt-3.5-turbo"):
        self.model = model

    async def send_message(self, message, dialog_messages=[]):
        answer = None
        while answer is None:
            try:
                messages = self._generate_prompt_messages(message, dialog_messages)
                r = await openai.ChatCompletion.acreate(
                    model=self.model,
                    messages=messages,
                    **OPENAI_COMPLETION_OPTIONS
                )
                answer = r.choices[0].message["content"]
                answer = self._postprocess_answer(answer)
                n_input_tokens, n_output_tokens = r.usage.prompt_tokens, r.usage.completion_tokens
            except openai.error.InvalidRequestError as e:
                if not dialog_messages:
                    raise ValueError("Too many tokens") from e
                dialog_messages = dialog_messages[1:]

        return answer, (n_input_tokens, n_output_tokens), 0

    def _generate_prompt_messages(self, message, dialog_messages, image_buffer: BytesIO = None):
        prompt = config.chat_modes["zara"]["prompt_start"]
        messages = [{"role": "system", "content": prompt}]

        for msg in dialog_messages:
            messages.append({"role": "user", "content": msg["user"]})
            messages.append({"role": "assistant", "content": msg["bot"]})

        if image_buffer:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{self._encode_image(image_buffer)}",
                        "detail": "high"
                    }}
                ]
            })
        else:
            messages.append({"role": "user", "content": message})

        return messages

    def _encode_image(self, image_buffer: BytesIO) -> str:
        return base64.b64encode(image_buffer.read()).decode("utf-8")

    def _postprocess_answer(self, answer):
        return answer.strip()

    def _count_tokens_from_messages(self, messages, answer, model="gpt-3.5-turbo"):
        encoding = tiktoken.encoding_for_model(model)
        tokens_per_message = 4 if model in ["gpt-3.5-turbo", "gpt-3.5-turbo-16k"] else 3

        n_input_tokens = sum(tokens_per_message + (
            len(encoding.encode(sub["text"])) if isinstance(m["content"], list)
            else len(encoding.encode(m["content"]))
        ) for m in messages for sub in (m["content"] if isinstance(m["content"], list) else [m]))

        n_input_tokens += 2
        n_output_tokens = 1 + len(encoding.encode(answer))
        return n_input_tokens, n_output_tokens
