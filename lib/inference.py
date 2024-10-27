from typing import Optional, Any, Dict
from pydantic import BaseModel

from .prompt import (
    act_tools,
    build_act_system_prompt,
    build_act_user_prompt,
    build_ask_system_prompt,
    build_extract_system_prompt,
    build_extract_user_prompt,
    build_observe_system_prompt,
    build_observe_user_message,
    build_ask_user_prompt,
    build_verify_act_completion_system_prompt,
    build_verify_act_completion_user_prompt,
    build_refine_system_prompt,
    build_refine_user_prompt,
    build_metadata_system_prompt,
    build_metadata_prompt,
)

from .llm import LLMProvider, AnnotatedScreenshotText
from ..utils.logger import get_default_logger


def verify_act_completion(
    goal: str,
    steps: str,
    llm_provider: LLMProvider,
    model_name: str,
    screenshot: Optional[bytes] = None,
    dom_elements: Optional[str] = None,
    logger: Optional[callable] = get_default_logger("stagehand.inference")
) -> bool:
    llm_client = llm_provider.get_client(model_name)
    messages = [
        build_verify_act_completion_system_prompt(),
        build_verify_act_completion_user_prompt(goal, steps, dom_elements)
    ]

    # Define response model using Pydantic
    class Verification(BaseModel):
        completed: bool = False

    response = llm_client.create_chat_completion(
        model=model_name,
        messages=messages,
        temperature=0.1,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        image={
            "buffer": screenshot,
            "description": "This is a screenshot of the whole visible page."
        } if screenshot else None,
        response_model=Verification
    )

    if not response or not isinstance(response, dict):
        logger.error(f"Unexpected response format: {response}")
        return False

    if "completed" not in response:
        logger.error("Missing 'completed' field in response")
        return False

    return response["completed"]

def act(
    action: str,
    dom_elements: str,
    steps: Optional[str],
    llm_provider: LLMProvider,
    model_name: str,
    screenshot: Optional[bytes] = None,
    retries: int = 0,
    logger: Optional[callable] = get_default_logger("stagehand.inference")
) -> Optional[Dict]:
    llm_client = llm_provider.get_client(model_name)
    messages = [
        build_act_system_prompt(),
        build_act_user_prompt(action, steps, dom_elements)
    ]

    response = llm_client.create_chat_completion(
        model=model_name,
        messages=messages,
        temperature=0.1,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        tool_choice="auto",
        tools=act_tools,
        image={"buffer": screenshot, "description": AnnotatedScreenshotText} if screenshot else None
    )

    tool_calls = response.choices[0].message.tool_calls
    if tool_calls and len(tool_calls) > 0:
        if tool_calls[0].function.name == "skipSection":
            return None
        return tool_calls[0].function.arguments
    else:
        if retries >= 2:
            logger.error("No tool calls found in response")
            return None

        return act(
            action=action,
            dom_elements=dom_elements,
            steps=steps,
            llm_provider=llm_provider,
            model_name=model_name,
            retries=retries + 1,
            logger=logger
        )

def extract(
    instruction: str,
    progress: str,
    previously_extracted_content: Any,
    dom_elements: str,
    schema: BaseModel,
    llm_provider: LLMProvider,
    model_name: str,
    chunks_seen: int,
    chunks_total: int
) -> Dict:
    llm_client = llm_provider.get_client(model_name)

    extraction_response = llm_client.create_extraction(
        model=model_name,
        messages=[
            build_extract_system_prompt(),
            build_extract_user_prompt(instruction, dom_elements)
        ],
        response_model=schema,
        temperature=0.1,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    refined_response = llm_client.create_extraction(
        model=model_name,
        messages=[
            build_refine_system_prompt(),
            build_refine_user_prompt(
                instruction,
                previously_extracted_content,
                extraction_response
            )
        ],
        response_model=schema,
        temperature=0.1,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    class MetadataSchema(BaseModel):
        progress: str
        completed: bool

    metadata_response = llm_client.create_extraction(
        model=model_name,
        messages=[
            build_metadata_system_prompt(),
            build_metadata_prompt(
                instruction,
                refined_response,
                chunks_seen,
                chunks_total
            )
        ],
        response_model=MetadataSchema,
        temperature=0.1,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    refined_response["metadata"] = metadata_response
    return refined_response

def observe(
    observation: str,
    dom_elements: str,
    llm_provider: LLMProvider,
    model_name: str
) -> str:
    llm_client = llm_provider.get_client(model_name)
    observation_response = llm_client.create_chat_completion(
        model=model_name,
        messages=[
            build_observe_system_prompt(),
            build_observe_user_message(observation, dom_elements)
        ],
        temperature=0.1,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    element_id = observation_response.choices[0].message.content

    if not element_id:
        raise Exception("no response when finding a selector")

    return element_id

def ask(
    question: str,
    llm_provider: LLMProvider,
    model_name: str
) -> str:
    llm_client = llm_provider.get_client(model_name)
    response = llm_client.create_chat_completion(
        model=model_name,
        messages=[
            build_ask_system_prompt(),
            build_ask_user_prompt(question)
        ],
        temperature=0.1,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    return response.choices[0].message.content