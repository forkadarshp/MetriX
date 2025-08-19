"""
Unit tests for audio utility functions.

Tests audio duration calculation, precision timers, and confidence validation.
"""
import unittest
import tempfile
import os
from app.utils import get_audio_duration_seconds, get_precision_timer, validate_confidence


class TestAudioUtils(unittest.TestCase):
    """Test cases for audio utility functions."""

    def test_nonexistent_file(self):
        """Test audio duration for non-existent file."""
        duration = get_audio_duration_seconds("nonexistent.mp3")
        self.assertEqual(duration, 0.0, "Non-existent file should return 0.0 duration")

    def test_empty_file(self):
        """Test audio duration for empty file."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_path = f.name
        try:
            duration = get_audio_duration_seconds(temp_path)
            # Empty file should return 0.0 or very small duration
            self.assertLessEqual(duration, 0.1, "Empty file should return very small duration")
        finally:
            os.unlink(temp_path)

    def test_precision_timer(self):
        """Test precision timer function."""
        timer = get_precision_timer()
        time1 = timer()
        time2 = timer()
        self.assertGreater(time2, time1, "Timer should return increasing values")
        self.assertIsInstance(time1, float, "Timer should return float values")

    def test_confidence_validation_normal(self):
        """Test confidence validation for normal values."""
        self.assertEqual(validate_confidence(0.95), 0.95, "Normal confidence should be unchanged")
        self.assertEqual(validate_confidence(0.0), 0.0, "Zero confidence should be unchanged")
        self.assertEqual(validate_confidence(1.0), 1.0, "Perfect confidence should be unchanged")

    def test_confidence_validation_percentage(self):
        """Test confidence validation for percentage values."""
        self.assertEqual(validate_confidence(95.0), 0.95, "Percentage should be converted to ratio")
        self.assertEqual(validate_confidence(85.5), 0.855, "Decimal percentage should be converted")

    def test_confidence_validation_negative(self):
        """Test confidence validation for negative values."""
        self.assertEqual(validate_confidence(-0.1), 0.0, "Negative confidence should be clamped to 0.0")
        self.assertEqual(validate_confidence(-10.0), 0.0, "Large negative should be clamped to 0.0")

    def test_confidence_validation_too_high(self):
        """Test confidence validation for values too high."""
        self.assertEqual(validate_confidence(1.1), 1.0, "Slightly high confidence should be clamped to 1.0")
        self.assertEqual(validate_confidence(150.0), 1.0, "Very high confidence should be clamped to 1.0")

    def test_confidence_validation_none(self):
        """Test confidence validation for None value."""
        self.assertEqual(validate_confidence(None), 0.0, "None confidence should default to 0.0")

    def test_confidence_validation_invalid_type(self):
        """Test confidence validation for invalid types."""
        self.assertEqual(validate_confidence("invalid"), 0.0, "String confidence should default to 0.0")
        self.assertEqual(validate_confidence([1, 2, 3]), 0.0, "List confidence should default to 0.0")


if __name__ == "__main__":
    unittest.main()
