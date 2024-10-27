import os
import json

from typing import Dict
from dataclasses import dataclass

@dataclass
class CacheValue:
    id: str
    result: str

class Cache:
    """
    A file system cache to skip inference when repeating steps.
    It also acts as the source of truth for identifying previously seen actions and observations.
    """
    def __init__(self, disabled: bool = False):
        self.disabled = disabled
        self.observations_path = "./.cache/observations.json"
        self.actions_path = "./.cache/actions.json"
        
        if not self.disabled:
            self._init_cache()

    def read_observations(self) -> Dict[str, CacheValue]:
        """Read and return cached observations."""
        if self.disabled:
            return {}
        
        try:
            with open(self.observations_path, 'r') as f:
                return json.load(f)
        except Exception as error:
            print(f"Error reading from observations.json: {error}")
            return {}

    def read_actions(self) -> Dict[str, CacheValue]:
        """Read and return cached actions."""
        if self.disabled:
            return {}
        
        try:
            with open(self.actions_path, 'r') as f:
                return json.load(f)
        except Exception as error:
            print(f"Error reading from actions.json: {error}")
            return {}

    def write_observations(self, key: str, value: CacheValue) -> None:
        """Write an observation to the cache."""
        if self.disabled:
            return

        observations = self.read_observations()
        observations[key] = {"id": value.id, "result": value.result}
        
        with open(self.observations_path, 'w') as f:
            json.dump(observations, f, indent=2)

    def write_actions(self, key: str, value: CacheValue) -> None:
        """Write an action to the cache."""
        if self.disabled:
            return

        actions = self.read_actions()
        actions[key] = {"id": value.id, "result": value.result}
        
        with open(self.actions_path, 'w') as f:
            json.dump(actions, f, indent=2)

    def evict_cache(self) -> None:
        """Clear the cache (Not implemented)."""
        raise NotImplementedError("implement me")

    def _init_cache(self) -> None:
        """Initialize cache directory and files if they don't exist."""
        if self.disabled:
            return

        cache_dir = ".cache"

        # Create cache directory if it doesn't exist
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        # Create actions file if it doesn't exist
        if not os.path.exists(self.actions_path):
            with open(self.actions_path, 'w') as f:
                json.dump({}, f)

        # Create observations file if it doesn't exist
        if not os.path.exists(self.observations_path):
            with open(self.observations_path, 'w') as f:
                json.dump({}, f)
