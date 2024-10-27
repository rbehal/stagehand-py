import os
from typing import List, Dict
from pydantic import BaseModel, Field

from selenium.webdriver.remote.webdriver import WebDriver

class DOMElement(BaseModel):
    """Represents a processed DOM element"""
    xpath: str = Field(description="XPath selector for the element")
    text: str = Field(description="Visible text content")
    tag_name: str = Field(description="HTML tag name")
    is_interactive: bool = Field(description="Whether element is interactive")
    attributes: Dict[str, str] = Field(description="Element attributes")
    bounding_box: Dict[str, float] = Field(description="Element position and size")
    chunk_id: int = Field(default=0, description="Viewport chunk this element belongs to")

class DOMProcessor:
    def __init__(self, driver: WebDriver, chunk_size: int = 3):
        self.driver = driver
        self.chunk_size = chunk_size
        
    def process_dom(self) -> List[DOMElement]:
        """Main entry point for DOM processing"""
        # Inject required scripts
        self._inject_processing_scripts()
        
        # Get candidate elements
        elements = self._get_candidate_elements()
        
        # Process chunks
        chunked_elements = self._chunk_elements(elements)
        
        return chunked_elements

    def _inject_processing_scripts(self) -> None:
        """Inject helper scripts into the page"""
        script_path = os.path.join(
            os.path.dirname(__file__), 
            'scripts', 
            'dom_extraction.js'
        )
        
        with open(script_path, 'r') as file:
            script_content = file.read()
            
        self.driver.execute_script(script_content)

    def _get_candidate_elements(self) -> List[DOMElement]:
        """Get all candidate elements from the page"""
        elements = self.driver.execute_script("return window.getVisibleElements();")
        return [DOMElement(**element) for element in elements]

    def _chunk_elements(self, elements: List[DOMElement]) -> List[DOMElement]:
        """Split elements into viewport chunks"""
        viewport_height = self.driver.execute_script("return window.innerHeight;")
        chunk_height = viewport_height / self.chunk_size
        
        for element in elements:
            chunk_id = int(element.bounding_box["y"] / chunk_height)
            element.chunk_id = chunk_id
            
        return elements
