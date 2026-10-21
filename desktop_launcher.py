"""Current-user Windows shortcut to a private, recoverable standard-library launcher.

No shell integration is attempted on other platforms. Windows shell execution
requires local verification; tests inspect the generated command with a mock.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from typing import Any


def _atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise OSError('Launcher paths cannot be symbolic links.')
    temporary = path.with_name(path.name + '-' + uuid.uuid4().hex + '.tmp')
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def publish_instance(home: Path, port: int, version: str, nonce: str) -> None:
    """Only health-verified callers may reuse this endpoint; PID alone is insufficient."""
    _atomic(Path(home) / 'diagnostics' / 'instance.json', json.dumps({
        'port': port, 'pid': os.getpid(), 'version': version, 'boot': nonce,
    }).encode('utf-8'))


def clear_instance(home: Path, nonce: str) -> None:
    path = Path(home) / 'diagnostics' / 'instance.json'
    try:
        if not path.is_symlink() and json.loads(path.read_text(encoding='utf-8')).get('boot') == nonce:
            path.unlink(missing_ok=True)
    except (OSError, ValueError, AttributeError):
        pass


def shortcut_script() -> str:
    # Values arrive in JSON via the subprocess environment, never interpolated
    # into executable PowerShell. Resolve the user's real Desktop, including
    # OneDrive/folder redirection, using the shell's known-folder interface.
    return r"""
