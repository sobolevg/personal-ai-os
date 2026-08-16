import stat
import tempfile
from pathlib import Path
import unittest

from services.link_capture.transcription.plaud_web_login import (
    _create_password_file,
    _generate_password,
)


class PlaudWebLoginTests(unittest.TestCase):
    def test_generated_password_matches_plaud_requirements(self) -> None:
        password = _generate_password()

        self.assertEqual(len(password), 16)
        self.assertTrue(any(character.islower() for character in password))
        self.assertTrue(any(character.isupper() for character in password))
        self.assertTrue(any(character.isdigit() for character in password))

    def test_password_file_is_private_and_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials" / "plaud-password"
            password = _create_password_file(path)

            self.assertEqual(path.read_text(encoding="utf-8"), password + "\n")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                _create_password_file(path)


if __name__ == "__main__":
    unittest.main()
