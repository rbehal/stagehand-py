from typing import List, Union, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class ContentType(str, Enum):
    IMAGE_URL = "image_url"
    TEXT = "text"

class ImageUrl(BaseModel):
    url: str

class ContentItem(BaseModel):
    type: ContentType
    image_url: Optional[ImageUrl] = None
    text: Optional[str] = None

class ChatMessage(BaseModel):
    role: MessageRole
    content: Union[str, List[ContentItem]]

models_with_vision = [
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-5-sonnet-20240620",
    "gpt-4o-2024-08-06",
]

ANNOTATED_SCREENSHOT_TEXT = "This is a screenshot of the current page state with the elements annotated on it. Each element id is annotated with a number to the top left of it. Duplicate annotations at the same location are under each other vertically."

class Image(BaseModel):
    buffer: bytes
    description: Optional[str] = None

class ResponseModel(BaseModel):
    name: str
    schema: Any

class ChatCompletionOptions(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    image: Optional[Image] = None
    response_model: Optional[ResponseModel] = None
    additional_options: Dict[str, Any] = Field(default_factory=dict)

class ExtractionOptions(ChatCompletionOptions):
    response_model: ResponseModel

class LLMClient:
    def create_chat_completion(self, options: ChatCompletionOptions) -> Any:
        raise NotImplementedError

    def create_extraction(self, options: ExtractionOptions) -> Any:
        raise NotImplementedError

    def logger(self, message: Dict[str, str]) -> None:
        raise NotImplementedError