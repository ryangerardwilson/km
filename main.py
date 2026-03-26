#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from _version import __version__


APP_NAME = "km"
LEGACY_APP_NAME = "keyd_manager"
APP_ROOT = Path(__file__).resolve().parent
ASSET_CONFIG = APP_ROOT / "assets" / "keyd.config"
SYSTEM_CONFIG = Path("/etc/keyd/sticky_keys.conf")
KEYD_SOCKET = Path("/var/run/keyd.socket")
SYS_INPUT_ROOT = Path("/sys/class/input")
REMAPPABLE_COPILOT_KEYS: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (0x247, "assistant", ("hotkeys", "wmi", "assistant")),
    (193, "f23", ("hotkeys", "wmi", "copilot")),
)
UNSUPPORTED_COPILOT_KEYS: tuple[tuple[tuple[int, ...], tuple[str, ...]], ...] = (
    ((0x252, 0x253, 0x279), ("dell", "hotkeys", "wmi", "intel hid")),
)
INSTALL_SCRIPT = Path(
    os.environ.get("KM_INSTALL_SCRIPT")
    or os.environ.get("KEYD_MANAGER_INSTALL_SCRIPT")
    or APP_ROOT / "install.sh"
)

HELP_TEXT = """km
edit, install, and inspect the managed keyd sticky-keys config

flags:
  km -h
    show this help
  km -v
    print the installed version
  km -u
    upgrade to the latest release

features:
  open the managed keyd config in your editor
  # km conf
  km conf

  install the managed config into /etc/keyd and reload the service
  # km apply
  km apply

  inspect the current keyd service status
  # km status
  km status
"""


def config_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME


def legacy_config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / LEGACY_APP_NAME / "keyd.config"


def config_path() -> Path:
    return config_dir() / "keyd.config"


def resolve_editor() -> str:
    return os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim"


def ensure_config_file() -> Path:
    target = config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target

    legacy = legacy_config_path()
    if legacy.exists():
        shutil.copy2(legacy, target)
    else:
        shutil.copy2(ASSET_CONFIG, target)
    return target


def run_root(command: list[str], capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = list(command)
    if os.geteuid() != 0:
        cmd.insert(0, "sudo")
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=capture_output,
    )


def print_help() -> None:
    print(HELP_TEXT.rstrip())


def edit_config() -> int:
    editor = resolve_editor()
    target = ensure_config_file()
    return subprocess.call([editor, str(target)])


def install_self() -> int:
    return subprocess.call([str(INSTALL_SCRIPT), "-u"])


