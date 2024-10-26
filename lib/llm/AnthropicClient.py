import os
from typing import Dict, Any, Callable
import json
import base64
from anthropic import Anthropic
from .LLMClient import LLMClient, ChatCompletionOptions, ExtractionOptions

class AnthropicClient(LLMClient):
    def __init__(self, logger: Callable[[Dict[str, str]], None]):
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.logger = logger

    async def create_chat_completion(self, options: ChatCompletionOptions) -> Dict[str, Any]:
        system_message = next((msg for msg in options.messages if msg.role == "system"), None)
        user_messages = [msg for msg in options.messages if msg.role != "system"]
        
        self.logger({
            "category": "Anthropic",
            "message": f"Creating chat completion with options: {json.dumps(options.dict())}"
        })

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

        response = await self.client.messages.create(
            model=options.model,
            max_tokens=options.max_tokens or 1500,
            messages=[{"role": msg.role, "content": msg.content} for msg in user_messages],
            tools=anthropic_tools,
            system=system_message.content if system_message else None,
            temperature=options.temperature
        )

        transformed_response = {
            "id": response.id,
            "object": "chat.completion",
            "created": int(response.created_at.timestamp()),
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": next((c.text for c in response.content if c.type == "text"), None),
                        "tool_calls": [
                            {
                                "id": c.id,
                                "type": "function",
                                "function": {
                                    "name": c.name,
                                    "arguments": json.dumps(c.input)
                                }
                            } for c in response.content if c.type == "tool_use"
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

        self.logger({
            "category": "Anthropic",
            "message": f"Transformed response: {json.dumps(transformed_response)}"
        })

        if options.response_model:
            tool_use = next((c for c in response.content if c.type == "tool_use"), None)
            if tool_use and hasattr(tool_use, 'input'):
                return tool_use.input
            else:
                raise ValueError("Extraction failed: No tool use with input in response")

        return transformed_response

    async def create_extraction(self, options: ExtractionOptions) -> Dict[str, Any]:
        self.logger({
            "category": "Anthropic",
            "message": f"Creating extraction with options: {json.dumps(options.dict())}",
            "level": 2
        })

        json_schema = options.response_model.schema.schema()
        schema_properties = json_schema.get("properties", {})
        schema_required = json_schema.get("required", [])

        tool_definition = {
            "name": "extract_data",
            "description": "Extracts specific data from the given content based on the provided schema.",
            "input_schema": {
                "type": "object",
                "properties": schema_properties,
                "required": schema_required
            }
        }

        system_message = next((msg for msg in options.messages if msg.role == "system"), None)
        user_messages = [msg for msg in options.messages if msg.role != "system"]

        response = await self.client.messages.create(
            model=options.model or "claude-3-opus-20240229",
            max_tokens=options.max_tokens or 1000,
            messages=[{"role": msg.role, "content": msg.content} for msg in user_messages],
            system=system_message.content if system_message else "You are an AI assistant capable of extracting structured data from text.",
            temperature=options.temperature or 0.1,
            tools=[tool_definition]
        )

        self.logger({
            "category": "Anthropic",
            "message": f"Response from Anthropic: {json.dumps(response.dict())}",
            "level": 2
        })

        tool_use = next((c for c in response.content if c.type == "tool_use"), None)
        if tool_use and hasattr(tool_use, 'input'):
            extracted_data = tool_use.input
            self.logger({
                "category": "Anthropic",
                "message": f"Extracted data: {json.dumps(extracted_data)}",
                "level": 2
            })
            return extracted_data
        else:
            raise ValueError("Extraction failed: No tool use with input in response")
