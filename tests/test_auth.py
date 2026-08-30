import os
import tempfile
import unittest
from pathlib import Path

import database.database as database
from auth.authentication import authenticate, create_session, get_user_by_session, register_user, revoke_session


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self.temp_dir.name) / "test.db"
        database.initialize_database()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_password_is_not_stored_in_plain_text(self):
        ok, _ = register_user("Ana Runner", "ana.runner", "ana@example.com", "segredo-forte")
        self.assertTrue(ok)
        user = authenticate("ana@example.com", "segredo-forte")
        self.assertIsNotNone(user)
        self.assertNotEqual(user["password_hash"], "segredo-forte")
        self.assertTrue(user["password_hash"].startswith("scrypt$"))

    def test_duplicate_email_is_rejected(self):
        register_user("Ana Runner", "ana.runner", "ana@example.com", "segredo-forte")
        ok, message = register_user("Outra Ana", "outra.runner", "ana@example.com", "segredo-forte")
        self.assertFalse(ok)
        self.assertIn("e-mail", message)

    def test_session_restores_user_until_revoked(self):
        register_user("Ana Runner", "ana.runner", "ana@example.com", "segredo-forte")
        user = authenticate("ana@example.com", "segredo-forte")
        token = create_session(user["id"])
        self.assertEqual(get_user_by_session(token)["email"], "ana@example.com")
        revoke_session(token)
        self.assertIsNone(get_user_by_session(token))


if __name__ == "__main__":
    unittest.main()