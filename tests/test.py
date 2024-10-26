import os
import sys

# Add the parent directory to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
load_dotenv('.env')

#  LLM Client Tests
from lib.llm.LLMClient import ChatCompletionOptions, ChatMessage, MessageRole

from lib.llm.OpenAIClient import OpenAIClient
from lib.llm.AnthropicClient import AnthropicClient


user_prompt = ChatMessage(role=MessageRole.USER, content="How are you doing today?")

def test_openai_client():
    openai_completion_options = ChatCompletionOptions(model="gpt-4o", messages=[user_prompt])
    openai_client = OpenAIClient()

    response = openai_client.create_chat_completion(openai_completion_options)
    return response

def test_anthropic_client():
    anthropic_completion_options = ChatCompletionOptions(model="claude-3-5-sonnet-latest", messages=[user_prompt])
    anthropic_client = AnthropicClient()

    response = anthropic_client.create_chat_completion(anthropic_completion_options)
    return response

print(test_openai_client())