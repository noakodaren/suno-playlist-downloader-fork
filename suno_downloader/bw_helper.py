import json
import subprocess
from typing import Optional


def bw_session():
    # try to read session from env
    try:
        out = subprocess.check_output(["bw", "session", "--quiet"], text=True).strip()
        return out
    except subprocess.CalledProcessError:
        raise RuntimeError('Bitwarden is not unlocked. Run "bw unlock" first.')


def get_item_fields(item_name: str, session: Optional[str] = None):
    session = session or bw_session()
    out = subprocess.check_output(["bw", "list", "items", "--session", session], text=True)
    items = json.loads(out)
    for it in items:
        if it.get('name') == item_name:
            # fields is a list of dicts with name/value
            fields = {f['name']: f.get('value') for f in it.get('fields', [])}
            return fields
    return None