def ensure_keyd_installed() -> int:
    if shutil.which("pacman") is None:
        print("This flow expects Arch Linux with pacman.", file=sys.stderr)
        return 1

    probe = subprocess.run(
        ["pacman", "-Q", "keyd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return 0

    install = run_root(["pacman", "-S", "--needed", "--noconfirm", "keyd"])
    return install.returncode


def _device_key_capabilities() -> list[tuple[str, set[int]]]:
    devices: list[tuple[str, set[int]]] = []
    for event_dir in sorted(SYS_INPUT_ROOT.glob("event*/device")):
        name_path = event_dir / "name"
        modalias_path = event_dir / "modalias"
        if not name_path.exists():
            continue
        name = name_path.read_text(encoding="utf-8", errors="ignore").strip()
        supported: set[int] = set()
        if modalias_path.exists():
            modalias = modalias_path.read_text(encoding="utf-8", errors="ignore")
            if ",k" in modalias:
                key_section = modalias.split(",k", 1)[1].split(",r", 1)[0]
                for token in key_section.split(","):
                    token = token.strip()
                    if not token:
                        continue
                    try:
                        supported.add(int(token, 16))
                    except ValueError:
                        continue
        devices.append((name, supported))
    return devices


def _should_skip_device(name: str) -> bool:
    lowered = name.lower()
    return "keyd virtual" in lowered or "makima virtual" in lowered


def detect_copilot_key_name() -> str | None:
    for name, supported in _device_key_capabilities():
        lowered = name.lower()
        if _should_skip_device(name):
            continue
        for code, key_name, hints in REMAPPABLE_COPILOT_KEYS:
            if code in supported and any(hint in lowered for hint in hints):
                return key_name
    return None


def detect_copilot_detection_warning() -> str | None:
    for name, supported in _device_key_capabilities():
        lowered = name.lower()
        if _should_skip_device(name):
            continue
        for codes, hints in UNSUPPORTED_COPILOT_KEYS:
            present_codes = [f"0x{code:x}" for code in codes if code in supported]
            if present_codes and any(hint in lowered for hint in hints):
                joined_codes = ", ".join(present_codes)
                return (
                    f"Detected {name} exposing Linux keycodes {joined_codes}, "
                    "which this keyd workflow cannot remap automatically as a "
                    "Copilot key on this machine."
                )
    return None


def render_system_config(source: Path) -> tuple[str, str | None]:
    text = source.read_text(encoding="utf-8")
    copilot_key = detect_copilot_key_name()
    if not copilot_key:
        return text, detect_copilot_detection_warning()
    if f"\n{copilot_key} =" in f"\n{text}":
        return text, None
    rendered = text.rstrip() + f"\n\n# Auto-detected laptop Copilot key\n{copilot_key} = oneshot(control)\n"
    return rendered, None


def apply_config() -> int:
    source = ensure_config_file()

    rc = ensure_keyd_installed()
    if rc != 0:
        return rc

    rendered, detection_warning = render_system_config(source)
    tmp_path = config_dir() / ".rendered-keyd.config"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(rendered, encoding="utf-8")
    install = run_root(["install", "-Dm644", str(tmp_path), str(SYSTEM_CONFIG)])
    if install.returncode != 0:
        return install.returncode

    enable = run_root(["systemctl", "enable", "--now", "keyd.service"])
    if enable.returncode != 0:
        return enable.returncode

    for _ in range(10):
        if KEYD_SOCKET.exists():
            break
        time.sleep(0.2)

    reload_cmd = ["keyd", "reload"]
    reload_result = run_root(reload_cmd, capture_output=True)
    if reload_result.returncode != 0:
        combined_output = "\n".join(
            part.strip()
            for part in (reload_result.stdout, reload_result.stderr)
            if part and part.strip()
        )

        restart = run_root(["systemctl", "restart", "keyd.service"], capture_output=True)
        if restart.returncode != 0:
            if combined_output:
                print(combined_output, file=sys.stderr)
            restart_output = "\n".join(
                part.strip()
                for part in (restart.stdout, restart.stderr)
                if part and part.strip()
            )
            if restart_output:
                print(restart_output, file=sys.stderr)
            return restart.returncode

        for _ in range(10):
            if KEYD_SOCKET.exists():
                break
            time.sleep(0.2)

        reload_result = run_root(reload_cmd, capture_output=True)
        if reload_result.returncode != 0:
            retry_output = "\n".join(
                part.strip()
                for part in (reload_result.stdout, reload_result.stderr)
                if part and part.strip()
            )
            if retry_output:
                print(retry_output, file=sys.stderr)
            return reload_result.returncode

    print(f"Installed {source} -> {SYSTEM_CONFIG}")
    if detection_warning:
        print(detection_warning, file=sys.stderr)
    print("keyd config applied.")
    return 0


def show_status() -> int:
    result = subprocess.run(
        ["systemctl", "status", "keyd.service", "--no-pager", "--lines=20"],
        check=False,
    )
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv == ["-h"]:
        print_help()
        return 0

    if argv == ["-v"]:
        print(__version__)
        return 0

    if argv == ["-u"]:
        return install_self()

    if argv == ["conf"]:
        return edit_config()

    if argv == ["apply"]:
        return apply_config()

    if argv == ["status"]:
        return show_status()

    print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
