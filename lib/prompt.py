from pydantic import BaseModel
from typing import List, Optional

from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

# Models for function parameters
class DoActionParams(BaseModel):
    method: str
    element: int
    args: List[str]
    step: str
    why: Optional[str]
    completed: bool

class SkipSectionParams(BaseModel):
    reason: str

# System prompts
act_system_prompt = """
# Instructions
You are a browser automation assistant. Your job is to accomplish the user's goal across multiple model calls.

You are given:
1. the user's overall goal
2. the steps that you've taken so far
3. a list of active DOM elements in this chunk to consider to get closer to the goal. 

You have 2 tools that you can call: doAction, and skipSection. Do action only performs Playwright actions. Do not perform any other actions.

Note: If there is a popup on the page for cookies or advertising that has nothing to do with the goal, try to close it first before proceeding. As this can block the goal from being completed.

Also, verify if the goal has been accomplished already. Do this by checking if the goal has been accomplished based on the previous steps completed, the current page DOM elements and the current page URL / starting page URL. If it has, set completed to true and finish the task.

Do exactly what the user's goal is. Do not exceed the scope of the goal.
"""

verify_act_completion_system_prompt = """
You are a browser automation assistant. The job has given you a goal and a list of steps that have been taken so far. Your job is to determine if the user's goal has been completed based on the provided information.

# Input
You will receive:
1. The user's goal: A clear description of what the user wants to achieve.
2. Steps taken so far: A list of actions that have been performed up to this point.
3. An image of the current page

# Your Task
Analyze the provided information to determine if the user's goal has been fully completed.

# Output
Return a boolean value:
- true: If the goal has been definitively completed based on the steps taken and the current page.
- false: If the goal has not been completed or if there's any uncertainty about its completion.

# Important Considerations
- False positives are okay. False negatives are not okay.
- Look for evidence of errors on the page or something having gone wrong in completing the goal. If one does not exist, return true.
"""

# Function definitions
def build_verify_act_completion_system_prompt() -> ChatCompletionMessageParam:
    return {
        "role": "system",
        "content": verify_act_completion_system_prompt
    }

def build_verify_act_completion_user_prompt(
    goal: str,
    steps: str = "None",
    dom_elements: Optional[str] = None
) -> ChatCompletionMessageParam:
    act_user_prompt = f"""
# My Goal
{goal}

# Steps You've Taken So Far
{steps}
"""
    
    if dom_elements:
        act_user_prompt += f"""
# Active DOM Elements on the current page
{dom_elements}
"""

    return {
        "role": "user",
        "content": act_user_prompt
    }

def build_act_system_prompt() -> ChatCompletionMessageParam:
    return {
        "role": "system",
        "content": act_system_prompt
    }

def build_act_user_prompt(
    action: str,
    dom_elements: str,
    steps: str = "None",
) -> ChatCompletionMessageParam:
    act_user_prompt = f"""
# My Goal
{action}

# Steps You've Taken So Far
{steps}

# Current Active Dom Elements
{dom_elements}
"""

    return {
        "role": "user",
        "content": act_user_prompt
    }

# Tools configuration
act_tools: List[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "doAction",
            "description": "execute the next playwright step that directly accomplishes the goal",
            "parameters": DoActionParams.model_json_schema()
        }
    },
    {
        "type": "function",
        "function": {
            "name": "skipSection",
            "description": "skips this area of the webpage because the current goal cannot be accomplished here",
            "parameters": SkipSectionParams.model_json_schema()
        }
    }
]

# Extract related prompts and functions
extract_system_prompt = """You are extracting content on behalf of a user. You will be given:
1. An instruction
2. A list of DOM elements to extract from

Return the exact text from the DOM elements with all symbols, characters, and endlines as is.
Only extract new information that has not already been extracted. Return null or an empty string if no new information is found."""

def build_extract_system_prompt() -> ChatCompletionMessageParam:
    return {
        "role": "system",
        "content": extract_system_prompt.replace('\s+', ' ')
    }

def build_extract_user_prompt(
    instruction: str,
    dom_elements: str
) -> ChatCompletionMessageParam:
    return {
        "role": "user",
        "content": f"Instruction: {instruction}\n    DOM: {dom_elements}\n    Extracted content:"
    }

# Refine related prompts
refine_system_prompt = """You are tasked with refining and filtering information for the final output based on newly extracted and previously extracted content. Your responsibilities are:
1. Remove exact duplicates for elements in arrays and objects.
2. For text fields, append or update relevant text if the new content is an extension, replacement, or continuation.
3. For non-text fields (e.g., numbers, booleans), update with new values if they differ.
4. Add any completely new fields or objects.

Return the updated content that includes both the previous content and the new, non-duplicate, or extended information."""

def build_refine_system_prompt() -> ChatCompletionMessageParam:
    return {
        "role": "system",
        "content": refine_system_prompt
    }

def build_refine_user_prompt(
    instruction: str,
    previously_extracted_content: dict,
    newly_extracted_content: dict
) -> ChatCompletionMessageParam:
    return {
        "role": "user",
        "content": f"""Instruction: {instruction}
Previously extracted content: {previously_extracted_content}
Newly extracted content: {newly_extracted_content}
Refined content:"""
    }

# Metadata related prompts
metadata_system_prompt = """You are an AI assistant tasked with evaluating the progress and completion status of an extraction task.
Analyze the extraction response and determine if the task is completed or if more information is needed.

Strictly abide by the following criteria:
1. If you are certain that the instruction is completed, set the completion status to true, even if there are still chunks left.
2. If there could still be more information to extract and there are still chunks left, set the completion status to false."""

def build_metadata_system_prompt() -> ChatCompletionMessageParam:
    return {
        "role": "system",
        "content": metadata_system_prompt
    }

def build_metadata_prompt(
    instruction: str,
    extraction_response: dict,
    chunks_seen: int,
    chunks_total: int
) -> ChatCompletionMessageParam:
    return {
        "role": "user",
        "content": f"""Instruction: {instruction}
Extracted content: {extraction_response}
Chunks seen: {chunks_seen}
Chunks total: {chunks_total}"""
    }

# Observe related prompts
observe_system_prompt = """
You are helping the user automate the browser by finding a playwright locator string. You will be given a instruction of the element to find, and a numbered list of possible elements.

return only element id we are looking for.

if the element is not found, return NONE.
"""

def build_observe_system_prompt() -> ChatCompletionMessageParam:
    return {
        "role": "system",
        "content": observe_system_prompt.replace('\s+', ' ')
    }

def build_observe_user_message(
    observation: str,
    dom_elements: str
) -> ChatCompletionMessageParam:
    return {
        "role": "user",
        "content": f"instruction: {observation}\n    DOM: {dom_elements}"
    }

# Ask related prompts
ask_system_prompt = """
you are a simple question answering assistent given the user's question. respond with only the answer.
"""

def build_ask_system_prompt() -> ChatCompletionMessageParam:
    return {
        "role": "system",
        "content": ask_system_prompt
    }

def build_ask_user_prompt(question: str) -> ChatCompletionMessageParam:
    return {
        "role": "user",
        "content": f"question: {question}"
    }
