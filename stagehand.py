import os
import json
import time
import random
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
from selenium.webdriver.common.action_chains import ActionChains

from utils.utils import get_browser
from utils.logger import get_default_logger

from lib.vision import ScreenshotService
from lib.llm.LLMProvider import LLMProvider
from lib.llm.LLMClient import MODELS_WITH_VISION, Image
from lib.inference import act, extract, observe, verify_act_completion

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
        self.default_model_name = "gpt-4o"
        self.headless = headless
        self.driver: Optional[WebDriver] = None
        self.pending_logs: List[Dict[str, Any]] = []
        self.is_processing_logs = False

        self._init()

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

    def _inject_scripts(self) -> None:
        """Inject required JavaScript files into the browser."""
        script_dir = Path(__file__).parent / "lib" / "scripts"
        for script in ["process.js", "utils.js", "debug.js"]:
            script_path = script_dir / script
            self.logger.info(f"Injecting script: {script_path}")
            with open(script_path, encoding='utf-8') as f:
                script_content = f.read()
                self.driver.execute_script(script_content)

    def _init(self) -> Dict[str, Optional[str]]:
        """Initialize the Stagehand instance."""
        browser_info = get_browser(self.env, self.headless, self.logger)
        self.driver = browser_info["driver"]

        # Set viewport size if headless
        if self.headless:
            self.driver.set_window_size(1280, 720)

        # Initialize custom scripts
        self._inject_scripts()

        return {
            "debug_url": browser_info.get("debug_url"),
            "session_url": browser_info.get("session_url")
        }
    
    def goto(self, url: str) -> None:
        """Navigate to a URL and ensure scripts are properly initialized.
        
        Args:
            url: The URL to navigate to
        """
        self.logger.info(f"Navigating to: {url}")
        
        try:
            self.driver.get(url)
            self.wait_for_settled_dom()
            # We have to reinject scripts after navigation as the javascript context reloads in Selenium
            self._inject_scripts()
        except Exception as e:
            self.logger.error(f"Error navigating to {url}: {str(e)}\nTrace: {traceback.format_exc()}")
            raise    

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
        self.act(f"click on {url}")
        
        # Wait for download to complete
        download_path = downloads_dir / f"{title}.pdf"
        timeout = time.time() + 30
        while not download_path.exists() and time.time() < timeout:
            time.sleep(0.5)

    def start_dom_debug(self) -> None:
        """Start DOM debugging if enabled."""
        try:
            if self.debug_dom:
                self.driver.execute_script("if (typeof window.debugDom === 'function') { window.debugDom(); } else { console.log('debugDom is not defined'); }")
        except Exception as e:
            self.log({
                "category": "dom",
                "message": f"Error in start_dom_debug: {str(e)}\nTrace: {traceback.format_exc()}",
                "level": 1
            })

    def cleanup_dom_debug(self) -> None:
        """Cleanup DOM debugging if enabled."""
        try:
            if self.debug_dom:
                self.driver.execute_script("if (typeof window.cleanupDebug === 'function') { window.cleanupDebug(); }")
        except Exception:
            # Silently handle cleanup errors
            pass

    def wait_for_settled_dom(self) -> None:
        """Wait for the DOM to be fully loaded and settled."""
        try:
            # Wait for body element to be present
            WebDriverWait(self.driver, 10).until(
                lambda d: d.find_element(By.TAG_NAME, "body")
            )
            
            # Wait for document ready state
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Check for custom waitForDomSettle function and use it if available
            try:
                self.driver.execute_script("""
                    return new Promise((resolve) => {
                        if (typeof window.waitForDomSettle === 'function') {
                            window.waitForDomSettle().then(() => {
                                resolve(true);
                            });
                        } else {
                            console.warn('waitForDomSettle is not defined, considering DOM as settled');
                            resolve(true);
                        }
                    });
                """)
            except Exception as e:
                self.log({
                    "category": "dom",
                    "message": f"Error waiting for DOM settle function: {str(e)}",
                    "level": 1
                })
                
        except Exception as e:
            self.log({
                "category": "dom",
                "message": f"Error in wait_for_settled_dom: {str(e)}\nTrace: {traceback.format_exc()}",
                "level": 1
            })

    def _get_vision_screenshot(self, use_vision: bool, model: str, selector_map: Dict[str, str]) -> Optional[Image]:
        """Get annotated screenshot for vision processing if enabled.
        
        Args:
            use_vision: Whether vision processing is enabled
            model: The LLM model being used
            selector_map: Dictionary mapping element IDs to selectors
            
        Returns:
            Optional[bytes]: Annotated screenshot bytes if vision is enabled and supported, None otherwise
        """
        if not use_vision:
            return None
            
        if not model in MODELS_WITH_VISION:
            self.log({
                "category": "action",
                "message": f"{model} does not support vision. Skipping vision processing.",
                "level": 1
            })
            return None
            
        screenshot_service = ScreenshotService(
            self.driver,
            selector_map,
            self.verbose
        )
        return screenshot_service.get_annotated_screenshot(False)

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
             steps: str = "",
             model_name: Optional[str] = None,
             chunks_seen: Optional[List[str]] = None,
             use_vision: bool = False,
             verifier_use_vision: bool = True,
             retries: int = 0) -> Dict[str, Any]:
        """Internal method to perform an action."""
        # Inject scripts before every action to be sure processDom() is available
        # TODO: Only inject it where necessary in the future
        self._inject_scripts() 

        model = model_name or self.default_model_name

        if not model in MODELS_WITH_VISION and (use_vision is not False or verifier_use_vision):
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

        annotated_screenshot = self._get_vision_screenshot(use_vision, model, selector_map)

        response = act(
            action, 
            output_string, 
            steps, 
            self.llm_provider, 
            model,
            screenshot=annotated_screenshot,
            logger=self.logger
        )

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
                    steps=steps + ("\n" if not steps.endswith("\n") else "") + "## Step: Scrolled to another section\n",
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
                    steps=steps,
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
        xpath = selector_map[str(element_id)]
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
                    # Re-inject scripts after navigation, as JS context resets
                    self._inject_scripts()

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
                    # Re-inject scripts after navigation, as JS context resets
                    self._inject_scripts()

            elif method in ["fill", "type"]:
                try:
                    element.clear()
                    element.click()
                    text = args[0]
                    for char in text:
                        ActionChains(self.driver).send_keys(char).perform()
                        time.sleep(random.uniform(0.025, 0.075))
                except Exception as e:
                    self.log({
                        "category": "action",
                        "message": f"Error filling element (Retries {retries}): {str(e)}\nTrace: {traceback.format_exc()}",
                        "level": 1
                    })
                    if retries < 2:
                        return self._act(
                            action=action,
                            steps=steps,
                            model_name=model,
                            use_vision=use_vision,
                            verifier_use_vision=verifier_use_vision,
                            retries=retries + 1,
                            chunks_seen=chunks_seen
                        )

            else:
                self.log({
                    "category": "action",
                    "message": f"Chosen method {method} is invalid",
                    "level": 1
                })
                if retries < 2:
                    return self._act(
                        action=action,
                        steps=steps,
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
                steps +
                ("\n" if not steps.endswith("\n") else "") +
                f"## Step: {response['step']}\n"
                f"  Element: {element_text}\n" 
                f"  Action: {response['method']}\n"
                f"  Reasoning: {response['why']}\n"
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

                action_complete = verify_act_completion(
                    action,
                    new_steps,
                    self.llm_provider,
                    model,
                    screenshot=fullpage_screenshot,
                    dom_elements=dom_elements,
                    logger=self.logger
                )

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
                    steps=steps,
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
        
    def _extract(
        self,
        instruction: str,
        schema: Any,
        progress: str = "",
        content: Union[Dict, List] = None,
        chunks_seen: List[int] = None,
        model_name: Optional[str] = None,
        use_vision: Optional[bool] = False
    ) -> Dict[str, Any]:
        """Internal method to handle extraction across chunks."""
        # Inject scripts before every extract to be sure processDom() is available
        # TODO: Only inject it where necessary in the future
        self._inject_scripts() 
        
        model = model_name or self.default_model_name

        content = content or {}
        chunks_seen = chunks_seen or []
        
        self.log({
            "category": "extraction",
            "message": f"starting extraction '{instruction}'",
            "level": 1
        })

        self.wait_for_settled_dom()
        self.start_dom_debug()
        
        result = self.driver.execute_script(
            "return window.processDom(arguments[0])",
            chunks_seen
        )

        output_string = result["outputString"]
        selector_map = result["selectorMap"]
        chunk = result["chunk"]
        chunks = result["chunks"]
        
        self.log({
            "category": "extraction",
            "message": f"received output from processDom. Current chunk index: {chunk}, Number of chunks left: {len(chunks) - len(chunks_seen)}",
            "level": 1
        })

        annotated_screenshot = self._get_vision_screenshot(use_vision, model, selector_map)

        extraction_response = extract(
            instruction,
            progress,
            content,
            output_string,
            schema,
            self.llm_provider,
            model_name or self.default_model_name,
            len(chunks_seen),
            len(chunks),
            screenshot=annotated_screenshot
        )

        metadata = extraction_response.pop("metadata", {})

        new_progress = metadata.get("progress", "")
        completed = metadata.get("completed", False)
        
        output = extraction_response
        # If we're extracting List[BaseModel], then the actual extracted values will be in the "items" key, so set that to the output
        if isinstance(output, dict) and "items" in output and isinstance(output.get("items"), list):
            output = output.get("items")
        
        self.cleanup_dom_debug()

        self.log({
            "category": "extraction",
            "message": f"received extraction response: {json.dumps(extraction_response)}",
            "level": 1
        })

        chunks_seen.append(chunk)

        if completed or len(chunks_seen) == len(chunks):
            self.log({
                "category": "extraction",
                "message": f"response: {json.dumps(extraction_response)}",
                "level": 1
            })
            return output
        else:
            self.log({
                "category": "extraction",
                "message": f"continuing extraction, progress: '{new_progress}'",
                "level": 1
            })
            self.wait_for_settled_dom()
            return self._extract(
                instruction=instruction,
                schema=schema,
                progress=new_progress,
                content=output,
                chunks_seen=chunks_seen,
                model_name=model_name,
                use_vision=use_vision
            )

    def extract(
        self,
        instruction: str,
        schema: Any,
        model_name: Optional[str] = None,
        use_vision: Optional[bool] = False
    ) -> Dict[str, Any]:
        """Extract structured data from the current page."""
        return self._extract(
            instruction=instruction,
            schema=schema,
            model_name=model_name,
            use_vision=use_vision
        )

    def observe(
        self,
        observation: str,
        model_name: Optional[str] = None
    ) -> Optional[str]:
        """Find an element on the page matching the observation."""
        self.log({
            "category": "observation",
            "message": f"starting observation: {observation}",
            "level": 1
        })

        self.wait_for_settled_dom()
        self.start_dom_debug()
        
        result = self.driver.execute_script("return window.processDom([])")
        output_string = result["outputString"]
        selector_map = result["selectorMap"]

        element_id = observe(
            observation,
            output_string,
            self.llm_provider,
            model_name or self.default_model_name
        )
        
        self.cleanup_dom_debug()

        if element_id == "NONE":
            self.log({
                "category": "observation",
                "message": f"no element found for {observation}",
                "level": 1
            })
            return None

        self.log({
            "category": "observation",
            "message": f"found element {element_id}",
            "level": 1
        })

        selector = selector_map[str(element_id)]
        locator_string = f"xpath={selector}"

        self.log({
            "category": "observation",
            "message": f"found locator {locator_string}",
            "level": 1
        })

        # Verify element exists
        element = self.driver.find_element(By.XPATH, selector)
        if not element:
            return None
            
        observation_id = self.record_observation(observation, locator_string)
        return observation_id

    def ask(
        self,
        question: str,
        model_name: Optional[str] = None
    ) -> Optional[str]:
        """Ask a question about the current page."""
        self.wait_for_settled_dom()

        return self.ask({
            "question": question,
            "llm_provider": self.llm_provider,
            "model_name": model_name or self.default_model_name
        })

    def set_driver(self, driver: WebDriver) -> None:
        """Set the WebDriver instance."""
        self.driver = driver

    def record_observation(self, observation: str, result: str) -> str:
        """Record an observation and its result."""
        observation_id = hashlib.sha256(observation.encode()).hexdigest()
        self.observations[observation_id] = {
            "result": result,
            "observation": observation
        }
        return observation_id

    def record_action(self, action: str, result: str) -> str:
        """Record an action and its result."""
        action_id = hashlib.sha256(action.encode()).hexdigest()
        self.actions[action_id] = {
            "result": result,
            "action": action
        }
        return action_id
