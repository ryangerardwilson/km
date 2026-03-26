import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]
MAIN = APP_ROOT / "main.py"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import main as km_main


def run_app(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base_env = os.environ.copy()
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, str(MAIN), *args],
        capture_output=True,
        text=True,
        check=False,
        env=base_env,
    )


def encode_modalias_keys(*codes: int) -> str:
    if not codes:
        return "input:b0003v0000p0000e0000-e0,1,4,ram4,lsfw"
    key_tokens = ",".join(f"{code:X}" for code in codes)
    return f"input:b0003v0000p0000e0000-e0,1,4,k{key_tokens},ram4,lsfw"


class MainContractTests(unittest.TestCase):
    def test_no_args_matches_dash_h(self):
        no_args = run_app()
        help_args = run_app("-h")
        self.assertEqual(no_args.returncode, 0)
        self.assertEqual(no_args.stdout, help_args.stdout)

    def test_version_is_single_line(self):
        result = run_app("-v")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "0.0.0")

    def test_ensure_config_seeds_xdg_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {"XDG_CONFIG_HOME": temp_dir}
            result = run_app("conf", env={**env, "EDITOR": "/usr/bin/true"})
            self.assertEqual(result.returncode, 0)
            target = Path(temp_dir) / "km" / "keyd.config"
            self.assertTrue(target.exists())

    def test_ensure_config_migrates_legacy_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            legacy_dir = Path(temp_dir) / "keyd_manager"
            legacy_dir.mkdir()
            legacy_config = legacy_dir / "keyd.config"
            legacy_config.write_text("[ids]\n*\n", encoding="utf-8")

            env = {"XDG_CONFIG_HOME": temp_dir}
            result = run_app("conf", env={**env, "EDITOR": "/usr/bin/true"})
            self.assertEqual(result.returncode, 0)

            target = Path(temp_dir) / "km" / "keyd.config"
            self.assertEqual(target.read_text(encoding="utf-8"), "[ids]\n*\n")

    def test_upgrade_invokes_install_script_with_dash_u(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "marker.txt"
            install_script = Path(temp_dir) / "install.sh"
            install_script.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" > \"$KM_MARKER\"\n",
                encoding="utf-8",
            )
            install_script.chmod(0o755)

            result = run_app(
                "-u",
                env={
                    "KM_INSTALL_SCRIPT": str(install_script),
                    "KM_MARKER": str(marker),
                },
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(encoding="utf-8").strip(), "-u")

    def test_apply_retries_reload_after_socket_error(self):
        completed = subprocess.CompletedProcess
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        source = Path(temp_dir.name) / "keyd.config"
        source.write_text("[main]\ncontrol = oneshot(control)\n", encoding="utf-8")

        with (
            mock.patch("main.ensure_config_file", return_value=source),
            mock.patch("main.ensure_keyd_installed", return_value=0),
            mock.patch("pathlib.Path.exists", autospec=True, side_effect=lambda path: path == km_main.KEYD_SOCKET),
            mock.patch("main.time.sleep"),
            mock.patch(
                "main.run_root",
                side_effect=[
                    completed(["install"], 0),
                    completed(["systemctl", "enable", "--now", "keyd.service"], 0),
                    completed(["keyd", "reload"], 1, "", "failed to connect to /var/run/keyd.socket"),
                    completed(["systemctl", "restart", "keyd.service"], 0),
                    completed(["keyd", "reload"], 0),
                ],
            ) as run_root,
        ):
            rc = km_main.apply_config()

        self.assertEqual(rc, 0)
        self.assertEqual(
            [call.args[0] for call in run_root.call_args_list],
            [
                ["install", "-Dm644", str(km_main.config_dir() / ".rendered-keyd.config"), str(km_main.SYSTEM_CONFIG)],
                ["systemctl", "enable", "--now", "keyd.service"],
                ["keyd", "reload"],
                ["systemctl", "restart", "keyd.service"],
                ["keyd", "reload"],
            ],
        )

    def test_detect_copilot_key_name_prefers_assistant_then_f23(self):
        with mock.patch(
            "main._device_key_capabilities",
            return_value=[
                ("AT Translated Set 2 keyboard", {125, 193}),
                ("Asus WMI hotkeys", {0x247}),
            ],
        ):
            self.assertEqual(km_main.detect_copilot_key_name(), "assistant")

        with mock.patch(
            "main._device_key_capabilities",
            return_value=[
                ("Vendor Copilot Hotkeys", {193}),
            ],
        ):
            self.assertEqual(km_main.detect_copilot_key_name(), "f23")

        with mock.patch(
            "main._device_key_capabilities",
            return_value=[
                ("AT Translated Set 2 keyboard", {125, 193}),
            ],
        ):
            self.assertIsNone(km_main.detect_copilot_key_name())

    def test_render_system_config_appends_detected_copilot_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "keyd.config"
            source.write_text("[main]\ncontrol = oneshot(control)\n", encoding="utf-8")

            with mock.patch("main.detect_copilot_key_name", return_value="f23"):
                rendered = km_main.render_system_config(source)

        self.assertIn("f23 = oneshot(control)", rendered)

    def test_detect_copilot_maps_f23_hotkey_devices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            event_dir = Path(temp_dir) / "event11" / "device"
            event_dir.mkdir(parents=True)
            (event_dir / "name").write_text("Dell Copilot Hotkeys", encoding="utf-8")
            (event_dir / "modalias").write_text(encode_modalias_keys(193), encoding="utf-8")

            original_root = km_main.SYS_INPUT_ROOT
            km_main.SYS_INPUT_ROOT = Path(temp_dir)
            try:
                self.assertEqual(km_main.detect_copilot_key_name(), "f23")
            finally:
                km_main.SYS_INPUT_ROOT = original_root

    def test_render_system_config_warns_for_dell_privacy_key_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            event_dir = Path(temp_dir) / "event11" / "device"
            event_dir.mkdir(parents=True)
            (event_dir / "name").write_text("Dell WMI hotkeys", encoding="utf-8")
            (event_dir / "modalias").write_text(encode_modalias_keys(0x252, 0x253), encoding="utf-8")

            original_root = km_main.SYS_INPUT_ROOT
            km_main.SYS_INPUT_ROOT = Path(temp_dir)
            try:
                rendered, warning = km_main.render_system_config(APP_ROOT / "assets" / "keyd.config")
            finally:
                km_main.SYS_INPUT_ROOT = original_root

            self.assertEqual(rendered, (APP_ROOT / "assets" / "keyd.config").read_text(encoding="utf-8"))
            self.assertIsNotNone(warning)
            self.assertIn("Dell WMI hotkeys", warning)
            self.assertIn("0x252", warning)


if __name__ == "__main__":
    unittest.main()
