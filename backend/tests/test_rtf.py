"""
Unit tests for Real-Time Factor (RTF) calculation.

Tests the accuracy and edge cases of RTF calculation which measures
processing time relative to audio duration.
"""
import unittest
from app.utils import calculate_rtf


class TestRTF(unittest.TestCase):
    """Test cases for Real-Time Factor calculation."""

    def test_real_time_processing(self):
        """Test RTF calculation for real-time processing."""
        latency = 2.0  # 2 seconds processing time
        audio_duration = 2.0  # 2 seconds audio
        rtf = calculate_rtf(latency, audio_duration)
        self.assertEqual(rtf, 1.0, "Real-time processing should have RTF of 1.0")

    def test_faster_than_real_time(self):
        """Test RTF calculation for faster than real-time processing."""
        latency = 1.0  # 1 second processing time
        audio_duration = 2.0  # 2 seconds audio
        rtf = calculate_rtf(latency, audio_duration)
        self.assertEqual(rtf, 0.5, "Faster than real-time should have RTF < 1.0")

    def test_slower_than_real_time(self):
        """Test RTF calculation for slower than real-time processing."""
        latency = 3.0  # 3 seconds processing time
        audio_duration = 2.0  # 2 seconds audio
        rtf = calculate_rtf(latency, audio_duration)
        self.assertEqual(rtf, 1.5, "Slower than real-time should have RTF > 1.0")

    def test_zero_audio_duration(self):
        """Test RTF calculation with zero audio duration."""
        latency = 1.0
        audio_duration = 0.0
        rtf = calculate_rtf(latency, audio_duration)
        self.assertIsNone(rtf, "Zero audio duration should return None")

    def test_negative_audio_duration(self):
        """Test RTF calculation with negative audio duration."""
        latency = 1.0
        audio_duration = -1.0
        rtf = calculate_rtf(latency, audio_duration)
        self.assertIsNone(rtf, "Negative audio duration should return None")

    def test_negative_latency(self):
        """Test RTF calculation with negative latency."""
        latency = -1.0
        audio_duration = 2.0
        rtf = calculate_rtf(latency, audio_duration)
        self.assertIsNone(rtf, "Negative latency should return None")

    def test_zero_latency(self):
        """Test RTF calculation with zero latency."""
        latency = 0.0
        audio_duration = 2.0
        rtf = calculate_rtf(latency, audio_duration)
        self.assertEqual(rtf, 0.0, "Zero latency should have RTF of 0.0")

    def test_very_high_rtf(self):
        """Test RTF calculation with very high RTF (should still return value but log warning)."""
        latency = 200.0  # 200 seconds processing time
        audio_duration = 1.0  # 1 second audio
        rtf = calculate_rtf(latency, audio_duration)
        self.assertEqual(rtf, 200.0, "Very high RTF should still return calculated value")

    def test_very_low_rtf(self):
        """Test RTF calculation with very low RTF."""
        latency = 0.001  # 1ms processing time
        audio_duration = 2.0  # 2 seconds audio
        rtf = calculate_rtf(latency, audio_duration)
        self.assertEqual(rtf, 0.0005, "Very low RTF should return calculated value")

    def test_custom_metric_name(self):
        """Test RTF calculation with custom metric name for logging."""
        latency = 1.0
        audio_duration = 2.0
        rtf = calculate_rtf(latency, audio_duration, "Custom RTF")
        self.assertEqual(rtf, 0.5, "Custom metric name should not affect calculation")


if __name__ == "__main__":
    unittest.main()
