"""Regression checks for configured policies, not authenticator integration tests."""

import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from test_hub_config import load_config


class AccountPolicyTests(unittest.TestCase):
    def setUp(self):
        self.config, _ = load_config({})

    def test_username_policy(self):
        pattern = self.config.Authenticator.username_pattern
        for username in ("ab", "student", "student_01", "student-01", "a" * 32):
            with self.subTest(allowed=username):
                self.assertIsNotNone(re.fullmatch(pattern, username))
        for username in ("a", "a" * 33, "Student", "1student", "../hub", "a/b", "a.b", "a b", ""):
            with self.subTest(rejected=username):
                self.assertIsNone(re.fullmatch(pattern, username))

    def test_signup_and_allowlist_remain_restricted(self):
        self.assertFalse(self.config.NativeAuthenticator.open_signup)
        self.assertEqual(self.config.Authenticator.admin_users, {"jhubadmin"})
        self.assertEqual(self.config.Authenticator.allowed_users, {"jhubadmin"})

    def test_password_and_retry_policy(self):
        auth = self.config.NativeAuthenticator
        self.assertEqual(auth.minimum_password_length, 12)
        self.assertTrue(auth.check_common_password)
        self.assertEqual(auth.allowed_failed_logins, 5)
        self.assertEqual(auth.seconds_before_next_try, 600)


class UserDirectorySecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "users"
        self.root.mkdir()
        _, namespace = load_config({})
        self.hook = namespace["create_user_dir_hook"]
        self.globals_patch = patch.dict(self.hook.__globals__, {"USERS_ROOT": str(self.root)})
        self.globals_patch.start()
        self.addCleanup(self.globals_patch.stop)

    def spawn(self, username):
        spawner = MagicMock()
        spawner.user.name = username
        self.hook(spawner)

    def test_rejects_traversal_nested_and_absolute_paths_before_mutation(self):
        outside = str(self.root.parent / "outside")
        for username in ("../hub", "..", ".", "", "nested/student", outside):
            with self.subTest(username=username), patch("os.makedirs") as mkdir, patch("os.chown") as chown, patch("os.chmod") as chmod:
                with self.assertRaisesRegex(ValueError, "Invalid user directory"):
                    self.spawn(username)
                mkdir.assert_not_called()
                chown.assert_not_called()
                chmod.assert_not_called()

    def test_rejects_symlink_escaping_storage_root(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        (self.root / "student").symlink_to(outside, target_is_directory=True)
        with patch("os.chown") as chown, patch("os.chmod") as chmod:
            with self.assertRaisesRegex(ValueError, "Invalid user directory"):
                self.spawn("student")
            chown.assert_not_called()
            chmod.assert_not_called()

    def test_creates_private_directory_and_handles_existing_directory(self):
        # Do not require root or change real ownership in unit tests.
        with patch("os.chown") as chown:
            self.spawn("student")
            self.spawn("student")
        directory = self.root / "student"
        self.assertTrue(directory.is_dir())
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(chown.call_count, 2)
        chown.assert_called_with(str(directory), 1000, 100)

    def test_repairs_existing_directory_permissions(self):
        directory = self.root / "student"
        directory.mkdir(mode=0o755)
        os.chmod(directory, 0o755)
        with patch("os.chown"):
            self.spawn("student")
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
