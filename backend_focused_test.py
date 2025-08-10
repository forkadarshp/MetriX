#!/usr/bin/env python3
"""
Focused Backend Test for Review Request:
Validate isolated mode with multiple vendors and Deepgram TTS metrics
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

class FocusedBackendTester:
    def __init__(self, base_url: str = None):
        # Get base URL from environment or use default
        if base_url is None:
            base_url = os.getenv('BACKEND_URL', 'https://c78c8b4c-cad4-4870-b393-0b372628dadb.preview.emergentagent.com')
        
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_run_ids = []
        
        print(f"🎯 Focused Backend Tester initialized with base URL: {self.base_url}")

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

    def test_pre_checks(self):
        """1) Pre-checks - Ensure backend base URL is environment-configured"""
        print("\n🔍 1) Pre-checks: Backend Base URL Configuration...")
        
        # Check if base URL is environment-configured (not localhost)
        if 'localhost' in self.base_url or '127.0.0.1' in self.base_url:
            self.log_test("Pre-check: Environment URL", False, 
                        f"Base URL appears to be localhost: {self.base_url}")
            return False
        
        # Test health endpoint to verify backend is accessible
        success, response, status_code = self.make_request('GET', '/api/health')
        
        if not success:
            self.log_test("Pre-check: Backend Accessibility", False, "Health endpoint request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                if 'status' in data and data['status'] == 'healthy':
                    self.log_test("Pre-check: Backend Accessibility", True, 
                                f"Backend healthy at {self.base_url}")
                    return True
                else:
                    self.log_test("Pre-check: Backend Accessibility", False, 
                                f"Invalid health response: {data}")
            except:
                self.log_test("Pre-check: Backend Accessibility", False, "Invalid JSON response")
        else:
            self.log_test("Pre-check: Backend Accessibility", False, f"Status code: {status_code}")
        
        return False

    def test_isolated_tts_multiple_vendors(self):
        """2) Quick run (isolated TTS) with multiple vendors"""
        print("\n🔍 2) Quick run: Isolated TTS with multiple vendors...")
        
        # Exact form data as specified in review request
        form_data = {
            'text': 'This is a test for isolated TTS across multiple vendors',
            'vendors': 'elevenlabs,deepgram',
            'mode': 'isolated',
            'config': json.dumps({
                "service": "tts",
                "models": {
                    "elevenlabs": {
                        "tts_model": "eleven_flash_v2_5",
                        "voice_id": "21m00Tcm4TlvDq8ikWAM"
                    },
                    "deepgram": {
                        "tts_model": "aura-2",
                        "voice": "thalia",
                        "stt_model": "nova-3"
                    }
                }
            })
        }
        
        headers = {}  # Let requests handle form data headers
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success:
            self.log_test("Isolated TTS Multiple Vendors", False, "Request failed")
            return None
        
        if status_code == 200:
            try:
                data = response.json()
                if 'run_id' in data and 'status' in data:
                    run_id = data['run_id']
                    self.created_run_ids.append(run_id)
                    self.log_test("Isolated TTS Multiple Vendors", True, 
                                f"Run created with ID: {run_id}")
                    return run_id
                else:
                    self.log_test("Isolated TTS Multiple Vendors", False, f"Invalid response: {data}")
            except Exception as e:
                self.log_test("Isolated TTS Multiple Vendors", False, f"JSON parsing error: {str(e)}")
        else:
            try:
                error_data = response.json() if response else {}
                self.log_test("Isolated TTS Multiple Vendors", False, 
                            f"Status code: {status_code}, Error: {error_data}")
            except:
                self.log_test("Isolated TTS Multiple Vendors", False, f"Status code: {status_code}")
        
        return None

    def test_validate_metrics_and_audio(self, run_id: str):
        """3) Validate metrics for both items"""
        print("\n🔍 3) Validate metrics for both run items...")
        
        if not run_id:
            self.log_test("Metrics Validation", False, "No run ID provided")
            return False
        
        # Wait for processing to complete
        max_wait_time = 90  # 90 seconds for real API calls
        check_interval = 5
        
        for attempt in range(max_wait_time // check_interval):
            success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
            
            if success and status_code == 200:
                try:
                    data = response.json()
                    run = data['run']
                    status = run.get('status', 'unknown')
                    
                    if status == 'completed':
                        items = run.get('items', [])
                        
                        if len(items) != 2:
                            self.log_test("Metrics Validation", False, 
                                        f"Expected 2 run_items, got {len(items)}")
                            return False
                        
                        # Validate each item
                        elevenlabs_item = None
                        deepgram_item = None
                        
                        for item in items:
                            vendor = item.get('vendor', '')
                            if vendor == 'elevenlabs':
                                elevenlabs_item = item
                            elif vendor == 'deepgram':
                                deepgram_item = item
                        
                        if not elevenlabs_item or not deepgram_item:
                            self.log_test("Metrics Validation", False, 
                                        f"Missing vendor items. ElevenLabs: {bool(elevenlabs_item)}, Deepgram: {bool(deepgram_item)}")
                            return False
                        
                        # Validate ElevenLabs item
                        el_valid = self.validate_item_metrics(elevenlabs_item, 'elevenlabs')
                        
                        # Validate Deepgram item (focus on TTS metrics and duration)
                        dg_valid = self.validate_item_metrics(deepgram_item, 'deepgram')
                        
                        if el_valid and dg_valid:
                            self.log_test("Metrics Validation", True, 
                                        "Both ElevenLabs and Deepgram items validated successfully")
                            return True
                        else:
                            self.log_test("Metrics Validation", False, 
                                        f"Validation failed. ElevenLabs: {el_valid}, Deepgram: {dg_valid}")
                            return False
                    
                    elif status == 'failed':
                        self.log_test("Metrics Validation", False, "Run failed during processing")
                        return False
                    else:
                        print(f"   Waiting for processing... Status: {status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                        
                except Exception as e:
                    print(f"   Error checking run status: {str(e)}")
                    time.sleep(check_interval)
            else:
                print(f"   Error fetching run details (attempt {attempt + 1})")
                time.sleep(check_interval)
        
        self.log_test("Metrics Validation", False, "Run did not complete within timeout")
        return False

    def validate_item_metrics(self, item: Dict, vendor: str) -> bool:
        """Validate individual item metrics"""
        print(f"\n   📊 Validating {vendor} item metrics...")
        
        # a. Confirm audio_path exists and GET /api/audio/{filename} returns 200 with content-length > 5KB
        audio_path = item.get('audio_path', '')
        if not audio_path:
            print(f"   ❌ {vendor}: No audio_path found")
            return False
        
        audio_filename = audio_path.split('/')[-1]
        success, response, status_code = self.make_request('GET', f'/api/audio/{audio_filename}', headers={})
        
        if not success or status_code != 200:
            print(f"   ❌ {vendor}: Audio file not accessible (status: {status_code})")
            return False
        
        content_length = len(response.content) if response else 0
        if content_length < 5120:  # 5KB
            print(f"   ❌ {vendor}: Audio file too small ({content_length} bytes < 5KB)")
            return False
        
        print(f"   ✅ {vendor}: Audio file valid ({content_length} bytes)")
        
        # b. Confirm metrics_summary contains required metrics
        metrics = item.get('metrics', [])
        metric_names = [m.get('metric_name') for m in metrics if m.get('metric_name')]
        
        required_metrics = ['tts_latency', 'audio_duration', 'wer', 'accuracy', 'confidence']
        missing_metrics = [m for m in required_metrics if m not in metric_names]
        
        if missing_metrics:
            print(f"   ❌ {vendor}: Missing metrics: {missing_metrics}")
            return False
        
        # c. Check values are plausible
        metric_values = {}
        for metric in metrics:
            name = metric.get('metric_name')
            value = metric.get('value')
            if name and value is not None:
                metric_values[name] = float(value)
        
        # Validate ranges
        validations = []
        
        # tts_latency between 0.05s and 5s
        tts_latency = metric_values.get('tts_latency', 0)
        if 0.05 <= tts_latency <= 5.0:
            validations.append(f"tts_latency: {tts_latency}s ✅")
        else:
            validations.append(f"tts_latency: {tts_latency}s ❌ (should be 0.05-5s)")
        
        # audio_duration between 0.5s and 30s
        audio_duration = metric_values.get('audio_duration', 0)
        if 0.5 <= audio_duration <= 30.0:
            validations.append(f"audio_duration: {audio_duration}s ✅")
        else:
            validations.append(f"audio_duration: {audio_duration}s ❌ (should be 0.5-30s)")
            # Special check for Deepgram duration anomaly
            if vendor == 'deepgram' and audio_duration > 1000:
                print(f"   🚨 DEEPGRAM DURATION ANOMALY: {audio_duration}s (thousands of seconds)")
        
        # wer between 0 and 1
        wer = metric_values.get('wer', -1)
        if 0 <= wer <= 1:
            validations.append(f"wer: {wer} ✅")
        else:
            validations.append(f"wer: {wer} ❌ (should be 0-1)")
        
        # accuracy between 0 and 100
        accuracy = metric_values.get('accuracy', -1)
        if 0 <= accuracy <= 100:
            validations.append(f"accuracy: {accuracy}% ✅")
        else:
            validations.append(f"accuracy: {accuracy}% ❌ (should be 0-100)")
        
        # tts_rtf present and between 0.01x and 10x
        tts_rtf = metric_values.get('tts_rtf')
        if tts_rtf is not None:
            if 0.01 <= tts_rtf <= 10.0:
                validations.append(f"tts_rtf: {tts_rtf}x ✅")
            else:
                validations.append(f"tts_rtf: {tts_rtf}x ❌ (should be 0.01-10x)")
        else:
            validations.append(f"tts_rtf: None ⚠️ (should be present)")
        
        print(f"   📈 {vendor} metrics:")
        for validation in validations:
            print(f"      {validation}")
        
        # Check if all validations passed (no ❌)
        failed_validations = [v for v in validations if '❌' in v]
        if failed_validations:
            print(f"   ❌ {vendor}: {len(failed_validations)} metric validation(s) failed")
            return False
        
        print(f"   ✅ {vendor}: All metrics validated successfully")
        return True

    def test_deepgram_speak_regression(self):
        """4) Deepgram Speak 400 regression check"""
        print("\n🔍 4) Deepgram Speak 400 regression check...")
        
        # Create a specific Deepgram TTS test to check for HTTP 400 errors
        form_data = {
            'text': 'Testing Deepgram Speak API with aura-2 model and thalia voice',
            'vendors': 'deepgram',
            'mode': 'isolated',
            'config': json.dumps({
                "service": "tts",
                "models": {
                    "deepgram": {
                        "tts_model": "aura-2",
                        "voice": "thalia"
                    }
                }
            })
        }
        
        headers = {}
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success or status_code != 200:
            self.log_test("Deepgram Speak Regression", False, 
                        f"Failed to create Deepgram test run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
        except:
            self.log_test("Deepgram Speak Regression", False, "Invalid response format")
            return False
        
        # Wait for processing and check for errors
        time.sleep(10)
        
        success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
        if success and status_code == 200:
            try:
                data = response.json()
                run = data['run']
                items = run.get('items', [])
                
                if items:
                    item = items[0]
                    status = item.get('status', '')
                    audio_path = item.get('audio_path', '')
                    
                    if status == 'completed' and audio_path:
                        # Check if audio file was actually created (not a 400 error)
                        audio_filename = audio_path.split('/')[-1]
                        audio_success, audio_response, audio_status = self.make_request('GET', f'/api/audio/{audio_filename}', headers={})
                        
                        if audio_success and audio_status == 200:
                            content_length = len(audio_response.content) if audio_response else 0
                            if content_length > 1000:  # Reasonable audio file size
                                self.log_test("Deepgram Speak Regression", True, 
                                            f"Deepgram Speak API working correctly (HTTP 200), audio: {content_length} bytes")
                                return True
                            else:
                                self.log_test("Deepgram Speak Regression", False, 
                                            f"Audio file too small, possible API error: {content_length} bytes")
                        else:
                            self.log_test("Deepgram Speak Regression", False, 
                                        f"Cannot access generated audio file: {audio_status}")
                    else:
                        self.log_test("Deepgram Speak Regression", False, 
                                    f"Run item failed or no audio generated. Status: {status}")
                else:
                    self.log_test("Deepgram Speak Regression", False, "No items found in run")
            except Exception as e:
                self.log_test("Deepgram Speak Regression", False, f"Error parsing response: {str(e)}")
        else:
            self.log_test("Deepgram Speak Regression", False, f"Failed to get run details: {status_code}")
        
        return False

    def generate_report(self, run_id: str):
        """5) Generate detailed report"""
        print("\n🔍 5) Generating detailed report...")
        
        if not run_id:
            print("   ❌ No run ID available for report generation")
            return
        
        success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
        if not success or status_code != 200:
            print(f"   ❌ Failed to get run details for report: {status_code}")
            return
        
        try:
            data = response.json()
            run = data['run']
            items = run.get('items', [])
            
            print(f"\n📋 DETAILED REPORT")
            print("=" * 50)
            print(f"Run ID: {run_id}")
            print(f"Run Status: {run.get('status', 'unknown')}")
            print(f"Mode: {run.get('mode', 'unknown')}")
            print(f"Items Count: {len(items)}")
            
            for i, item in enumerate(items, 1):
                print(f"\n📊 Item {i} ({item.get('vendor', 'unknown')}):")
                print(f"   Item ID: {item.get('id', 'unknown')}")
                print(f"   Status: {item.get('status', 'unknown')}")
                print(f"   Audio Path: {item.get('audio_path', 'none')}")
                
                # Get audio file size
                audio_path = item.get('audio_path', '')
                if audio_path:
                    audio_filename = audio_path.split('/')[-1]
                    audio_success, audio_response, audio_status = self.make_request('GET', f'/api/audio/{audio_filename}', headers={})
                    if audio_success and audio_status == 200:
                        content_length = len(audio_response.content) if audio_response else 0
                        print(f"   Audio File Size: {content_length} bytes")
                    else:
                        print(f"   Audio File Size: Unable to access (status: {audio_status})")
                
                # Metrics table
                metrics = item.get('metrics', [])
                if metrics:
                    print(f"   Metrics:")
                    for metric in metrics:
                        name = metric.get('metric_name', 'unknown')
                        value = metric.get('value', 'unknown')
                        unit = metric.get('unit', '')
                        print(f"      {name}: {value} {unit}")
                else:
                    print(f"   Metrics: None found")
                
                # Check for anomalies
                anomalies = []
                for metric in metrics:
                    name = metric.get('metric_name', '')
                    value = metric.get('value', 0)
                    
                    if name == 'audio_duration' and float(value) > 100:
                        anomalies.append(f"Excessive audio duration: {value}s")
                    elif name == 'tts_latency' and float(value) > 10:
                        anomalies.append(f"High TTS latency: {value}s")
                    elif name == 'wer' and float(value) > 0.5:
                        anomalies.append(f"High WER: {value}")
                
                if anomalies:
                    print(f"   🚨 Anomalies:")
                    for anomaly in anomalies:
                        print(f"      {anomaly}")
                else:
                    print(f"   ✅ No anomalies detected")
            
        except Exception as e:
            print(f"   ❌ Error generating report: {str(e)}")

    def run_focused_test(self):
        """Run the focused test as specified in review request"""
        print("🎯 Starting Focused Backend Test for Review Request")
        print("=" * 60)
        print("Testing: Isolated mode with multiple vendors and Deepgram TTS metrics")
        print("=" * 60)
        
        # 1) Pre-checks
        if not self.test_pre_checks():
            print("\n❌ Pre-checks failed. Aborting test.")
            return 1
        
        # 2) Quick run (isolated TTS)
        run_id = self.test_isolated_tts_multiple_vendors()
        if not run_id:
            print("\n❌ Failed to create isolated TTS run. Aborting test.")
            return 1
        
        # 3) Validate metrics for both items
        if not self.test_validate_metrics_and_audio(run_id):
            print("\n❌ Metrics validation failed.")
            # Continue to generate report even if validation failed
        
        # 4) Deepgram Speak 400 regression check
        self.test_deepgram_speak_regression()
        
        # 5) Generate report
        self.generate_report(run_id)
        
        # Print final summary
        print("\n" + "=" * 60)
        print("📊 FOCUSED TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All focused tests passed!")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} test(s) failed.")
            return 1

def main():
    """Main test execution"""
    tester = FocusedBackendTester()
    return tester.run_focused_test()

if __name__ == "__main__":
    sys.exit(main())