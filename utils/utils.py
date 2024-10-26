from typing import Dict, Any
from pydantic import BaseModel

def get_json_response_format(schema: BaseModel, name: str) -> Dict[str, Any]:
    return {
        "type": "json_object",
        "schema": schema.model_json_schema()
    }