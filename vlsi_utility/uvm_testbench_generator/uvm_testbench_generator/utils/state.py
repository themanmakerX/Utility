class StateManager:
    _instance = None

    def __init__(self):
        if StateManager._instance is not None:
            raise Exception("This is a singleton class. Use get_instance().")
        self.state = {}
        self._listeners = []
        self._key_listeners = {}

    @staticmethod
    def get_instance():
        if StateManager._instance is None:
            StateManager._instance = StateManager()
        return StateManager._instance

    def set(self, key, value):
        self.state[key] = value
        self._notify(key, value)

    def get(self, key, default=None):
        return self.state.get(key, default)

    def get_all(self):
        return self.state.copy()

    def clear(self):
        self.state.clear()
        self._notify(None, None)

    def subscribe(self, callback):
        self._listeners.append(callback)

    def subscribe_key(self, key, callback):
        self._key_listeners.setdefault(key, []).append(callback)

    def _notify(self, key, value):
        for cb in list(self._listeners):
            try:
                cb(key, value, self.get_all())
            except Exception:
                pass
        if key is not None:
            for cb in list(self._key_listeners.get(key, [])):
                try:
                    cb(key, value, self.get_all())
                except Exception:
                    pass
