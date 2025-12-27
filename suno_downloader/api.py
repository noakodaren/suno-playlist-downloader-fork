from typing import Optional, Dict, Any
import time
import requests

API_BASE = "https://studio-api.prod.suno.com"

def merge_json(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        result = a.copy()
        for key, value in b.items():
            if key in result:
                result[key] = merge_json(result[key], value)
            else:
                result[key] = value
        return result
    if isinstance(a, list) and isinstance(b,list):
        return a + b
    return b

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
        all = {}
        for page in range(1,1000000):
            url = f"{API_BASE}/api/playlist/{playlist_id}/?page={page}"
            r = requests.get(url, headers=self._headers(), timeout=self.timeout)
            #print(r.text)
            r.raise_for_status()
            x = r.json()
            if len(x.get('playlist_clips')) == 0:
                break
            all = merge_json(all, x)
        print(f"Song count: {len(all.get('playlist_clips'))}")
        return all

    def request_download_url(self, clip_id: str) -> Optional[str]:
        url1 = f"{API_BASE}/api/gen/{clip_id}/convert_wav/"
        r1 = requests.post(url1, headers=self._headers(), timeout=self.timeout)
        url = f"{API_BASE}/api/gen/{clip_id}/wav_file/"
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        try:
            data = r.json()
        except ValueError:
            ret = f"https://cdn1.suno.ai/{clip_id}.wav"
            return ret
        ret = data.get("wav_file_url")
        if ret is None:
            ret = f"https://cdn1.suno.ai/{clip_id}.wav"
        return ret
