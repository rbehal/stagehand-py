import os
import json
import time
import hashlib
import traceback
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, List, Any, Callable, Union

from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webdriver import WebDriver

from utils import get_browser
from utils.logger import get_default_logger

from lib.vision import ScreenshotService
from lib.llm.LLMProvider import LLMProvider
from lib.inference import act, verify_act_completion

load_dotenv()

class Stagehand:
    def __init__(
        self,
        env: str = os.environ.get('ENVIRONMENT', 'LOCAL'),
        verbose: int = 0,
        debug_dom: bool = False,
        llm_provider: Optional[LLMProvider] = None,
        headless: bool = False,
        logger: Optional[Callable] = None
    ):
        """Initialize Stagehand instance.
        
        Args:
            env: Environment to run in ('LOCAL' or 'BROWSERBASE')
            verbose: Logging verbosity level (0-2)
            debug_dom: Whether to enable DOM debugging
            llm_provider: Optional LLM provider instance
            headless: Whether to run browser in headless mode
            logger: Optional custom logger function
        """
        self.logger = logger or get_default_logger("stagehand")
        self.llm_provider = llm_provider or LLMProvider(self.logger)
        self.env = env
        self.observations: Dict[str, Dict[str, str]] = {}
        self.actions: Dict[str, Dict[str, str]] = {}
        self.verbose = verbose
        self.debug_dom = debug_dom
        self.default_model_name = "gpt-4"
        self.headless = headless
        self.driver: Optional[WebDriver] = None
        self.pending_logs: List[Dict[str, Any]] = []
        self.is_processing_logs = False

    def log(self, log_obj: Dict[str, Any]) -> None:
        """Handle logging for the Stagehand instance."""
        log_obj["level"] = log_obj.get("level", 1)

        category_string = f":{log_obj['category']}" if log_obj.get('category') else ""
        log_message = f"[stagehand{category_string}] {log_obj['message']}"
        
        if log_obj["level"] == 1:
            self.logger.info(log_message)
        elif log_obj["level"] == 2:
            self.logger.debug(log_message)

        # Add logs to pending queue for browserbase
        if self.env == "BROWSERBASE":
            self.pending_logs.append({
                **log_obj,
                "id": hashlib.md5(str(time.time()).encode()).hexdigest()
            })
            self._run_browserbase_log_processing()

    def _run_browserbase_log_processing(self) -> None:
        """Process pending logs for browserbase."""
        if self.is_processing_logs:
            return
            
        self.is_processing_logs = True
        pending_logs = self.pending_logs.copy()
        
        for log_obj in pending_logs:
            self._log_to_browserbase(log_obj)
            
        self.is_processing_logs = False

    def _log_to_browserbase(self, log_obj: Dict[str, Any]) -> None:
        """Send log to browserbase console."""
        if not self.driver:
            return

        if self.verbose >= log_obj.get("level", 1):
            try:
                log_message = f"[stagehand{':' + log_obj['category'] if log_obj.get('category') else ''}] {log_obj['message']}"
                
                if ("trace" in log_obj["message"].lower() or 
                    "error:" in log_obj["message"].lower()):
                    self.driver.execute_script(f"console.error('{log_message}')")
                else:
                    self.driver.execute_script(f"console.log('{log_message}')")
                    
                self.pending_logs = [log for log in self.pending_logs 
                                   if log["id"] != log_obj["id"]]
                                   
            except Exception:
                # Handle page navigation errors silently
                pass

    def init(self, model_name: str = "gpt-4") -> Dict[str, Optional[str]]:
        """Initialize the Stagehand instance."""
        browser_info = get_browser(self.env, self.headless, self.logger)
        self.driver = browser_info["driver"]
        self.default_model_name = model_name

        # Set viewport size if headless
        if self.headless:
            self.driver.set_window_size(1280, 720)

        # Initialize custom scripts
        script_dir = Path(__file__).parent / "lib" / "scripts"
        for script in ["process.js", "utils.js", "debug.js"]:
            with open(script_dir / script) as f:
                self.driver.execute_script(f.read())

        return {
            "debug_url": browser_info.get("debug_url"),
            "session_url": browser_info.get("session_url")
        }

    def download_pdf(self, url: str, title: str) -> None:
        """Download a PDF file."""
        # Configure Chrome options for PDF download
        chrome_options = Options()
        chrome_options.add_experimental_option(
            "prefs", {
                "plugins.always_open_pdf_externally": True,
                "download.default_directory": str(Path.cwd() / "downloads")
            }
        )
        
        # Create downloads directory if it doesn't exist
        downloads_dir = Path.cwd() / "downloads"
        downloads_dir.mkdir(exist_ok=True)
        
        # Click the download link
        self.act({"action": f"click on {url}"})
        
        # Wait for download to complete
        download_path = downloads_dir / f"{title}.pdf"
        timeout = time.time() + 30
        while not download_path.exists() and time.time() < timeout:
            time.sleep(0.5)

    def act(self, 
            action: str,
            model_name: Optional[str] = None,
            use_vision: Union[bool, str] = "fallback") -> Dict[str, Any]:
        """Perform an action on the page."""
        use_vision = use_vision if use_vision != "fallback" else False
        
        return self._act(
            action=action,
            model_name=model_name,
            chunks_seen=[],
            use_vision=use_vision,
            verifier_use_vision=use_vision is not False
        )

    def _act(self,
             action: str, 
             model_name: Optional[str] = None,
             chunks_seen: Optional[List[str]] = None,
             use_vision: bool = False,
             verifier_use_vision: bool = True,
             retries: int = 0) -> Dict[str, Any]:
        """Internal method to perform an action."""
        model = model_name or self.default_model_name

        if not self.models_with_vision.includes(model) and (use_vision is not False or verifier_use_vision):
            self.log({
                "category": "action",
                "message": f"{model} does not support vision, but use_vision was set to {use_vision}. Defaulting to false.",
                "level": 1
            })
            use_vision = False
            verifier_use_vision = False

        self.log({
            "category": "action", 
            "message": f"Running / Continuing action: {action} on page: {self.driver.current_url}",
            "level": 2
        })

        self.wait_for_settled_dom()
        self.start_dom_debug()

        self.log({
            "category": "action",
            "message": "Processing DOM...",
            "level": 2
        })

        # Process DOM using injected JavaScript
        result = self.driver.execute_script(
            "return window.processDom(arguments[0])", 
            chunks_seen
        )
        output_string = result["outputString"] 
        selector_map = result["selectorMap"]
        chunk = result["chunk"]
        chunks = result["chunks"]

        self.log({
            "category": "action",
            "message": f"Looking at chunk {chunk}. Chunks left: {len(chunks) - len(chunks_seen)}",
            "level": 1
        })

        # Handle vision if enabled
        annotated_screenshot = None
        if use_vision is True:
            if not self.models_with_vision.includes(model):
                self.log({
                    "category": "action",
                    "message": f"{model} does not support vision. Skipping vision processing.",
                    "level": 1
                })
            else:
                screenshot_service = ScreenshotService(
                    self.driver,
                    selector_map,
                    self.verbose
                )
                annotated_screenshot = screenshot_service.get_annotated_screenshot(False)

        response = act({
            "action": action,
            "dom_elements": output_string,
            "steps": "",
            "llm_provider": self.llm_provider,
            "model_name": model,
            "screenshot": annotated_screenshot,
            "logger": self.logger
        })

        self.log({
            "category": "action",
            "message": f"Received response from LLM: {json.dumps(response)}",
            "level": 1
        })

        self.cleanup_dom_debug()

        if not response:
            if len(chunks_seen) + 1 < len(chunks):
                chunks_seen.append(chunk)
                
                self.log({
                    "category": "action",
                    "message": f"No action found in current chunk. Chunks seen: {len(chunks_seen)}.",
                    "level": 1
                })

                return self._act(
                    action=action,
                    steps="## Step: Scrolled to another section\n",
                    chunks_seen=chunks_seen,
                    model_name=model_name,
                    use_vision=use_vision,
                    verifier_use_vision=verifier_use_vision
                )
            elif use_vision == "fallback":
                self.log({
                    "category": "action",
                    "message": "Switching to vision-based processing",
                    "level": 1
                })
                self.driver.execute_script("window.scrollTo(0, 0)")
                return self._act(
                    action=action,
                    steps="",
                    chunks_seen=chunks_seen,
                    model_name=model_name,
                    use_vision=True,
                    verifier_use_vision=verifier_use_vision
                )
            else:
                return {
                    "success": False,
                    "message": "Action was not able to be completed.",
                    "action": action
                }

        # Action found, proceed to execute
        element_id = response["element"]
        xpath = selector_map[element_id]
        method = response["method"]
        args = response["args"]

        # Get element text from outputString
        element_lines = output_string.split("\n")
        element_text = next(
            (line.split(":")[1] for line in element_lines if line.startswith(f"{element_id}:")),
            "Element not found"
        )

        self.log({
            "category": "action",
            "message": f"Executing method: {method} on element: {element_id} (xpath: {xpath}) with args: {json.dumps(args)}",
            "level": 1
        })

        url_change_string = ""
        
        try:
            element = self.driver.find_element(By.XPATH, xpath)
            initial_url = self.driver.current_url

            if method == "scrollIntoView":
                self.log({
                    "category": "action",
                    "message": "Scrolling element into view",
                    "level": 2
                })
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                        element
                    )
                except Exception as e:
                    self.log({
                        "category": "action",
                        "message": f"Error scrolling element into view: {str(e)}\nTrace: {traceback.format_exc()}",
                        "level": 1
                    })

            elif method == "click":
                self.log({
                    "category": "action",
                    "message": "Clicking element",
                    "level": 2
                })
                element.click()

                # Handle new window/tab
                handles = self.driver.window_handles
                if len(handles) > 1:
                    new_handle = handles[-1]
                    self.driver.switch_to.window(new_handle)
                    new_url = self.driver.current_url
                    self.log({
                        "category": "action",
                        "message": f"New page detected (new tab) with URL: {new_url}",
                        "level": 1
                    })
                    self.driver.close()
                    self.driver.switch_to.window(handles[0])
                    self.driver.get(new_url)
                    self.wait_for_settled_dom()

                # Wait for network idle
                try:
                    WebDriverWait(self.driver, 5).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                except TimeoutException:
                    self.log({
                        "category": "action",
                        "message": "Network idle timeout hit",
                        "level": 1
                    })

                self.log({
                    "category": "action",
                    "message": "Finished waiting for (possible) page navigation",
                    "level": 1
                })

                if self.driver.current_url != initial_url:
                    self.log({
                        "category": "action",
                        "message": f"New page detected with URL: {self.driver.current_url}",
                        "level": 1
                    })

            else:
                self.log({
                    "category": "action",
                    "message": f"Chosen method {method} is invalid",
                    "level": 1
                })
                if retries < 2:
                    return self._act(
                        action=action,
                        steps="",
                        model_name=model,
                        use_vision=use_vision,
                        verifier_use_vision=verifier_use_vision,
                        retries=retries + 1,
                        chunks_seen=chunks_seen
                    )
                else:
                    return {
                        "success": False,
                        "message": f"Internal error: Chosen method {method} is invalid",
                        "action": action
                    }

            new_steps = (
                "" +
                "## Step: " + response["step"] + "\n" +
                "  Element: " + element_text + "\n" +
                "  Action: " + response["method"] + "\n" +
                "  Reasoning: " + response["why"] + "\n"
            )

            if url_change_string:
                new_steps += f"  Result (Important): {url_change_string}\n\n"

            action_complete = False
            if response.get("completed"):
                self.log({
                    "category": "action",
                    "message": "Action marked as completed, Verifying if this is true...",
                    "level": 1
                })

                dom_elements = None
                fullpage_screenshot = None

                if verifier_use_vision:
                    try:
                        screenshot_service = ScreenshotService(
                            self.driver,
                            selector_map,
                            self.verbose
                        )
                        fullpage_screenshot = screenshot_service.get_screenshot(True, 15)
                    except Exception:
                        screenshot_service = ScreenshotService(
                            self.driver,
                            selector_map,
                            self.verbose
                        )
                        fullpage_screenshot = screenshot_service.get_screenshot(True, 15)
                else:
                    dom_elements = self.driver.execute_script("return window.processAllOfDom()")["outputString"]

                action_complete = verify_act_completion({
                    "goal": action,
                    "steps": new_steps,
                    "llm_provider": self.llm_provider,
                    "model_name": model,
                    "screenshot": fullpage_screenshot,
                    "dom_elements": dom_elements,
                    "logger": self.logger
                })

                self.log({
                    "category": "action",
                    "message": f"Action completion verification result: {action_complete}",
                    "level": 1
                })

            if not action_complete:
                self.log({
                    "category": "action",
                    "message": "Continuing to next action step",
                    "level": 1
                })
                return self._act(
                    action=action,
                    steps=new_steps,
                    model_name=model_name,
                    chunks_seen=chunks_seen,
                    use_vision=use_vision,
                    verifier_use_vision=verifier_use_vision
                )
            else:
                self.log({
                    "category": "action",
                    "message": "Action completed successfully",
                    "level": 1
                })
                self.record_action(action, response["step"])
                return {
                    "success": True,
                    "message": f"Action completed successfully: {new_steps}",
                    "action": action
                }

        except Exception as error:
            self.log({
                "category": "action",
                "message": f"Error performing action (Retries: {retries}): {str(error)}\nTrace: {traceback.format_exc()}",
                "level": 1
            })
            if retries < 2:
                return self._act(
                    action=action,
                    steps="",
                    model_name=model_name,
                    use_vision=use_vision,
                    verifier_use_vision=verifier_use_vision,
                    retries=retries + 1,
                    chunks_seen=chunks_seen
                )

            self.record_action(action, "")
            return {
                "success": False,
                "message": f"Error performing action: {str(error)}",
                "action": action
            }

    def set_driver(self, driver: WebDriver) -> None:
        """Set the WebDriver instance."""
        self.driver = driver
