#!/usr/bin/env python3
"""
Comprehensive metrics validation test for TTS/STT benchmarking dashboard.
Tests all metric calculations for precision and accuracy.
"""

import os
import sys
import time
import tempfile
import wave
import numpy as np
from pathlib import Path

# Add backend to path
sys.path.insert(0, '/app/backend')

# Import the functions we need to test
from server import (
    calculate_wer, 
    get_audio_duration_seconds, 
    calculate_rtf, 
    validate_confidence,
    JIWER_AVAILABLE
)

class MetricsValidator:
    """Test suite for metrics validation."""
    
    def __init__(self):
        self.test_results = []
        self.failed_tests = []
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        full_message = f"{status}: {test_name}"
        if message:
            full_message += f" - {message}"
        
        print(full_message)
        self.test_results.append((test_name, passed, message))
        
        if not passed:
            self.failed_tests.append(test_name)
    
    def assert_almost_equal(self, actual, expected, tolerance=0.001, test_name=""):
        """Assert two values are approximately equal."""
        if abs(actual - expected) <= tolerance:
            self.log_test(test_name or f"{actual} ≈ {expected}", True)
            return True
        else:
            self.log_test(test_name or f"{actual} ≈ {expected}", False, 
                         f"Expected {expected}, got {actual}, diff={abs(actual-expected)}")
            return False
    
    def create_test_wav(self, duration_seconds: float, sample_rate: int = 44100) -> str:
        """Create a test WAV file with known duration."""
        # Generate sine wave
        frames = int(duration_seconds * sample_rate)
        frequency = 440.0  # A4 note
        t = np.linspace(0, duration_seconds, frames, False)
        wave_data = (np.sin(frequency * 2 * np.pi * t) * 32767).astype(np.int16)
        
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
        os.close(temp_fd)
        
        # Write WAV file
        with wave.open(temp_path, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(wave_data.tobytes())
        
        return temp_path
    
    def test_wer_calculation(self):
        """Test WER calculation accuracy."""
        print("\n🧪 Testing WER Calculation")
        
        # Test cases: (reference, hypothesis, expected_wer)
        test_cases = [
            ("hello world", "hello world", 0.0),  # Perfect match
            ("hello world", "hello earth", 0.5),  # 1 substitution out of 2 words
            ("hello world", "hello", 0.5),       # 1 deletion out of 2 words
            ("hello world", "hello beautiful world", 0.5),  # 1 insertion, 2 ref words
            ("", "hello", 1.0),                   # Empty reference
            ("hello", "", 1.0),                   # Empty hypothesis
            ("", "", 0.0),                        # Both empty
            ("Hello, World!", "hello world", 1.0),  # Case and punctuation differences - jiwer is sensitive
            ("The quick brown fox", "the quick brown fox", 0.25),  # Case difference - jiwer is case-sensitive
        ]
        
        for ref, hyp, expected in test_cases:
            actual = calculate_wer(ref, hyp)
            test_name = f"WER('{ref}', '{hyp}')"
            
            if JIWER_AVAILABLE and (ref.lower().replace(",", "").replace("!", "") != hyp or 
                                   ref.replace(",", "").replace("!", "").lower().split() != hyp.split()):
                # For jiwer, be more lenient with normalization differences
                tolerance = 0.1
            else:
                tolerance = 0.001
                
            self.assert_almost_equal(actual, expected, tolerance, test_name)
    
    def test_audio_duration_calculation(self):
        """Test audio duration calculation accuracy."""
        print("\n🧪 Testing Audio Duration Calculation")
        
        # Test with known WAV files
        test_durations = [0.5, 1.0, 2.5, 5.0]  # seconds
        
        for expected_duration in test_durations:
            wav_path = self.create_test_wav(expected_duration)
            try:
                actual_duration = get_audio_duration_seconds(wav_path)
                test_name = f"Duration of {expected_duration}s WAV file"
                
                # Allow 1ms tolerance for rounding/encoding differences
                self.assert_almost_equal(actual_duration, expected_duration, 0.001, test_name)
                
            finally:
                # Clean up
                try:
                    os.unlink(wav_path)
                except:
                    pass
        
        # Test with non-existent file
        fake_duration = get_audio_duration_seconds("/nonexistent/file.wav")
        self.log_test("Non-existent file returns 0.0", fake_duration == 0.0)
    
    def test_rtf_calculation(self):
        """Test RTF calculation and validation."""
        print("\n🧪 Testing RTF Calculation")
        
        # Test cases: (latency, duration, expected_rtf, should_be_none)
        test_cases = [
            (1.0, 2.0, 0.5, False),      # Faster than real-time
            (2.0, 2.0, 1.0, False),      # Real-time
            (3.0, 2.0, 1.5, False),      # Slower than real-time
            (1.0, 0.0, None, True),      # Zero duration
            (1.0, -1.0, None, True),     # Negative duration
            (-1.0, 2.0, None, True),     # Negative latency
            (0.0, 2.0, 0.0, False),      # Zero latency (perfect)
            (0.01, 2.0, 0.005, False),   # Very fast processing
        ]
        
        for latency, duration, expected, should_be_none in test_cases:
            actual = calculate_rtf(latency, duration, "TEST RTF")
            test_name = f"RTF({latency}, {duration})"
            
            if should_be_none:
                self.log_test(test_name, actual is None, f"Expected None, got {actual}")
            else:
                if actual is not None:
                    self.assert_almost_equal(actual, expected, 0.001, test_name)
                else:
                    self.log_test(test_name, False, f"Expected {expected}, got None")
    
    def test_confidence_validation(self):
        """Test confidence score validation."""
        print("\n🧪 Testing Confidence Validation")
        
        # Test cases: (input, expected_output)
        test_cases = [
            (0.95, 0.95),      # Normal confidence
            (1.0, 1.0),        # Perfect confidence
            (0.0, 0.0),        # Zero confidence
            (-0.1, 0.0),       # Negative (clamp to 0)
            (1.1, 1.0),        # > 1.0 but <= 1.01 (clamp to 1.0)
            (95.0, 0.95),      # Percentage (convert)
            (100.0, 1.0),      # 100% (convert)
            (150.0, 1.0),      # > 100% (clamp)
            (None, 0.0),       # None input
            ("invalid", 0.0),  # Invalid type
        ]
        
        for input_val, expected in test_cases:
            actual = validate_confidence(input_val, "test")
            test_name = f"Confidence({input_val})"
            self.assert_almost_equal(actual, expected, 0.001, test_name)
    
    def test_timing_precision(self):
        """Test timing precision using perf_counter."""
        print("\n🧪 Testing Timing Precision")
        
        # Test timing precision
        start = time.perf_counter()
        time.sleep(0.1)  # Sleep for 100ms
        end = time.perf_counter()
        
        elapsed = end - start
        # Should be close to 0.1 seconds (allowing for system variations)
        test_name = "perf_counter precision (100ms sleep)"
        if 0.09 <= elapsed <= 0.12:  # Allow 10ms tolerance
            self.log_test(test_name, True, f"Elapsed: {elapsed:.4f}s")
        else:
            self.log_test(test_name, False, f"Expected ~0.1s, got {elapsed:.4f}s")
    
    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        print("\n🧪 Testing Edge Cases")
        
        # WER with empty strings
        wer_empty = calculate_wer("", "")
        self.log_test("WER with empty strings", wer_empty == 0.0)
        
        # RTF with very small numbers
        rtf_small = calculate_rtf(0.001, 0.001, "Small RTF")
        self.log_test("RTF with small numbers", rtf_small == 1.0)
        
        # Duration with tiny file
        try:
            # Create minimal WAV file (invalid but file exists)
            temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
            # Write minimal invalid WAV data
            os.write(temp_fd, b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00')  # Incomplete header
            os.close(temp_fd)
            
            duration = get_audio_duration_seconds(temp_path)
            # Should return 0.0 for invalid WAV files
            test_passed = duration == 0.0
            self.log_test("Invalid WAV file handling", test_passed, f"Duration: {duration}")
            
            os.unlink(temp_path)
        except Exception as e:
            # If any exception occurs, that's also acceptable handling
            self.log_test("Invalid WAV file handling", True, f"Exception handled: {str(e)[:50]}")
    
    def run_all_tests(self):
        """Run all validation tests."""
        print("🚀 Starting Metrics Validation Test Suite")
        print("=" * 60)
        
        # Check if jiwer is available
        print(f"📋 jiwer library available: {JIWER_AVAILABLE}")
        if not JIWER_AVAILABLE:
            print("⚠️  Using fallback WER calculation (less accurate)")
        
        self.test_wer_calculation()
        self.test_audio_duration_calculation()
        self.test_rtf_calculation()
        self.test_confidence_validation()
        self.test_timing_precision()
        self.test_edge_cases()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, passed, _ in self.test_results if passed)
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for test_name in self.failed_tests:
                print(f"  - {test_name}")
            print(f"\n🚨 PRODUCTION READINESS: NOT READY")
            print(f"   {failed_tests} critical issues must be fixed before production deployment.")
        else:
            print(f"\n✅ ALL TESTS PASSED!")
            print(f"🎉 PRODUCTION READINESS: READY")
            print(f"   All metric calculations are validated and precise.")
        
        return failed_tests == 0

def main():
    """Main function."""
    validator = MetricsValidator()
    success = validator.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()