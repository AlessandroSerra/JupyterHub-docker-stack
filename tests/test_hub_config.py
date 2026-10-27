"""Check host/container storage mapping without importing JupyterHub."""

import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import MagicMock, patch


CONFIG = Path(__file__).resolve().parents[1] / "jupyterhub" / "jupyterhub_config.py"


def load_config(environment):
    config = MagicMock()
    authenticator = MagicMock()
    authenticator.__file__ = "/mock/nativeauthenticator/__init__.py"
    with patch.dict(os.environ, environment, clear=True), \
         patch.dict("sys.modules", {"nativeauthenticator": authenticator}):
        namespace = runpy.run_path(str(CONFIG), init_globals={"get_config": lambda: config})
    return config, namespace


class HubStorageTests(unittest.TestCase):
    def test_linux_defaults_are_preserved(self):
        config, _ = load_config({})
        self.assertEqual(config.DockerSpawner.volumes, {
            "/srv/jupyterhub/users/{username}": "/home/jovyan/work",
        })

    def test_custom_host_path_is_used_for_notebook_bind_mount(self):
        config, _ = load_config({"JUPYTERHUB_USERS_DIR": "/Users/example/jupyterhub/users"})
        self.assertEqual(config.DockerSpawner.volumes, {
            "/Users/example/jupyterhub/users/{username}": "/home/jovyan/work",
        })

    def test_hook_uses_container_mount_not_host_path(self):
        _, namespace = load_config({"JUPYTERHUB_USERS_DIR": "/Users/example/jupyterhub/users"})
        spawner = MagicMock()
        spawner.user.name = "student"
        with patch("os.makedirs") as mkdir, patch("os.chown") as chown, patch("os.chmod") as chmod:
            namespace["create_user_dir_hook"](spawner)
        mkdir.assert_called_once_with("/srv/jupyterhub/users/student", mode=0o700, exist_ok=True)
        chown.assert_called_once_with("/srv/jupyterhub/users/student", 1000, 100)
        chmod.assert_called_once_with("/srv/jupyterhub/users/student", 0o700)

    def test_persistent_kernels_are_in_jupyter_search_path(self):
        config, _ = load_config({})
        self.assertEqual(config.DockerSpawner.environment["JUPYTER_PATH"],
                         "/home/jovyan/work/.jupyter/share/jupyter")

    def test_relative_host_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute host path"):
            load_config({"JUPYTERHUB_USERS_DIR": "./users"})


if __name__ == "__main__":
    unittest.main()