$ErrorActionPreference = 'Stop'
$cfg = $env:FOUNDRY_SHORTCUT_CONFIG | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
$desktop = $shell.SpecialFolders.Item('Desktop')
if (-not $desktop -or -not (Test-Path -LiteralPath $desktop -PathType Container)) { throw 'DesktopUnavailable' }
$link = Join-Path $desktop 'Idea Foundry.lnk'
if (Test-Path -LiteralPath $link) {
    $existing = $shell.CreateShortcut($link)
    if ($existing.TargetPath -eq $cfg.python -and $existing.Arguments -eq $cfg.arguments -and -not $cfg.icon_changed -and (Test-Path -LiteralPath $cfg.icon)) {
        [Console]::WriteLine('{"status":"unchanged"}')
        exit 0
    }
}
Add-Type -AssemblyName System.Drawing
$source = [System.Drawing.Image]::FromFile($cfg.png)
$bitmap = New-Object System.Drawing.Bitmap 256,256
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$memory = New-Object System.IO.MemoryStream
try {
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.DrawImage($source, 0, 0, 256, 256)
    $bitmap.Save($memory, [System.Drawing.Imaging.ImageFormat]::Png)
    $png = $memory.ToArray()
    $iconTemporary = $cfg.icon + '.tmp'
    $file = [System.IO.File]::Open($iconTemporary, [System.IO.FileMode]::Create)
    $writer = New-Object System.IO.BinaryWriter($file)
    try {
        $writer.Write([UInt16]0); $writer.Write([UInt16]1); $writer.Write([UInt16]1)
        $writer.Write([byte]0); $writer.Write([byte]0); $writer.Write([byte]0); $writer.Write([byte]0)
        $writer.Write([UInt16]1); $writer.Write([UInt16]32); $writer.Write([UInt32]$png.Length); $writer.Write([UInt32]22)
        $writer.Write([byte[]]$png)
    } finally { $writer.Dispose(); $file.Dispose() }
    Move-Item -LiteralPath $iconTemporary -Destination $cfg.icon -Force
} finally { $graphics.Dispose(); $bitmap.Dispose(); $source.Dispose(); $memory.Dispose() }
$temporary = Join-Path $desktop 'Idea Foundry.temporary.lnk'
try {
    $shortcut = $shell.CreateShortcut($temporary)
    $shortcut.TargetPath = $cfg.python
    $shortcut.Arguments = $cfg.arguments
    $shortcut.WorkingDirectory = $cfg.directory
    $shortcut.IconLocation = $cfg.icon + ',0'
    $shortcut.Description = 'Idea Foundry - local build studio'
    $shortcut.WindowStyle = 1
    $shortcut.Save()
    Move-Item -LiteralPath $temporary -Destination $link -Force
} finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
[Console]::WriteLine('{"status":"installed"}')
""".strip()


def install_shortcut(root: Path, home: Path, *, platform_name: str | None = None) -> dict[str, Any]:
    """Idempotent best effort. Failure never disables the original .bat launcher."""
    if (platform_name or os.name) != 'nt':
        return {'status': 'not_applicable', 'reason': 'Windows desktop integration is only available on Windows.'}
    root, home = Path(root).resolve(), Path(home).resolve()
    directory = home / 'launcher'
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink():
            raise OSError('Unsafe launcher directory.')
        required = [root / 'bootstrap.py', root / 'desktop_launcher.py', root / 'forge/static/icon.png']
        if not all(path.is_file() and not path.is_symlink() for path in required):
            return {'status': 'unavailable', 'reason': 'Launcher files are unavailable in this installation; the original launcher remains usable.'}
        for name in ('bootstrap.py', 'desktop_launcher.py'):
            source = (root / name).read_bytes()
            target = directory / name
            if target.exists() and target.read_bytes() == source:
                continue
            if target.is_file() and not target.is_symlink():
                _atomic(directory / (target.stem + '-previous.py'), target.read_bytes())
            _atomic(target, source)
            if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(source).digest():
                raise OSError('Stable launcher copy did not match its source.')
        # Preserve the original downloaded program as fallback even when called
        # by an update installed under home/updates/versions. It is never moved.
        original = Path(os.environ.get('FOUNDRY_LAUNCH_ROOT', str(root))).resolve()
        existing = directory / 'settings.json'
        if existing.is_file() and not existing.is_symlink():
            try:
                saved = json.loads(existing.read_text(encoding='utf-8'))
                fallback = Path(saved['fallback_root']).resolve()
                if (fallback / 'run.py').is_file():
                    original = fallback
            except (OSError, ValueError, TypeError, KeyError):
                pass
        _atomic(existing, json.dumps({'schema': 1, 'fallback_root': str(original), 'home': str(home)}, indent=2).encode())
        icon_content = required[-1].read_bytes()
        icon_source = directory / 'icon.png'
        icon_changed = not icon_source.is_file() or icon_source.read_bytes() != icon_content
        if icon_changed:
            _atomic(icon_source, icon_content)
        python = Path(sys.executable)
        # Keep a visible console so Ctrl+C performs the application's existing
        # clean worker shutdown. The shortcut does not use a hidden pythonw job.
        if python.name.lower() == 'pythonw.exe' and python.with_name('python.exe').is_file():
            python = python.with_name('python.exe')
        configuration = {'python': str(python), 'arguments': subprocess.list2cmdline([str(directory / 'bootstrap.py'), '--open']),
                         'directory': str(directory), 'png': str(directory / 'icon.png'), 'icon': str(directory / 'IdeaFoundry.ico'),
                         'icon_changed': icon_changed}
        powershell = shutil.which('powershell.exe') or shutil.which('powershell')
        if not powershell:
            return {'status': 'unavailable', 'reason': 'Windows PowerShell is unavailable; the original launcher remains usable.'}
        environment = dict(os.environ, FOUNDRY_SHORTCUT_CONFIG=json.dumps(configuration))
        encoded = base64.b64encode(shortcut_script().encode('utf-16le')).decode('ascii')
        result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                                env=environment, capture_output=True, text=True, timeout=15, check=False)
        if result.returncode:
            return {'status': 'failed', 'reason': 'Windows could not create the desktop shortcut; the original launcher remains usable.'}
        try:
            report = json.loads(result.stdout.strip())
            status = report.get('status')
        except (ValueError, AttributeError):
            status = None
        if status not in {'installed', 'unchanged'}:
            return {'status': 'failed', 'reason': 'Windows did not confirm shortcut creation; the original launcher remains usable.'}
        return {'status': status, 'reason': 'Idea Foundry desktop shortcut uses a private stable launcher and preserves the original folder as fallback.'}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'status': 'failed', 'reason': 'Desktop integration was unavailable; the original launcher remains usable.'}
