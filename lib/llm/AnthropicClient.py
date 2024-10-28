import os
import json
import base64
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from openai.types import CompletionUsage
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function

from anthropic import Anthropic, NotGiven
from anthropic.types import TextBlock

from utils.logger import get_default_logger
from utils.utils import get_json_response_format

from .LLMClient import LLMClient, ChatCompletionOptions, ChatMessage


class AnthropicClient(LLMClient):
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.logger = logger if logger else get_default_logger("AnthropicClient")

    def create_chat_completion(self, options: ChatCompletionOptions) -> Dict[str, Any]:
        system_message = next((msg for msg in options.messages if msg.role == "system"), None)
        user_messages = [msg for msg in options.messages if msg.role != "system"]
        
        self.logger.info(f"Creating chat completion with options: {json.dumps(options.model_dump(exclude={'response_model', 'image'}))}")

        if options.image:
            screenshot_message = {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(options.image.buffer).decode()
                        }
                    }
                ]
            }
            if options.image.description:
                screenshot_message["content"].append({"type": "text", "text": options.image.description})
            user_messages.append(screenshot_message)

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
            response_format = get_json_response_format(
                options.response_model.schema,
                options.response_model.name
            )
            json_schema = response_format["json_schema"]

            schema_properties = json_schema["schema"]["properties"]
            schema_required = json_schema["schema"]["required"]

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
            messages=[{"role": msg.role, "content": msg.content} if isinstance(msg, ChatMessage) else msg for msg in user_messages],
            tools=anthropic_tools if anthropic_tools else NotGiven(),
            system=system_message.content if system_message else NotGiven(),
            temperature=options.temperature if options.temperature is not None else NotGiven()
        )

        # Anthropic uses different values for their "finish reasons" than OpenAI, so to convert to the OpenAI types, we need to convert the reason
        anthropic_to_openai_stop_reason_map = {
            "max_tokens": "length",
            "tool_use": "tool_calls"
        }

        transformed_response = ChatCompletion(
            id=response.id,
            object="chat.completion",
            created=int(datetime.now().timestamp()),
            model=response.model,
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=next((c.text for c in response.content if isinstance(c, TextBlock)), None),
                        tool_calls=[
                            ChatCompletionMessageToolCall(
                                id=c.id,
                                type="function",
                                function=Function(
                                    name=c.name,
                                    arguments=json.dumps(c.input)
                                )
                            ) for c in response.content if hasattr(c, 'type') and c.type == "tool_use"
                        ]
                    ),
                    finish_reason=anthropic_to_openai_stop_reason_map.get(response.stop_reason, "stop")
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens
            )
        )

        self.logger.debug(f"Transformed response: {transformed_response.model_dump()}")

        if options.response_model:
            tool_use = next((c for c in response.content if c.type == "tool_use"), None)
            if tool_use and hasattr(tool_use, 'input'):
                return tool_use.input

        return transformed_response
