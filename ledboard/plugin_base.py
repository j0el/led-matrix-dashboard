from abc import ABC, abstractmethod
from PIL import Image


class BasePlugin(ABC):
    name = "base"
    refresh_seconds = 300
    display_seconds = 10

    def __init__(self, app_context: dict):
        self.app_context = app_context
        self.last_refresh = 0
        self.state = {}

    def should_refresh(self, now_ts: float) -> bool:
        return (now_ts - self.last_refresh) >= self.refresh_seconds

    def refresh(self) -> None:
        self.last_refresh = __import__("time").time()

    @abstractmethod
    def render(self, width: int, height: int) -> Image.Image:
        raise NotImplementedError

