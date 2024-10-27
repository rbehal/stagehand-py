import os
import json
import base64
import logging
from typing import Dict, Any, Optional

from openai import OpenAI, NOT_GIVEN

from utils.logger import get_default_logger
from utils.utils import get_json_response_format

from .LLMClient import LLMClient, ChatCompletionOptions, ExtractionOptions


class OpenAIClient(LLMClient):
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.logger = logger if logger else get_default_logger("OpenAIClient")

    def create_chat_completion(self, options: ChatCompletionOptions) -> Dict[str, Any]:
        self.logger.info(f"Creating chat completion with options: {json.dumps(options.model_dump(exclude={'response_model'}))}")

        if options.image:
            screenshot_message = {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64.b64encode(options.image.buffer).decode()}"
                        }
                    }
                ]
            }
            if options.image.description:
                screenshot_message["content"].append({"type": "text", "text": options.image.description})
            options.messages.append(screenshot_message)

        openai_options = options.model_dump(exclude={"image", "response_model"})

        response_format = None
        if options.response_model:
            response_format = get_json_response_format(
                options.response_model.schema,
                options.response_model.name
            )

        # Replace None values with NOT_GIVEN
        openai_options = {k: v if v is not None else NOT_GIVEN for k, v in openai_options.items()}
        response = self.client.chat.completions.create(
            **openai_options,
            response_format=response_format or NOT_GIVEN
        )

        self.logger.debug(f"Response from OpenAI: {response.model_dump_json()}")

        if options.response_model:
            extracted_data = response.choices[0].message.content
            self.logger.debug(f"Extracted data: {extracted_data}")

            parsed_data = json.loads(extracted_data)
            return parsed_data

        return response

    def create_extraction(self, options: ExtractionOptions) -> Dict[str, Any]:
        self.logger.info(f"Creating extraction with options: {json.dumps(options.dict())}")

        response_format = get_json_response_format(
            options.response_model.schema,
            options.response_model.name
        )

        completion = self.client.chat.completions.create(
            model=options.model,
            messages=[msg.dict() for msg in options.messages],
            response_format=response_format
        )

        extracted_data = completion.choices[0].message.content
        self.logger.debug(f"Extracted data: {extracted_data}")

        parsed_data = json.loads(extracted_data)
        return parsed_data
