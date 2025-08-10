#!/usr/bin/env python3
"""
Transcript Storage and Serving Feature Testing
Testing the new transcript artifact storage and serving functionality per review request
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

class TranscriptTester:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_run_ids = []
        self.created_items = []

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

    def wait_for_run_completion(self, run_id: str, max_wait: int = 60) -> Optional[Dict]:
        """Wait for run to complete and return run details"""
        check_interval = 3
        for attempt in range(max_wait // check_interval):
            success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
            
            if success and status_code == 200:
                try:
                    data = response.json()
                    run = data['run']
                    status = run.get('status', 'unknown')
                    
                    if status == 'completed':
                        return run
                    elif status == 'failed':
                        print(f"   Run {run_id} failed during processing")
                        return None
                    else:
                        print(f"   Waiting... Run status: {status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                except Exception as e:
                    print(f"   Error checking run status: {str(e)}")
                    time.sleep(check_interval)
            else:
                print(f"   Error fetching run details (attempt {attempt + 1})")
                time.sleep(check_interval)
        
        print(f"   Run {run_id} did not complete within {max_wait} seconds")
        return None

    def test_chained_run_transcript_storage(self):
        """Test 1: Create quick chained run and verify transcript storage + serving"""
        print("\n🔍 Test 1: Chained Run Transcript Storage & Serving...")
        
        # Create quick chained run as specified
        form_data = {
            'text': 'The quick brown fox',
            'vendors': 'elevenlabs,deepgram',
            'mode': 'chained',
            'config': json.dumps({})  # Use defaults
        }
        
        headers = {}  # Let requests handle form data headers
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success or status_code != 200:
            self.log_test("Chained Run Creation", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            print(f"   Created run ID: {run_id}")
        except:
            self.log_test("Chained Run Creation", False, "Invalid response format")
            return False
        
        # Wait for completion
        run_details = self.wait_for_run_completion(run_id, max_wait=90)
        if not run_details:
            self.log_test("Chained Run Completion", False, "Run did not complete successfully")
            return False
        
        # Check run items for transcript and audio_path
        items = run_details.get('items', [])
        if not items:
            self.log_test("Chained Run Items", False, "No items found in completed run")
            return False
        
        # Find the latest run item (should be status completed)
        latest_item = None
        for item in items:
            if item.get('status') == 'completed':
                latest_item = item
                break
        
        if not latest_item:
            self.log_test("Chained Run Item Status", False, "No completed items found")
            return False
        
        item_id = latest_item['id']
        transcript = latest_item.get('transcript', '')
        audio_path = latest_item.get('audio_path', '')
        
        self.created_items.append(item_id)
        
        # Verify transcript and audio_path are present
        if not transcript:
            self.log_test("Chained Run Transcript", False, "No transcript found in run item")
            return False
        
        if not audio_path:
            self.log_test("Chained Run Audio Path", False, "No audio_path found in run item")
            return False
        
        print(f"   Item ID: {item_id}")
        print(f"   Transcript: '{transcript}'")
        print(f"   Audio path: {audio_path}")
        
        # Check if transcript file exists on disk
        transcript_filename = f"transcript_{item_id}.txt"
        transcript_path = f"storage/transcripts/{transcript_filename}"
        
        # Try to access the transcript via API endpoint
        success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
        
        if success and status_code == 200:
            # Check content type and content
            content_type = response.headers.get('content-type', '')
            transcript_content = response.text
            
            if 'text/plain' in content_type and transcript_content.strip():
                file_size = len(transcript_content.encode('utf-8'))
                self.log_test("Chained Run Transcript Serving", True, 
                            f"Transcript served successfully: {file_size} bytes, content: '{transcript_content[:60]}...'")
                
                # Verify content matches what's in the database
                if transcript.strip() in transcript_content or transcript_content.strip() in transcript:
                    self.log_test("Chained Run Transcript Content Match", True, 
                                "Transcript file content matches database transcript")
                    return True
                else:
                    self.log_test("Chained Run Transcript Content Match", False, 
                                f"Content mismatch. DB: '{transcript}', File: '{transcript_content}'")
            else:
                self.log_test("Chained Run Transcript Serving", False, 
                            f"Wrong content type or empty content: {content_type}, length: {len(transcript_content)}")
        else:
            self.log_test("Chained Run Transcript Serving", False, 
                        f"Failed to serve transcript: HTTP {status_code}")
        
        return False

    def test_isolated_stt_transcript_storage(self):
        """Test 2: Create isolated STT run and verify transcript storage"""
        print("\n🔍 Test 2: Isolated STT Run Transcript Storage...")
        
        # Create isolated STT run
        form_data = {
            'text': 'Testing isolated STT transcript storage',
            'vendors': 'deepgram',
            'mode': 'isolated',
            'config': json.dumps({
                "service": "stt"
            })
        }
        
        headers = {}
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success or status_code != 200:
            self.log_test("Isolated STT Run Creation", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            print(f"   Created STT run ID: {run_id}")
        except:
            self.log_test("Isolated STT Run Creation", False, "Invalid response format")
            return False
        
        # Wait for completion
        run_details = self.wait_for_run_completion(run_id, max_wait=90)
        if not run_details:
            self.log_test("Isolated STT Run Completion", False, "Run did not complete successfully")
            return False
        
        # Check for completed items
        items = run_details.get('items', [])
        completed_items = [item for item in items if item.get('status') == 'completed']
        
        if not completed_items:
            self.log_test("Isolated STT Run Items", False, "No completed items found")
            return False
        
        # Check the deepgram item
        deepgram_item = None
        for item in completed_items:
            if item.get('vendor') == 'deepgram':
                deepgram_item = item
                break
        
        if not deepgram_item:
            self.log_test("Isolated STT Deepgram Item", False, "No deepgram item found")
            return False
        
        item_id = deepgram_item['id']
        transcript = deepgram_item.get('transcript', '')
        
        self.created_items.append(item_id)
        
        if not transcript:
            self.log_test("Isolated STT Transcript", False, "No transcript found in deepgram item")
            return False
        
        print(f"   STT Item ID: {item_id}")
        print(f"   STT Transcript: '{transcript}'")
        
        # Test transcript file serving
        transcript_filename = f"transcript_{item_id}.txt"
        success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
        
        if success and status_code == 200:
            content_type = response.headers.get('content-type', '')
            transcript_content = response.text
            
            if 'text/plain' in content_type and transcript_content.strip():
                self.log_test("Isolated STT Transcript Serving", True, 
                            f"STT transcript served: '{transcript_content[:60]}...'")
                return True
            else:
                self.log_test("Isolated STT Transcript Serving", False, 
                            f"Wrong content type or empty: {content_type}")
        else:
            self.log_test("Isolated STT Transcript Serving", False, 
                        f"Failed to serve STT transcript: HTTP {status_code}")
        
        return False

    def test_isolated_tts_transcript_storage(self):
        """Test 3: Create isolated TTS run and verify transcript storage"""
        print("\n🔍 Test 3: Isolated TTS Run Transcript Storage...")
        
        # Create isolated TTS run (should synthesize then evaluate via Deepgram STT)
        form_data = {
            'text': 'Testing isolated TTS with transcript evaluation',
            'vendors': 'elevenlabs',
            'mode': 'isolated',
            'config': json.dumps({
                "service": "tts"
            })
        }
        
        headers = {}
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success or status_code != 200:
            self.log_test("Isolated TTS Run Creation", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            print(f"   Created TTS run ID: {run_id}")
        except:
            self.log_test("Isolated TTS Run Creation", False, "Invalid response format")
            return False
        
        # Wait for completion (TTS evaluation takes longer)
        run_details = self.wait_for_run_completion(run_id, max_wait=120)
        if not run_details:
            self.log_test("Isolated TTS Run Completion", False, "Run did not complete successfully")
            return False
        
        # Check for completed items
        items = run_details.get('items', [])
        completed_items = [item for item in items if item.get('status') == 'completed']
        
        if not completed_items:
            self.log_test("Isolated TTS Run Items", False, "No completed items found")
            return False
        
        # Check the elevenlabs item
        elevenlabs_item = None
        for item in completed_items:
            if item.get('vendor') == 'elevenlabs':
                elevenlabs_item = item
                break
        
        if not elevenlabs_item:
            self.log_test("Isolated TTS ElevenLabs Item", False, "No elevenlabs item found")
            return False
        
        item_id = elevenlabs_item['id']
        audio_path = elevenlabs_item.get('audio_path', '')
        
        self.created_items.append(item_id)
        
        if not audio_path:
            self.log_test("Isolated TTS Audio Path", False, "No audio_path found in elevenlabs item")
            return False
        
        print(f"   TTS Item ID: {item_id}")
        print(f"   TTS Audio path: {audio_path}")
        
        # For TTS evaluation, transcript should be saved from the Deepgram evaluation
        transcript_filename = f"transcript_{item_id}.txt"
        success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
        
        if success and status_code == 200:
            content_type = response.headers.get('content-type', '')
            transcript_content = response.text
            
            if 'text/plain' in content_type and transcript_content.strip():
                self.log_test("Isolated TTS Transcript Serving", True, 
                            f"TTS evaluation transcript served: '{transcript_content[:60]}...'")
                return True
            else:
                self.log_test("Isolated TTS Transcript Serving", False, 
                            f"Wrong content type or empty: {content_type}")
        else:
            self.log_test("Isolated TTS Transcript Serving", False, 
                        f"Failed to serve TTS evaluation transcript: HTTP {status_code}")
        
        return False

    def test_frontend_contract_unchanged(self):
        """Test 4: Validate frontend contract - GET /api/runs unchanged"""
        print("\n🔍 Test 4: Frontend Contract Validation...")
        
        # Get runs list
        success, response, status_code = self.make_request('GET', '/api/runs')
        
        if not success or status_code != 200:
            self.log_test("Frontend Contract - Runs List", False, f"Failed to get runs: {status_code}")
            return False
        
        try:
            data = response.json()
            
            # Check expected structure
            if 'runs' not in data:
                self.log_test("Frontend Contract - Runs Structure", False, "Missing 'runs' key in response")
                return False
            
            runs = data['runs']
            if not isinstance(runs, list):
                self.log_test("Frontend Contract - Runs Type", False, "Runs is not a list")
                return False
            
            # Check if we have any runs (should have some from previous tests)
            if len(runs) == 0:
                self.log_test("Frontend Contract - Runs Count", False, "No runs found (expected some from tests)")
                return False
            
            # Check structure of first run
            first_run = runs[0]
            expected_run_fields = ['id', 'mode', 'status', 'started_at', 'items']
            missing_run_fields = [field for field in expected_run_fields if field not in first_run]
            
            if missing_run_fields:
                self.log_test("Frontend Contract - Run Fields", False, 
                            f"Missing run fields: {missing_run_fields}")
                return False
            
            # Check items structure
            items = first_run.get('items', [])
            if items:
                first_item = items[0]
                expected_item_fields = ['id', 'vendor', 'text_input', 'status']
                missing_item_fields = [field for field in expected_item_fields if field not in first_item]
                
                if missing_item_fields:
                    self.log_test("Frontend Contract - Item Fields", False, 
                                f"Missing item fields: {missing_item_fields}")
                    return False
            
            self.log_test("Frontend Contract - Structure Unchanged", True, 
                        f"GET /api/runs returns expected structure with {len(runs)} runs")
            
            # Test dashboard stats (should also be unchanged)
            success, response, status_code = self.make_request('GET', '/api/dashboard/stats')
            
            if success and status_code == 200:
                stats_data = response.json()
                expected_stats_fields = ['total_runs', 'completed_runs', 'total_items', 'avg_wer', 
                                       'avg_accuracy', 'avg_latency', 'success_rate']
                missing_stats_fields = [field for field in expected_stats_fields if field not in stats_data]
                
                if not missing_stats_fields:
                    self.log_test("Frontend Contract - Dashboard Stats", True, 
                                "Dashboard stats structure unchanged")
                    return True
                else:
                    self.log_test("Frontend Contract - Dashboard Stats", False, 
                                f"Missing stats fields: {missing_stats_fields}")
            else:
                self.log_test("Frontend Contract - Dashboard Stats", False, 
                            f"Failed to get dashboard stats: {status_code}")
            
        except Exception as e:
            self.log_test("Frontend Contract - JSON Parsing", False, f"JSON parsing error: {str(e)}")
        
        return False

    def run_transcript_tests(self):
        """Run all transcript storage and serving tests"""
        print("🚀 Starting Transcript Storage & Serving Tests...")
        print(f"Testing against: {self.base_url}")
        print("=" * 70)
        
        # Test 1: Chained run transcript storage + serving
        self.test_chained_run_transcript_storage()
        
        # Test 2: Isolated STT run transcript storage
        self.test_isolated_stt_transcript_storage()
        
        # Test 3: Isolated TTS run transcript storage (evaluation path)
        self.test_isolated_tts_transcript_storage()
        
        # Test 4: Frontend contract unchanged
        self.test_frontend_contract_unchanged()
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 TRANSCRIPT TESTS SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        # Print detailed results
        print("\n📋 DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"  {status}: {result['name']}")
            if result['details']:
                print(f"    → {result['details']}")
        
        # Print created resources
        if self.created_run_ids:
            print(f"\n🔧 Created Run IDs: {self.created_run_ids}")
        if self.created_items:
            print(f"🔧 Created Item IDs: {self.created_items}")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All transcript tests passed! Feature is working correctly.")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} test(s) failed. Check the details above.")
            return 1

def main():
    """Main test execution"""
    # Use the backend URL from environment or default
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:8001')
    
    tester = TranscriptTester(backend_url)
    return tester.run_transcript_tests()

if __name__ == "__main__":
    sys.exit(main())