import os
import json
import base64
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from anthropic import Anthropic, NotGiven
from anthropic.types import TextBlock

from utils.logger import get_default_logger

from .LLMClient import LLMClient, ChatCompletionOptions


class AnthropicClient(LLMClient):
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.logger = logger if logger else get_default_logger("AnthropicClient")

    def create_chat_completion(self, options: ChatCompletionOptions) -> Dict[str, Any]:
        system_message = next((msg for msg in options.messages if msg.role == "system"), None)
        user_messages = [msg for msg in options.messages if msg.role != "system"]
        
        self.logger.info(f"Creating chat completion with options: {json.dumps(options.dict())}")

        if options.image:
            screenshot_message = {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64.b64encode(options.image.buffer).decode()
                        }
                    }
                ]
            }
            if options.image.description:
                screenshot_message["content"].append({"type": "text", "text": options.image.description})
            options.messages.append(screenshot_message)

        anthropic_tools = []
        if options.tools:
            anthropic_tools = [
                {
                    "name": tool.function.name,
                    "description": tool.function.description,
                    "input_schema": {
                        "type": "object",
                        "properties": tool.function.parameters.properties,
                        "required": tool.function.parameters.required
                    }
                } if tool.type == "function" else tool
                for tool in options.tools
            ]

        if options.response_model:
            json_schema = options.response_model.schema.schema()
            schema_properties = json_schema.get("properties", {})
            schema_required = json_schema.get("required", [])

            tool_definition = {
                "name": "extract_data",
                "description": "Extracts specific data based on the provided schema.",
                "input_schema": {
                    "type": "object",
                    "properties": schema_properties,
                    "required": schema_required
                }
            }
            anthropic_tools.append(tool_definition)

        response = self.client.messages.create(
            model=options.model,
            max_tokens=options.max_tokens or 1500,
            messages=[{"role": msg.role, "content": msg.content} for msg in user_messages],
            tools=anthropic_tools if anthropic_tools else NotGiven(),
            system=system_message.content if system_message else NotGiven(),
            temperature=options.temperature if options.temperature is not None else NotGiven()
        )

        transformed_response = {
            "id": response.id,
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),  # Use current timestamp instead
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": next((c.text for c in response.content if isinstance(c, TextBlock)), None),
                        "tool_calls": [
                            {
                                "id": c.id,
                                "type": "function",
                                "function": {
                                    "name": c.name,
                                    "arguments": json.dumps(c.input)
                                }
                            } for c in response.content if hasattr(c, 'type') and c.type == "tool_calls"
                        ]
                    },
                    "finish_reason": response.stop_reason
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        }

        self.logger.debug(f"Transformed response: {json.dumps(transformed_response)}")

        if options.response_model:
            tool_use = next((c for c in response.content if c.type == "tool_use"), None)
            if tool_use and hasattr(tool_use, 'input'):
                return tool_use.input
            else:
                raise ValueError("Extraction failed: No tool use with input in response")

        return transformed_response
