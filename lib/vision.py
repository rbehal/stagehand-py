import io
import os
import logging
import platform
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from PIL import Image, ImageDraw, ImageFont


@dataclass
class AnnotationBox:
    x: float
    y: float
    width: float
    height: float
    id: str

@dataclass
class NumberPosition:
    x: float
    y: float

class ScreenshotService:
    def __init__(
        self,
        driver: WebDriver,
        selector_map: Dict[int, str],
        verbose: int,
        is_debug_enabled: bool = False
    ):
        self.driver = driver
        self.selector_map = selector_map
        self.annotation_boxes: List[AnnotationBox] = []
        self.number_positions: List[NumberPosition] = []
        self.is_debug_enabled = is_debug_enabled
        self.verbose = verbose

    def log(self, category: Optional[str], message: str, level: int = 1) -> None:
        if self.verbose >= level:
            category_string = f":{category}" if category else ""
            logging.info(f"[stagehand{category_string}] {message}")

    def get_screenshot(self, fullpage: bool = True, quality: Optional[int] = None) -> bytes:
        if quality and (quality < 0 or quality > 100):
            raise ValueError("quality must be between 0 and 100")

        # For full page screenshot in Selenium
        if fullpage:
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            total_width = self.driver.execute_script("return document.body.scrollWidth")
            self.driver.set_window_size(total_width, total_height)

        screenshot = self.driver.get_screenshot_as_png()
        
        if quality:
            # Convert PNG to JPEG with quality setting
            img = Image.open(io.BytesIO(screenshot))
            output = io.BytesIO()
            img.convert('RGB').save(output, format='JPEG', quality=quality)
            return output.getvalue()
        
        return screenshot

    def get_screenshot_pixel_count(self, screenshot: bytes) -> int:
        img = Image.open(io.BytesIO(screenshot))
        width, height = img.size
        pixel_count = width * height
        
        self.log(
            category="Info",
            message=f"Screenshot pixel count: {pixel_count}",
            level=1
        )
        return pixel_count

    def get_annotated_screenshot(self, fullpage: bool) -> bytes:
        self.annotation_boxes = []
        self.number_positions = []

        screenshot = self.get_screenshot(fullpage)
        img = Image.open(io.BytesIO(screenshot))
        draw = ImageDraw.Draw(img)

        scroll_position = self.driver.execute_script(
            "return {scrollX: window.scrollX, scrollY: window.scrollY};"
        )

        # Process each element in selector_map
        for id_str, selector in self.selector_map.items():
            self._create_element_annotation(draw, id_str, selector, scroll_position)

        output = io.BytesIO()
        img.save(output, format='PNG')
        annotated_screenshot = output.getvalue()

        if self.is_debug_enabled:
            self.save_and_open_screenshot(annotated_screenshot)

        return annotated_screenshot

    def _create_element_annotation(
        self,
        draw: ImageDraw.Draw,
        id_str: str,
        selector: str,
        scroll_position: dict
    ) -> None:
        try:
            element = self.driver.find_element(By.XPATH, selector)
            location = element.location
            size = element.size

            box = AnnotationBox(
                x=location['x'] + scroll_position['scrollX'],
                y=location['y'] + scroll_position['scrollY'],
                width=size['width'],
                height=size['height'],
                id=id_str
            )

            self.annotation_boxes.append(box)

            # Draw rectangle
            draw.rectangle(
                [(box.x, box.y), (box.x + box.width, box.y + box.height)],
                outline='red',
                width=2
            )

            # Add number indicator
            number_pos = self._find_non_overlapping_number_position(box)
            circle_radius = 12
            
            # Draw circle with number
            draw.ellipse(
                [(number_pos.x - circle_radius, number_pos.y - circle_radius),
                 (number_pos.x + circle_radius, number_pos.y + circle_radius)],
                fill='white',
                outline='red',
                width=2
            )

            # Add text
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except:
                font = ImageFont.load_default()
                
            draw.text(
                (number_pos.x, number_pos.y),
                str(id_str),
                fill='red',
                font=font,
                anchor="mm"
            )

        except Exception as error:
            self.log(
                category="Error",
                message=f"Failed to create annotation for element {id_str}: {str(error)}",
                level=0
            )

    def _find_non_overlapping_number_position(self, box: AnnotationBox) -> NumberPosition:
        circle_radius = 12
        position = NumberPosition(
            x=box.x - circle_radius,
            y=box.y - circle_radius
        )

        attempts = 0
        max_attempts = 10
        offset = 5

        while self._is_number_overlapping(position) and attempts < max_attempts:
            position.y += offset
            attempts += 1

        self.number_positions.append(position)
        return position

    def _is_number_overlapping(self, position: NumberPosition) -> bool:
        circle_radius = 12
        return any(
            ((position.x - existing.x) ** 2 + (position.y - existing.y) ** 2) ** 0.5 < circle_radius * 2
            for existing in self.number_positions
        )

    @staticmethod
    def save_and_open_screenshot(screenshot: bytes) -> None:
        screenshot_dir = os.path.join(os.getcwd(), "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)

        timestamp = datetime.now().isoformat().replace(':', '-').replace('.', '-')
        filename = os.path.join(screenshot_dir, f"screenshot-{timestamp}.png")

        with open(filename, 'wb') as f:
            f.write(screenshot)
        
        print(f"Screenshot saved to: {filename}")

        # Open screenshot with default viewer
        if platform.system() == "Windows":
            os.startfile(filename)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", filename])
        else:  # Linux
            subprocess.run(["xdg-open", filename])
