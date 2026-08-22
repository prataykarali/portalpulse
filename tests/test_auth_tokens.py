"""Unit tests for Role-Based Cryptographic Access Tokens (RBAC-PAT)."""

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.db import (
    ROLE_ACCESS_TOKENS,
    LEGACY_KEYS,
    validate_role_access_token,
    validate_quantum_key,
)


class TestAuthTokens(unittest.TestCase):
    def test_valid_admin_token(self):
        role = validate_role_access_token(ROLE_ACCESS_TOKENS["admin"])
        self.assertEqual(role, "admin")

    def test_valid_faculty_token(self):
        role = validate_role_access_token(ROLE_ACCESS_TOKENS["faculty"])
        self.assertEqual(role, "faculty")

    def test_valid_student_token(self):
        role = validate_role_access_token(ROLE_ACCESS_TOKENS["student"])
        self.assertEqual(role, "student")

    def test_invalid_token_rejection(self):
        self.assertIsNone(validate_role_access_token("INVALID-TOKEN-XYZ-000"))
        self.assertIsNone(validate_role_access_token(""))
        self.assertIsNone(validate_role_access_token("ADM-SEC-TAMPERED-KEY"))

    def test_legacy_quantum_key_compatibility(self):
        # Backward compatibility with original key strings
        self.assertEqual(validate_quantum_key(LEGACY_KEYS["admin"]), "admin")
        self.assertEqual(validate_quantum_key(LEGACY_KEYS["faculty"]), "faculty")
        self.assertEqual(validate_quantum_key(LEGACY_KEYS["student"]), "student")

    def test_whitespace_handling(self):
        token_with_spaces = f"  {ROLE_ACCESS_TOKENS['admin']}  "
        self.assertEqual(validate_role_access_token(token_with_spaces), "admin")


if __name__ == "__main__":
    unittest.main()
