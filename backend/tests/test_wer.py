"""
Unit tests for Word Error Rate (WER) calculation.

Tests the accuracy and edge cases of WER calculation using both
jiwer library (when available) and fallback implementation.
"""
import unittest
from app.utils import calculate_wer


class TestWER(unittest.TestCase):
    """Test cases for Word Error Rate calculation."""

    def test_perfect_match(self):
        """Test WER calculation for perfect match."""
        reference = "the quick brown fox"
        hypothesis = "the quick brown fox"
        wer = calculate_wer(reference, hypothesis)
        self.assertEqual(wer, 0.0, "Perfect match should have WER of 0.0")

    def test_complete_mismatch(self):
        """Test WER calculation for complete mismatch."""
        reference = "the quick brown fox"
        hypothesis = "hello world goodbye earth"
        wer = calculate_wer(reference, hypothesis)
        self.assertEqual(wer, 1.0, "Complete mismatch should have WER of 1.0")

    def test_single_substitution(self):
        """Test WER calculation for single word substitution."""
        reference = "the quick brown fox"
        hypothesis = "the fast brown fox"
        wer = calculate_wer(reference, hypothesis)
        self.assertEqual(wer, 0.25, "Single substitution in 4 words should have WER of 0.25")

    def test_case_insensitive(self):
        """Test that WER calculation is case insensitive."""
        reference = "The Quick Brown Fox"
        hypothesis = "the quick brown fox"
        wer = calculate_wer(reference, hypothesis)
        self.assertEqual(wer, 0.0, "Case differences should not affect WER")

    def test_punctuation_handling(self):
        """Test that punctuation is properly handled."""
        reference = "Hello, world!"
        hypothesis = "Hello world"
        wer = calculate_wer(reference, hypothesis)
        self.assertEqual(wer, 0.0, "Punctuation differences should not affect WER")

    def test_empty_reference(self):
        """Test WER calculation with empty reference."""
        reference = ""
        hypothesis = "some words"
        wer = calculate_wer(reference, hypothesis)
        self.assertEqual(wer, 1.0, "Empty reference with hypothesis should have WER of 1.0")

    def test_empty_hypothesis(self):
        """Test WER calculation with empty hypothesis."""
        reference = "some words"
        hypothesis = ""
        wer = calculate_wer(reference, hypothesis)
        self.assertEqual(wer, 1.0, "Reference with empty hypothesis should have WER of 1.0")

    def test_both_empty(self):
        """Test WER calculation with both empty strings."""
        reference = ""
        hypothesis = ""
        wer = calculate_wer(reference, hypothesis)
        self.assertEqual(wer, 0.0, "Both empty strings should have WER of 0.0")


if __name__ == "__main__":
    unittest.main()
