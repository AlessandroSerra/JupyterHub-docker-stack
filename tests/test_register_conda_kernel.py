"""Unit tests that do not create environments or install actual kernels."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "singleuser" / "register-conda-kernel.py"
spec = importlib.util.spec_from_file_location("register_conda_kernel", SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class KernelHelperTests(unittest.TestCase):
    def test_valid_names(self):
        for name in ("analysis", "python-3.12", "my_env", "ROOT.v1"):
            with self.subTest(name=name):
                helper.validate_name(name)

    def test_invalid_names(self):
        for name in ("", "my env", "../analysis", "a/b", "a;echo", "a:b"):
            with self.subTest(name=name), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    helper.validate_name(name)
                self.assertEqual(error.exception.code, 1)

    def test_default_environment_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(helper.get_env_dirs(), [Path(helper.DEFAULT_ENVS_DIR)])

    def test_environment_search_paths(self):
        with patch.dict(os.environ, {"CONDA_ENVS_PATH": f"/first{os.pathsep}{os.pathsep}/second"}):
            self.assertEqual(helper.get_env_dirs(), [Path("/first"), Path("/second")])

    def test_find_environment_in_second_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            environment = second / "analysis"
            environment.mkdir(parents=True)
            with patch.dict(os.environ, {"CONDA_ENVS_PATH": f"{first}{os.pathsep}{second}"}):
                self.assertEqual(helper.find_env_path("analysis"), environment)

    def test_missing_environment_reports_search_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            message = io.StringIO()
            with patch.dict(os.environ, {"CONDA_ENVS_PATH": temporary}):
                with contextlib.redirect_stderr(message), self.assertRaises(SystemExit):
                    helper.find_env_path("missing")
            self.assertIn(temporary, message.getvalue())
            self.assertIn("mamba create", message.getvalue())

    def test_missing_python_stops_registration(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = Path(temporary) / "analysis"
            environment.mkdir()
            with patch.object(helper, "find_env_path", return_value=environment):
                with patch.object(helper.subprocess, "run") as run:
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        helper.register_kernel("analysis", "analysis", "Python (analysis)")
                    run.assert_not_called()

    def test_missing_ipykernel_reports_install_command(self):
        message = io.StringIO()
        with patch.object(helper.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            with contextlib.redirect_stderr(message), self.assertRaises(SystemExit):
                helper.check_ipykernel(Path("/env/bin/python"), "analysis")
        self.assertIn("mamba install -y -n analysis ipykernel", message.getvalue())

    def test_registration_uses_environment_python_and_custom_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = Path(temporary) / "envs" / "analysis"
            python = environment / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.touch()
            prefix = Path(temporary) / "persistent" / "jupyter"
            variables = {
                "CONDA_ENVS_PATH": str(environment.parent),
                "JUPYTER_KERNELS_PREFIX": str(prefix),
            }
            with patch.dict(os.environ, variables):
                with patch.object(helper.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                    with contextlib.redirect_stdout(io.StringIO()):
                        helper.register_kernel("analysis", "analysis-kernel", "Python (analysis)")
            self.assertTrue(prefix.is_dir())
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args_list[0].args[0], [str(python), "-c", "import ipykernel"])
            run.assert_called_with(
                [str(python), "-m", "ipykernel", "install", "--prefix", str(prefix),
                 "--name", "analysis-kernel", "--display-name", "Python (analysis)"],
                check=True,
            )

    def test_registration_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            python = Path(temporary) / "bin" / "python"
            python.parent.mkdir()
            python.touch()
            output = io.StringIO()
            with patch.object(helper, "find_env_path", return_value=Path(temporary)):
                with patch.object(helper, "check_ipykernel"):
                    with patch.dict(os.environ, {"JUPYTER_KERNELS_PREFIX": str(Path(temporary) / "kernels")}):
                        with patch.object(helper.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "install")):
                            with contextlib.redirect_stdout(output), self.assertRaises(subprocess.CalledProcessError):
                                helper.register_kernel("analysis", "analysis", "Analysis")
            self.assertNotIn("successfully", output.getvalue())


if __name__ == "__main__":
    unittest.main()
