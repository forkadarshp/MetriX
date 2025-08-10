#!/usr/bin/env python3
"""
Review Request Validation Tests
Testing the specific requirements from the review request
"""

import requests
import json
import time
import sys
import os
from datetime import datetime

class ReviewRequestValidator:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.results = []

    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name}: PASSED")
        else:
            print(f"❌ {test_name}: FAILED")
        
        if details:
            print(f"   → {details}")
        
        self.results.append({
            "test": test_name,
            "success": success,
            "details": details
        })

    def make_request(self, method: str, endpoint: str, data=None, headers=None, timeout=30):
        """Make HTTP request"""
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
            
            return True, response, response.status_code
        except Exception as e:
            print(f"   Request error: {str(e)}")
            return False, None, 0

    def wait_for_completion(self, run_id: str, max_wait: int = 90):
        """Wait for run completion"""
        for attempt in range(max_wait // 3):
            success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
            
            if success and status_code == 200:
                try:
                    data = response.json()
                    run = data['run']
                    status = run.get('status', 'unknown')
                    
                    if status == 'completed':
                        return run
                    elif status == 'failed':
                        return None
                    else:
                        time.sleep(3)
                except:
                    time.sleep(3)
            else:
                time.sleep(3)
        
        return None

    def test_1_quick_chained_run(self):
        """Test 1: Create quick chained run and verify transcript artifacts"""
        print("\n🔍 Test 1: Quick Chained Run with Transcript Artifacts...")
        
        # Create quick chained run as specified
        form_data = {
            'text': 'The quick brown fox',
            'vendors': 'elevenlabs,deepgram',
            'mode': 'chained',
            'config': json.dumps({})  # Use defaults
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers={})
        
        if not success or status_code != 200:
            self.log_result("1a. Quick Chained Run Creation", False, f"HTTP {status_code}")
            return
        
        try:
            data = response.json()
            run_id = data['run_id']
            print(f"   Created run ID: {run_id}")
        except:
            self.log_result("1a. Quick Chained Run Creation", False, "Invalid response")
            return
        
        self.log_result("1a. Quick Chained Run Creation", True, f"Run ID: {run_id}")
        
        # Wait for completion
        run_details = self.wait_for_completion(run_id)
        if not run_details:
            self.log_result("1b. Run Completion", False, "Run did not complete")
            return
        
        self.log_result("1b. Run Completion", True, "Run completed successfully")
        
        # Get latest run item from GET /api/runs
        success, response, status_code = self.make_request('GET', '/api/runs')
        if not success or status_code != 200:
            self.log_result("1c. Get Runs List", False, f"HTTP {status_code}")
            return
        
        runs_data = response.json()
        runs = runs_data.get('runs', [])
        
        # Find our run (should be first/latest)
        target_run = None
        for run in runs:
            if run.get('id') == run_id:
                target_run = run
                break
        
        if not target_run:
            self.log_result("1c. Locate Run in List", False, "Run not found in list")
            return
        
        # Check for completed status and transcript/audio_path
        items = target_run.get('items', [])
        completed_items = [item for item in items if item.get('status') == 'completed']
        
        if not completed_items:
            self.log_result("1d. Completed Items", False, "No completed items found")
            return
        
        latest_item = completed_items[0]
        item_id = latest_item['id']
        transcript = latest_item.get('transcript', '')
        audio_path = latest_item.get('audio_path', '')
        
        if not transcript:
            self.log_result("1e. Transcript Present", False, "No transcript in item")
            return
        
        if not audio_path:
            self.log_result("1f. Audio Path Present", False, "No audio_path in item")
            return
        
        self.log_result("1e. Transcript Present", True, f"Transcript: '{transcript}'")
        self.log_result("1f. Audio Path Present", True, f"Audio: {audio_path}")
        
        # Verify transcript file exists on disk and is served by API
        transcript_filename = f"transcript_{item_id}.txt"
        
        # Check file exists on disk
        transcript_path = f"/app/backend/storage/transcripts/{transcript_filename}"
        if os.path.exists(transcript_path):
            with open(transcript_path, 'r') as f:
                file_content = f.read().strip()
            file_size = os.path.getsize(transcript_path)
            self.log_result("1g. Transcript File on Disk", True, f"Size: {file_size} bytes")
        else:
            self.log_result("1g. Transcript File on Disk", False, "File not found")
            return
        
        # Test API serving
        success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
        
        if success and status_code == 200:
            content_type = response.headers.get('content-type', '')
            api_content = response.text.strip()
            
            if 'text/plain' in content_type and api_content:
                self.log_result("1h. Transcript API Serving", True, 
                              f"HTTP 200, text/plain, content: '{api_content[:60]}...'")
                
                # Verify content matches
                if api_content == file_content:
                    self.log_result("1i. Content Consistency", True, "API and file content match")
                else:
                    self.log_result("1i. Content Consistency", False, 
                                  f"Mismatch: API='{api_content}' vs File='{file_content}'")
            else:
                self.log_result("1h. Transcript API Serving", False, 
                              f"Wrong content-type or empty: {content_type}")
        else:
            self.log_result("1h. Transcript API Serving", False, f"HTTP {status_code}")

    def test_2_isolated_stt_run(self):
        """Test 2: Create isolated STT run and verify transcript"""
        print("\n🔍 Test 2: Isolated STT Run with Transcript...")
        
        form_data = {
            'text': 'Testing isolated STT mode transcript storage',
            'vendors': 'deepgram',
            'mode': 'isolated',
            'config': json.dumps({"service": "stt"})
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers={})
        
        if not success or status_code != 200:
            self.log_result("2a. Isolated STT Run Creation", False, f"HTTP {status_code}")
            return
        
        try:
            data = response.json()
            run_id = data['run_id']
        except:
            self.log_result("2a. Isolated STT Run Creation", False, "Invalid response")
            return
        
        self.log_result("2a. Isolated STT Run Creation", True, f"Run ID: {run_id}")
        
        # Wait for completion
        run_details = self.wait_for_completion(run_id)
        if not run_details:
            self.log_result("2b. STT Run Completion", False, "Run did not complete")
            return
        
        # Find deepgram item
        items = run_details.get('items', [])
        deepgram_items = [item for item in items if item.get('vendor') == 'deepgram' and item.get('status') == 'completed']
        
        if not deepgram_items:
            self.log_result("2c. Deepgram STT Item", False, "No completed deepgram item")
            return
        
        item = deepgram_items[0]
        item_id = item['id']
        transcript = item.get('transcript', '')
        
        if not transcript:
            self.log_result("2d. STT Transcript", False, "No transcript in deepgram item")
            return
        
        self.log_result("2d. STT Transcript", True, f"Transcript: '{transcript}'")
        
        # Test transcript file serving
        transcript_filename = f"transcript_{item_id}.txt"
        success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
        
        if success and status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'text/plain' in content_type:
                self.log_result("2e. STT Transcript Serving", True, "HTTP 200 text/plain")
            else:
                self.log_result("2e. STT Transcript Serving", False, f"Wrong content-type: {content_type}")
        else:
            self.log_result("2e. STT Transcript Serving", False, f"HTTP {status_code}")

    def test_3_isolated_tts_run(self):
        """Test 3: Create isolated TTS run and verify transcript (evaluation path)"""
        print("\n🔍 Test 3: Isolated TTS Run with Evaluation Transcript...")
        
        form_data = {
            'text': 'Testing isolated TTS evaluation transcript',
            'vendors': 'elevenlabs',
            'mode': 'isolated',
            'config': json.dumps({"service": "tts"})
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers={})
        
        if not success or status_code != 200:
            self.log_result("3a. Isolated TTS Run Creation", False, f"HTTP {status_code}")
            return
        
        try:
            data = response.json()
            run_id = data['run_id']
        except:
            self.log_result("3a. Isolated TTS Run Creation", False, "Invalid response")
            return
        
        self.log_result("3a. Isolated TTS Run Creation", True, f"Run ID: {run_id}")
        
        # Wait for completion (TTS evaluation takes longer)
        run_details = self.wait_for_completion(run_id, max_wait=120)
        if not run_details:
            self.log_result("3b. TTS Run Completion", False, "Run did not complete")
            return
        
        # Find elevenlabs item
        items = run_details.get('items', [])
        elevenlabs_items = [item for item in items if item.get('vendor') == 'elevenlabs' and item.get('status') == 'completed']
        
        if not elevenlabs_items:
            self.log_result("3c. ElevenLabs TTS Item", False, "No completed elevenlabs item")
            return
        
        item = elevenlabs_items[0]
        item_id = item['id']
        audio_path = item.get('audio_path', '')
        
        if not audio_path:
            self.log_result("3d. TTS Audio Path", False, "No audio_path in elevenlabs item")
            return
        
        self.log_result("3d. TTS Audio Path", True, f"Audio: {audio_path}")
        
        # Test transcript file serving (from evaluation)
        transcript_filename = f"transcript_{item_id}.txt"
        success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
        
        if success and status_code == 200:
            content_type = response.headers.get('content-type', '')
            content = response.text.strip()
            if 'text/plain' in content_type and content:
                self.log_result("3e. TTS Evaluation Transcript", True, 
                              f"HTTP 200 text/plain, content: '{content[:50]}...'")
            else:
                self.log_result("3e. TTS Evaluation Transcript", False, 
                              f"Wrong content-type or empty: {content_type}")
        else:
            self.log_result("3e. TTS Evaluation Transcript", False, f"HTTP {status_code}")

    def test_4_frontend_contract(self):
        """Test 4: Validate frontend contract unchanged"""
        print("\n🔍 Test 4: Frontend Contract Validation...")
        
        # Test GET /api/runs structure
        success, response, status_code = self.make_request('GET', '/api/runs')
        
        if not success or status_code != 200:
            self.log_result("4a. GET /api/runs", False, f"HTTP {status_code}")
            return
        
        try:
            data = response.json()
            
            # Check expected structure
            if 'runs' not in data:
                self.log_result("4b. Runs Structure", False, "Missing 'runs' key")
                return
            
            runs = data['runs']
            if not isinstance(runs, list):
                self.log_result("4b. Runs Structure", False, "Runs is not a list")
                return
            
            self.log_result("4b. Runs Structure", True, f"Found {len(runs)} runs")
            
            # Check if we have items and metrics_summary (unchanged)
            if runs:
                first_run = runs[0]
                expected_fields = ['id', 'mode', 'status', 'items']
                missing_fields = [f for f in expected_fields if f not in first_run]
                
                if missing_fields:
                    self.log_result("4c. Run Fields", False, f"Missing: {missing_fields}")
                else:
                    self.log_result("4c. Run Fields", True, "All expected fields present")
                
                # Check items structure
                items = first_run.get('items', [])
                if items:
                    first_item = items[0]
                    if 'metrics_summary' in first_item:
                        self.log_result("4d. Items Structure", True, "metrics_summary field preserved")
                    else:
                        self.log_result("4d. Items Structure", False, "metrics_summary field missing")
                else:
                    self.log_result("4d. Items Structure", True, "No items to check (acceptable)")
            
        except Exception as e:
            self.log_result("4b. JSON Parsing", False, f"Error: {str(e)}")

    def run_validation(self):
        """Run all validation tests"""
        print("🚀 Review Request Validation Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 70)
        
        # Run all tests
        self.test_1_quick_chained_run()
        self.test_2_isolated_stt_run()
        self.test_3_isolated_tts_run()
        self.test_4_frontend_contract()
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 VALIDATION SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        # Print detailed results
        print("\n📋 DETAILED RESULTS:")
        for result in self.results:
            status = "✅" if result['success'] else "❌"
            print(f"  {status} {result['test']}")
            if result['details']:
                print(f"    → {result['details']}")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All validation tests passed! Review requirements met.")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} test(s) failed.")
            return 1

def main():
    validator = ReviewRequestValidator()
    return validator.run_validation()

if __name__ == "__main__":
    sys.exit(main())