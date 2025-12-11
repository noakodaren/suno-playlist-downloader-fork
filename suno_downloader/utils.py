from typing import Optional
import os
import time
import requests
from tqdm import tqdm

INVALID_CHARS = set('/\\:?*"<>|')


def sanitize_filename(name: str) -> str:
    if not name:
        return "unnamed"
    return ''.join(c if c not in INVALID_CHARS else '_' for c in name).strip()


def download_with_retries(url: str, out_path: str, timeout: int = 30, attempts: int = 3, backoff: int = 2):
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)

    for attempt in range(1, attempts + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length') or 0)
                with open(out_path, 'wb') as f, tqdm(total=total, unit='B', unit_scale=True, desc=os.path.basename(out_path)) as pbar:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            return True
        except Exception as e:
            if attempt == attempts:
                raise
            time.sleep(backoff * attempt)
    return False
