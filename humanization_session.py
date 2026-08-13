import threading

from humanization_ua import get_headers_with_random_ua


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()

    def get_session(self, platform: str):
        with self.lock:
            if platform not in self.sessions:
                import requests

                session = requests.Session()
                session.headers.update(get_headers_with_random_ua())
                self.sessions[platform] = session
            return self.sessions[platform]

    def clear_session(self, platform: str):
        with self.lock:
            if platform in self.sessions:
                self.sessions[platform].cookies.clear()
                del self.sessions[platform]


SESSION_MANAGER = SessionManager()
