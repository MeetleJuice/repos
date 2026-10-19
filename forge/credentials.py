"""Local key setup: allowlisted dotenv values, atomic persistence, no secret responses."""
import os
from pathlib import Path
import re
import uuid
from typing import Any, Iterable

from .providers import KEYS, ALIASES, CONFIG_NAMES, environment_value

ALLOWED = {*KEYS, *ALIASES, *CONFIG_NAMES, 'OLLAMA_URL'}


def parse_dotenv(text: str) -> dict[str, str]:
    if len(text) > 32768 or '\x00' in text:
        raise ValueError('Choose a plain-text .env file smaller than 32 KB.')
    values = {}
    for line in text.lstrip('\ufeff').splitlines():
        line = line.strip()
        if line.startswith('export '): line = line[7:].strip()
        if not line or line.startswith('#') or '=' not in line: continue
        name, value = line.split('=', 1); name = name.strip(); value = value.strip()
        if name not in ALLOWED: continue
        if value[:1] in {'"', "'"}:
            quote = value[0]; end = value.find(quote, 1)
            if end < 0 or value[end+1:].strip() and not value[end+1:].strip().startswith('#'):
                raise ValueError('A recognized .env entry has unmatched quotes or trailing text.')
            value = value[1:end]
        else: value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
        if any(ord(ch) < 32 for ch in value) or any(ch in value for ch in ('\"', "'")) or len(value) > 4096:
            raise ValueError('A recognized .env entry contains unsupported characters.')
        if value and value not in {'...', 'YOUR_KEY', 'your-key-here'}:
            values[name] = value
    for alias,canonical in ALIASES.items():
        if canonical not in values and values.get(alias):
            values[canonical] = values[alias]
    return values


def read_dotenv(path: str | Path) -> str:
    with Path(path).open('rb') as stream:
        data = stream.read(65537)
    if len(data) > 65536: raise ValueError('Local .env exceeds the 64 KB file limit.')
    try:
        return data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    except UnicodeError:
        raise ValueError('Save the local .env as plain UTF-8 or UTF-16 text.') from None


class CredentialStore:
    def __init__(self, home: str | Path, roots: Iterable[str | Path] = ()) -> None:
        self.path = Path(home) / '.env'
        self.paths = list(dict.fromkeys([self.path, *(Path(root) / '.env' for root in roots)]))
        self.injected = {name for name in ALLOWED if os.getenv(name)}
        self.managed: set[str] = set()
        self.warnings: list[str] = []
        self.loaded_files: list[str] = []
        self.reload()

    def reload(self) -> dict[str, Any]:
        found: dict[str, str] = {}
        self.warnings = []
        self.loaded_files = []
        for path in self.paths:
            try:
                if not path.is_file(): continue
                values = parse_dotenv(read_dotenv(path))
            except (OSError, ValueError):
                self.warnings.append("Could not load " + str(path) + ". Check permissions/encoding and matching quotes, or import a corrected key file.")
                continue
            self.loaded_files.append(str(path))
            for name, value in values.items():
                found.setdefault(name, value)
        for name in self.managed - set(found):
            if name not in self.injected: os.environ.pop(name, None)
        for name, value in found.items():
            if name not in self.injected: os.environ[name] = value
        self.managed = set(found)
        return self.status()

    def status(self) -> dict[str, Any]:
        return {'path': str(self.path), 'warnings': self.warnings, 'loaded_files': self.loaded_files,
                'txt_warning': any(p.with_name('.env.txt').is_file() for p in self.paths),
                'keys': {name: bool(environment_value(name)) for name in KEYS},
                'configuration': {name:bool(environment_value(name)) for name in CONFIG_NAMES}}

    def import_text(self, text: str) -> dict[str, Any]:
        if not isinstance(text, str): raise ValueError('Choose a plain-text .env file.')
        values = {k:v for k,v in parse_dotenv(text).items() if k in {*KEYS, *CONFIG_NAMES}}
        if not values: raise ValueError('No recognized nonempty provider keys or Cloudflare account configuration were found.')
        existing = read_dotenv(self.path) if self.path.exists() else ''
        kept = [line for line in existing.splitlines() if line.strip().removeprefix('export ').split('=',1)[0].strip() not in values]
        content = '\n'.join(kept + [f'{k}="{v}"' for k,v in values.items()]) + '\n'
        atomic_text(self.path, content)
        self.injected -= values.keys()
        return self.reload()


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.env-' + uuid.uuid4().hex + '.tmp')
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream: stream.write(content)
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()
