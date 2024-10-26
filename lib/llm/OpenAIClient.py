import json
import base64
from typing import Dict, Any, Callable
from openai import OpenAI
from pydantic import BaseModel
from .LLMClient import LLMClient, ChatCompletionOptions, ExtractionOptions

def get_json_response_format(schema: BaseModel, name: str) -> Dict[str, Any]:
    return {
        "type": "json_object",
        "schema": schema.model_json_schema()
    }

class OpenAIClient(LLMClient):
    def __init__(self, logger: Callable[[Dict[str, str]], None]):
        self.client = OpenAI()
        self.logger = logger

    async def create_chat_completion(self, options: ChatCompletionOptions) -> Dict[str, Any]:
        self.logger({
            "category": "OpenAI",
            "message": f"Creating chat completion with options: {json.dumps(options.dict())}",
            "level": 1
        })

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

        openai_options = options.dict(exclude={"image", "response_model"})

        response_format = None
        if options.response_model:
            response_format = get_json_response_format(
                options.response_model.schema,
                options.response_model.name
            )

        response = await self.client.chat.completions.create(
            **openai_options,
            response_format=response_format
        )

        self.logger({
            "category": "OpenAI",
            "message": f"Response from OpenAI: {json.dumps(response)}",
            "level": 2
        })

        if options.response_model:
            extracted_data = response.choices[0].message.content
            self.logger({
                "category": "OpenAI",
                "message": f"Extracted data: {extracted_data}",
                "level": 2
            })

            parsed_data = json.loads(extracted_data)
            return parsed_data

        return response

    async def create_extraction(self, options: ExtractionOptions) -> Dict[str, Any]:
        self.logger({
            "category": "OpenAI",
            "message": f"Creating extraction with options: {json.dumps(options.dict())}",
            "level": 1
        })

        response_format = get_json_response_format(
            options.response_model.schema,
            options.response_model.name
        )

        completion = await self.client.chat.completions.create(
            model=options.model,
            messages=[msg.dict() for msg in options.messages],
            response_format=response_format
        )

        extracted_data = completion.choices[0].message.content
        self.logger({
            "category": "OpenAI",
            "message": f"Extracted data: {extracted_data}",
            "level": 2
        })

        parsed_data = json.loads(extracted_data)
        return parsed_data