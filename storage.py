import json
from pathlib import Path
from cryptography.fernet import Fernet

_CONFIG_DIR = Path.home() / ".md-to-ppt"
_KEY_FILE = _CONFIG_DIR / "secret.key"
_DATA_FILE = _CONFIG_DIR / "keys.enc"


class KeyStore:
    def __init__(self):
        _CONFIG_DIR.mkdir(exist_ok=True)
        if not _KEY_FILE.exists():
            _KEY_FILE.write_bytes(Fernet.generate_key())
        self._fernet = Fernet(_KEY_FILE.read_bytes())

    def _load_all(self) -> dict:
        if not _DATA_FILE.exists():
            return {}
        try:
            return json.loads(self._fernet.decrypt(_DATA_FILE.read_bytes()))
        except Exception:
            return {}

    def _save_all(self, data: dict):
        _DATA_FILE.write_bytes(self._fernet.encrypt(json.dumps(data).encode()))

    def save(self, name: str, value: str):
        data = self._load_all()
        data[name] = value
        self._save_all(data)

    def load(self, name: str) -> str:
        return self._load_all().get(name, "")

    def has(self, name: str) -> bool:
        return bool(self.load(name))
