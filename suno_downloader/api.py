from typing import Optional, Dict, Any
import time
import requests

API_BASE = "https://studio-api.prod.suno.com"


class SunoAPI:
    def __init__(self, bearer_token: str, device_id: str, timeout: int = 30):
        if not bearer_token or not device_id:
            raise ValueError("bearer_token and device_id are required")
        self.bearer = bearer_token
        self.device_id = device_id
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        # browser-token is typically a small JSON with a timestamp; keep it simple
        browser_token = {"token": str(int(time.time() * 1000))}
        return {
            "Authorization": f"Bearer {self.bearer}",
            "device-id": self.device_id,
            "browser-token": str(browser_token),
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "suno-downloader/1.0",
        }

    def get_playlist(self, playlist_id: str) -> Dict[str, Any]:
        url = f"{API_BASE}/api/playlist/{playlist_id}"
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def request_download_url(self, clip_id: str) -> Optional[str]:
        url = f"{API_BASE}/api/billing/clips/{clip_id}/download/"
        r = requests.post(url, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        try:
            data = r.json()
        except ValueError:
            return None
        # common key is download_url — but defensive check
        return data.get("download_url") or data.get("url")
