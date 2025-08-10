#!/usr/bin/env python3
"""
Focused Transcript Testing for User Review Request
Testing specific isolated TTS and STT modes as requested by the user
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

class FocusedTranscriptTester:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_run_ids = []

    def log_test(self, name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}: PASSED")
        else:
            print(f"❌ {name}: FAILED - {details}")
        
        if details:
            print(f"   Details: {details}")
        
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details,
            "response_data": response_data
        })

    def make_request(self, method: str, endpoint: str, data: Any = None, 
                    headers: Optional[Dict] = None, timeout: int = 30) -> tuple:
        """Make HTTP request and return (success, response, status_code)"""
        url = f"{self.base_url}{endpoint}"
        
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                if isinstance(data, dict) and headers.get('Content-Type') == 'application/json':
                    response = requests.post(url, json=data, headers=headers, timeout=timeout)
                else:
                    response = requests.post(url, data=data, headers=headers, timeout=timeout)
            else:
                return False, None, 0
            
            return True, response, response.status_code
        except Exception as e:
            print(f"   Request error: {str(e)}")
            return False, None, 0

    def wait_for_run_completion(self, run_id: str, max_wait: int = 90) -> bool:
        """Wait for run to complete and return success status"""
        check_interval = 3
        for attempt in range(max_wait // check_interval):
            success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
            
            if success and status_code == 200:
                try:
                    data = response.json()
                    run = data['run']
                    status = run.get('status', 'unknown')
                    
                    if status == 'completed':
                        return True
                    elif status == 'failed':
                        print(f"   Run {run_id} failed during processing")
                        return False
                    else:
                        print(f"   Waiting for run completion... Status: {status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                except Exception as e:
                    print(f"   Error checking run status: {str(e)}")
                    time.sleep(check_interval)
            else:
                print(f"   Error fetching run details (attempt {attempt + 1})")
                time.sleep(check_interval)
        
        print(f"   Run {run_id} did not complete within {max_wait} seconds")
        return False

    def test_isolated_tts_mode_transcript_flow(self):
        """
        Test isolated TTS mode as per user request:
        1. User provides text input
        2. System converts to TTS using selected vendor (ElevenLabs)
        3. System tests that audio with default Deepgram STT for evaluation
        4. System saves STT transcript result properly
        5. Transcript is available via /api/transcript/{filename} endpoint
        """
        print("\n🔍 Testing Isolated TTS Mode - Complete Transcript Flow...")
        
        test_text = "This is a comprehensive test of isolated TTS mode with transcript evaluation using ElevenLabs and Deepgram."
        
        # Create isolated TTS run with ElevenLabs
        form_data = {
            'text': test_text,
            'vendors': 'elevenlabs',
            'mode': 'isolated',
            'config': json.dumps({
                "service": "tts",
                "models": {
                    "elevenlabs": {"tts_model": "eleven_flash_v2_5", "voice_id": "21m00Tcm4TlvDq8ikWAM"}
                }
            })
        }
        
        headers = {}
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success or status_code != 200:
            self.log_test("Isolated TTS - Run Creation", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            print(f"   ✓ Created TTS run: {run_id}")
        except:
            self.log_test("Isolated TTS - Run Creation", False, "Invalid response format")
            return False
        
        # Wait for processing completion
        if not self.wait_for_run_completion(run_id, max_wait=90):
            self.log_test("Isolated TTS - Processing", False, "Run did not complete")
            return False
        
        print(f"   ✓ Run completed successfully")
        
        # Get run details to verify the complete flow
        success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
        if not success or status_code != 200:
            self.log_test("Isolated TTS - Get Details", False, f"Failed to get run details: {status_code}")
            return False
        
        try:
            data = response.json()
            run = data['run']
            items = run.get('items', [])
            
            if not items:
                self.log_test("Isolated TTS - Items Check", False, "No items found in run")
                return False
            
            item = items[0]
            item_id = item.get('id')
            audio_path = item.get('audio_path', '')
            vendor = item.get('vendor', '')
            
            # Step 1: Verify TTS audio was generated by ElevenLabs
            if not audio_path or 'elevenlabs' not in audio_path:
                self.log_test("Isolated TTS - ElevenLabs TTS", False, f"No ElevenLabs audio generated: {audio_path}")
                return False
            
            print(f"   ✓ ElevenLabs TTS generated audio: {audio_path}")
            
            # Step 2: Verify vendor is correctly set
            if vendor != 'elevenlabs':
                self.log_test("Isolated TTS - Vendor Check", False, f"Expected vendor 'elevenlabs', got '{vendor}'")
                return False
            
            print(f"   ✓ Vendor correctly set: {vendor}")
            
            # Step 3: Check metrics to verify Deepgram STT evaluation was performed
            metrics = item.get('metrics', [])
            metric_names = [m.get('metric_name') for m in metrics]
            
            # Should have TTS metrics and evaluation metrics from Deepgram STT
            expected_metrics = ['tts_latency', 'audio_duration', 'wer', 'accuracy', 'confidence']
            found_metrics = [m for m in expected_metrics if m in metric_names]
            
            if len(found_metrics) < 4:  # Should have at least 4 of the 5 expected metrics
                self.log_test("Isolated TTS - Evaluation Metrics", False, 
                            f"Missing evaluation metrics. Found: {found_metrics}, Expected: {expected_metrics}")
                return False
            
            print(f"   ✓ Deepgram STT evaluation metrics found: {found_metrics}")
            
            # Step 4: Verify transcript file was saved and is accessible
            transcript_filename = f"transcript_{item_id}.txt"
            success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
            
            if not success or status_code != 200:
                self.log_test("Isolated TTS - Transcript Access", False, 
                            f"Cannot access transcript file: {status_code}")
                return False
            
            transcript_content = response.text
            if not transcript_content or len(transcript_content.strip()) == 0:
                self.log_test("Isolated TTS - Transcript Content", False, "Transcript file is empty")
                return False
            
            print(f"   ✓ Transcript file accessible: '{transcript_content.strip()}'")
            
            # Step 5: Verify transcript quality (should be similar to input text)
            original_words = set(test_text.lower().split())
            transcript_words = set(transcript_content.lower().split())
            common_words = original_words.intersection(transcript_words)
            similarity = len(common_words) / len(original_words) if original_words else 0
            
            if similarity < 0.3:  # At least 30% word overlap
                self.log_test("Isolated TTS - Transcript Quality", False, 
                            f"Poor transcript quality (similarity: {similarity:.2f})")
                return False
            
            print(f"   ✓ Transcript quality good (similarity: {similarity:.2f})")
            
            self.log_test("Isolated TTS - Complete Flow", True, 
                        f"Full TTS→STT evaluation flow working. Input: '{test_text}' → ElevenLabs TTS → Deepgram STT → Transcript: '{transcript_content.strip()}'")
            return True
                
        except Exception as e:
            self.log_test("Isolated TTS - Processing Error", False, f"Error processing results: {str(e)}")
            return False

    def test_isolated_stt_mode_transcript_flow(self):
        """
        Test isolated STT mode as per user request:
        1. User provides text input
        2. System converts to TTS using default ElevenLabs to generate audio for testing
        3. System uses that audio to test the selected STT vendor
        4. System saves transcript result properly
        5. Transcript is available via /api/transcript/{filename} endpoint
        """
        print("\n🔍 Testing Isolated STT Mode - Complete Transcript Flow...")
        
        test_text = "This is a comprehensive test of isolated STT mode using default ElevenLabs TTS followed by Deepgram STT."
        
        # Create isolated STT run with Deepgram
        form_data = {
            'text': test_text,
            'vendors': 'deepgram',
            'mode': 'isolated',
            'config': json.dumps({
                "service": "stt",
                "models": {
                    "deepgram": {"stt_model": "nova-3"},
                    "elevenlabs": {"tts_model": "eleven_flash_v2_5"}  # For initial TTS generation
                }
            })
        }
        
        headers = {}
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success or status_code != 200:
            self.log_test("Isolated STT - Run Creation", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            print(f"   ✓ Created STT run: {run_id}")
        except:
            self.log_test("Isolated STT - Run Creation", False, "Invalid response format")
            return False
        
        # Wait for processing completion
        if not self.wait_for_run_completion(run_id, max_wait=90):
            self.log_test("Isolated STT - Processing", False, "Run did not complete")
            return False
        
        print(f"   ✓ Run completed successfully")
        
        # Get run details to verify the complete flow
        success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
        if not success or status_code != 200:
            self.log_test("Isolated STT - Get Details", False, f"Failed to get run details: {status_code}")
            return False
        
        try:
            data = response.json()
            run = data['run']
            items = run.get('items', [])
            
            if not items:
                self.log_test("Isolated STT - Items Check", False, "No items found in run")
                return False
            
            item = items[0]
            item_id = item.get('id')
            audio_path = item.get('audio_path', '')
            transcript = item.get('transcript', '')
            vendor = item.get('vendor', '')
            
            # Step 1: Verify audio was generated by default ElevenLabs TTS
            if not audio_path or 'elevenlabs' not in audio_path:
                self.log_test("Isolated STT - ElevenLabs TTS", False, f"No ElevenLabs audio for testing: {audio_path}")
                return False
            
            print(f"   ✓ ElevenLabs TTS generated test audio: {audio_path}")
            
            # Step 2: Verify vendor is correctly set to the STT vendor
            if vendor != 'deepgram':
                self.log_test("Isolated STT - Vendor Check", False, f"Expected vendor 'deepgram', got '{vendor}'")
                return False
            
            print(f"   ✓ STT vendor correctly set: {vendor}")
            
            # Step 3: Verify transcript was generated by Deepgram STT
            if not transcript:
                self.log_test("Isolated STT - STT Transcript", False, "No transcript generated by Deepgram STT")
                return False
            
            print(f"   ✓ Deepgram STT generated transcript: '{transcript}'")
            
            # Step 4: Check metrics to verify STT processing
            metrics = item.get('metrics', [])
            metric_names = [m.get('metric_name') for m in metrics]
            
            # Should have STT metrics
            expected_metrics = ['stt_latency', 'wer', 'accuracy', 'confidence', 'audio_duration']
            found_metrics = [m for m in expected_metrics if m in metric_names]
            
            if len(found_metrics) < 4:  # Should have at least 4 of the 5 expected metrics
                self.log_test("Isolated STT - STT Metrics", False, 
                            f"Missing STT metrics. Found: {found_metrics}, Expected: {expected_metrics}")
                return False
            
            print(f"   ✓ STT processing metrics found: {found_metrics}")
            
            # Step 5: Verify transcript file was saved and is accessible
            transcript_filename = f"transcript_{item_id}.txt"
            success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
            
            if not success or status_code != 200:
                self.log_test("Isolated STT - Transcript Access", False, 
                            f"Cannot access transcript file: {status_code}")
                return False
            
            transcript_content = response.text
            if not transcript_content or len(transcript_content.strip()) == 0:
                self.log_test("Isolated STT - Transcript Content", False, "Transcript file is empty")
                return False
            
            print(f"   ✓ Transcript file accessible: '{transcript_content.strip()}'")
            
            # Step 6: Verify transcript file matches database transcript
            if transcript_content.strip() != transcript.strip():
                self.log_test("Isolated STT - Transcript Consistency", False, 
                            f"File content '{transcript_content.strip()}' != DB content '{transcript.strip()}'")
                return False
            
            print(f"   ✓ Transcript file matches database")
            
            # Step 7: Verify transcript quality
            original_words = set(test_text.lower().split())
            transcript_words = set(transcript_content.lower().split())
            common_words = original_words.intersection(transcript_words)
            similarity = len(common_words) / len(original_words) if original_words else 0
            
            if similarity < 0.3:  # At least 30% word overlap
                self.log_test("Isolated STT - Transcript Quality", False, 
                            f"Poor transcript quality (similarity: {similarity:.2f})")
                return False
            
            print(f"   ✓ Transcript quality good (similarity: {similarity:.2f})")
            
            self.log_test("Isolated STT - Complete Flow", True, 
                        f"Full ElevenLabs TTS→Deepgram STT flow working. Input: '{test_text}' → ElevenLabs TTS → Deepgram STT → Transcript: '{transcript_content.strip()}'")
            return True
                
        except Exception as e:
            self.log_test("Isolated STT - Processing Error", False, f"Error processing results: {str(e)}")
            return False

    def run_focused_tests(self):
        """Run the focused transcript tests as requested by the user"""
        print("🚀 Starting Focused Transcript Testing (User Review Request)...")
        print(f"Testing against: {self.base_url}")
        print("=" * 80)
        
        print("\n📋 TESTING SCOPE:")
        print("1. Isolated TTS Mode: Text → ElevenLabs TTS → Deepgram STT evaluation → Transcript storage")
        print("2. Isolated STT Mode: Text → ElevenLabs TTS → Selected STT vendor → Transcript storage")
        print("3. Transcript availability via /api/transcript/{filename} endpoint")
        print("=" * 80)
        
        # Test isolated TTS mode transcript flow
        self.test_isolated_tts_mode_transcript_flow()
        
        # Test isolated STT mode transcript flow  
        self.test_isolated_stt_mode_transcript_flow()
        
        # Print summary
        print("\n" + "=" * 80)
        print("📊 FOCUSED TRANSCRIPT TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All focused transcript tests passed!")
            print("✅ Isolated TTS mode: Text → ElevenLabs TTS → Deepgram STT evaluation → Transcript storage ✓")
            print("✅ Isolated STT mode: Text → ElevenLabs TTS → Selected STT vendor → Transcript storage ✓")
            print("✅ Transcript serving via /api/transcript/{filename} endpoint ✓")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} focused test(s) failed. Check the details above.")
            return 1

def main():
    """Main test execution"""
    # Use environment variable for base URL, default to localhost
    base_url = os.getenv('BACKEND_URL', 'http://localhost:8001')
    tester = FocusedTranscriptTester(base_url)
    return tester.run_focused_tests()

if __name__ == "__main__":
    sys.exit(main())