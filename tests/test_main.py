import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]
MAIN = APP_ROOT / "main.py"


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


if __name__ == "__main__":
    unittest.main()
