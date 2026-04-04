import time


class PluginManager:
    def __init__(self, plugins):
        self.plugins = plugins
        self.index = 0
        self.plugin_started_at = time.time()

    def current_plugin(self):
        return self.plugins[self.index]

    def tick_rotation(self):
        if not self.plugins:
            return

        now = time.time()
        plugin = self.current_plugin()

        if now - self.plugin_started_at >= plugin.display_seconds:
            self.index = (self.index + 1) % len(self.plugins)
            self.plugin_started_at = now

