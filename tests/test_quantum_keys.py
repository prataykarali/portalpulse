"""Unit tests for 256-bit Quantum-Resistant symmetric key validator."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.db import QUANTUM_KEYS, validate_quantum_key


class TestQuantumKeys(unittest.TestCase):
    def test_valid_admin_key(self):
        role = validate_quantum_key(QUANTUM_KEYS["admin"])
        self.assertEqual(role, "admin")

    def test_valid_faculty_key(self):
        role = validate_quantum_key(QUANTUM_KEYS["faculty"])
        self.assertEqual(role, "faculty")

    def test_valid_student_key(self):
        role = validate_quantum_key(QUANTUM_KEYS["student"])
        self.assertEqual(role, "student")

    def test_invalid_key_rejection(self):
        role = validate_quantum_key("INVALID-QUANTUM-KEY-000")
        self.assertIsNone(role)


if __name__ == "__main__":
    unittest.main()
