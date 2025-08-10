#!/usr/bin/env python3
"""
Transcript File Validation Tests for TTS/STT Benchmarking Dashboard
Testing transcript file creation and serving across all modes as per review request
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

class TranscriptValidationTester:
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
                        print(f"   Waiting for run completion... Status: {status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                except Exception as e:
                    print(f"   Error checking run status: {str(e)}")
                    time.sleep(check_interval)
            else:
                print(f"   Error fetching run details (attempt {attempt + 1})")
                time.sleep(check_interval)
        
        print(f"   Run {run_id} did not complete within {max_wait} seconds")
        return None

    def test_isolated_tts_transcript(self):
        """Test 1: Create isolated TTS run and verify transcript file creation"""
        print("\n🔍 Test 1: Isolated TTS Run - Transcript File Validation...")
        
        # Create isolated TTS run with ElevenLabs
        run_data = {
            "mode": "isolated",
            "vendors": ["elevenlabs"],
            "config": {"service": "tts"},
            "text_inputs": ["The quick brown fox jumps over the lazy dog for TTS evaluation"]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("Isolated TTS - Run Creation", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
        except:
            self.log_test("Isolated TTS - Run Creation", False, "Invalid response format")
            return False
        
        # Wait for completion
        run = self.wait_for_run_completion(run_id, max_wait=90)
        if not run:
            self.log_test("Isolated TTS - Processing", False, "Run did not complete successfully")
            return False
        
        # Check run items for transcript files
        items = run.get('items', [])
        if not items:
            self.log_test("Isolated TTS - Items", False, "No items found in completed run")
            return False
        
        # Test each item for transcript file
        for item in items:
            run_item_id = item.get('id')
            if not run_item_id:
                continue
                
            # Check if transcript file exists via API
            transcript_filename = f"transcript_{run_item_id}.txt"
            success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
            
            if success and status_code == 200:
                transcript_content = response.text if response else ""
                if len(transcript_content) > 0:
                    self.log_test("Isolated TTS - Transcript API", True, 
                                f"Transcript accessible: {transcript_filename}, Content: '{transcript_content[:80]}...'")
                    
                    # Verify file exists on disk
                    transcript_path = f"storage/transcripts/{transcript_filename}"
                    if os.path.exists(transcript_path):
                        self.log_test("Isolated TTS - Transcript File", True, 
                                    f"Transcript file exists on disk: {transcript_path}")
                        return True
                    else:
                        self.log_test("Isolated TTS - Transcript File", False, 
                                    f"Transcript file missing on disk: {transcript_path}")
                else:
                    self.log_test("Isolated TTS - Transcript Content", False, 
                                f"Empty transcript content for {transcript_filename}")
            else:
                self.log_test("Isolated TTS - Transcript API", False, 
                            f"Cannot access transcript via API: {status_code}")
        
        return False

    def test_isolated_stt_transcript(self):
        """Test 2: Create isolated STT run and verify transcript file creation"""
        print("\n🔍 Test 2: Isolated STT Run - Transcript File Validation...")
        
        # Create isolated STT run with Deepgram
        run_data = {
            "mode": "isolated",
            "vendors": ["deepgram"],
            "config": {"service": "stt"},
            "text_inputs": ["Hello world, this is a test of speech to text transcription"]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("Isolated STT - Run Creation", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
        except:
            self.log_test("Isolated STT - Run Creation", False, "Invalid response format")
            return False
        
        # Wait for completion
        run = self.wait_for_run_completion(run_id, max_wait=90)
        if not run:
            self.log_test("Isolated STT - Processing", False, "Run did not complete successfully")
            return False
        
        # Check run items for transcript files
        items = run.get('items', [])
        if not items:
            self.log_test("Isolated STT - Items", False, "No items found in completed run")
            return False
        
        # Test each item for transcript file
        for item in items:
            run_item_id = item.get('id')
            if not run_item_id:
                continue
                
            # Check if transcript file exists via API
            transcript_filename = f"transcript_{run_item_id}.txt"
            success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
            
            if success and status_code == 200:
                transcript_content = response.text if response else ""
                if len(transcript_content) > 0:
                    self.log_test("Isolated STT - Transcript API", True, 
                                f"Transcript accessible: {transcript_filename}, Content: '{transcript_content[:80]}...'")
                    
                    # Verify file exists on disk
                    transcript_path = f"storage/transcripts/{transcript_filename}"
                    if os.path.exists(transcript_path):
                        self.log_test("Isolated STT - Transcript File", True, 
                                    f"Transcript file exists on disk: {transcript_path}")
                        return True
                    else:
                        self.log_test("Isolated STT - Transcript File", False, 
                                    f"Transcript file missing on disk: {transcript_path}")
                else:
                    self.log_test("Isolated STT - Transcript Content", False, 
                                f"Empty transcript content for {transcript_filename}")
            else:
                self.log_test("Isolated STT - Transcript API", False, 
                            f"Cannot access transcript via API: {status_code}")
        
        return False

    def test_chained_mode_transcript(self):
        """Test 3: Create chained run and verify transcript file creation"""
        print("\n🔍 Test 3: Chained Mode Run - Transcript File Validation...")
        
        # Create chained run with ElevenLabs -> Deepgram
        run_data = {
            "mode": "chained",
            "vendors": ["elevenlabs", "deepgram"],
            "text_inputs": ["The quick brown fox jumps over the lazy dog for end-to-end testing"]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("Chained Mode - Run Creation", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
        except:
            self.log_test("Chained Mode - Run Creation", False, "Invalid response format")
            return False
        
        # Wait for completion
        run = self.wait_for_run_completion(run_id, max_wait=120)
        if not run:
            self.log_test("Chained Mode - Processing", False, "Run did not complete successfully")
            return False
        
        # Check run items for transcript files
        items = run.get('items', [])
        if not items:
            self.log_test("Chained Mode - Items", False, "No items found in completed run")
            return False
        
        # Test each item for transcript file
        for item in items:
            run_item_id = item.get('id')
            if not run_item_id:
                continue
                
            # Check if transcript file exists via API
            transcript_filename = f"transcript_{run_item_id}.txt"
            success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
            
            if success and status_code == 200:
                transcript_content = response.text if response else ""
                if len(transcript_content) > 0:
                    self.log_test("Chained Mode - Transcript API", True, 
                                f"Transcript accessible: {transcript_filename}, Content: '{transcript_content[:80]}...'")
                    
                    # Verify file exists on disk
                    transcript_path = f"storage/transcripts/{transcript_filename}"
                    if os.path.exists(transcript_path):
                        self.log_test("Chained Mode - Transcript File", True, 
                                    f"Transcript file exists on disk: {transcript_path}")
                        return True
                    else:
                        self.log_test("Chained Mode - Transcript File", False, 
                                    f"Transcript file missing on disk: {transcript_path}")
                else:
                    self.log_test("Chained Mode - Transcript Content", False, 
                                f"Empty transcript content for {transcript_filename}")
            else:
                self.log_test("Chained Mode - Transcript API", False, 
                            f"Cannot access transcript via API: {status_code}")
        
        return False

    def test_runs_api_structure(self):
        """Test 4: Confirm /api/runs structure is unchanged (no regressions)"""
        print("\n🔍 Test 4: /api/runs Structure Validation...")
        
        success, response, status_code = self.make_request('GET', '/api/runs')
        
        if not success:
            self.log_test("Runs API Structure", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                
                # Check for required top-level structure
                if 'runs' not in data:
                    self.log_test("Runs API Structure", False, "Missing 'runs' field in response")
                    return False
                
                runs = data['runs']
                if not isinstance(runs, list):
                    self.log_test("Runs API Structure", False, "'runs' field is not a list")
                    return False
                
                # Check structure of individual runs if any exist
                if runs:
                    run = runs[0]
                    required_fields = ['id', 'mode', 'vendor_list_json', 'status', 'started_at']
                    missing_fields = [field for field in required_fields if field not in run]
                    
                    if missing_fields:
                        self.log_test("Runs API Structure", False, 
                                    f"Missing required fields in run: {missing_fields}")
                        return False
                    
                    # Check for items structure
                    if 'items' in run:
                        items = run['items']
                        if isinstance(items, list) and items:
                            item = items[0]
                            item_required_fields = ['id', 'run_id', 'vendor', 'text_input', 'status']
                            item_missing_fields = [field for field in item_required_fields if field not in item]
                            
                            if item_missing_fields:
                                self.log_test("Runs API Structure", False, 
                                            f"Missing required fields in run item: {item_missing_fields}")
                                return False
                
                self.log_test("Runs API Structure", True, 
                            f"API structure validated. Found {len(runs)} runs with correct structure")
                return True
                
            except Exception as e:
                self.log_test("Runs API Structure", False, f"JSON parsing error: {str(e)}")
        else:
            self.log_test("Runs API Structure", False, f"Status code: {status_code}")
        
        return False

    def run_comprehensive_transcript_validation(self):
        """Run all transcript validation tests as per review request"""
        print("🚀 Starting Comprehensive Transcript File Validation...")
        print(f"Testing against: {self.base_url}")
        print("=" * 80)
        
        # Test 1: Isolated TTS run transcript validation
        test1_result = self.test_isolated_tts_transcript()
        
        # Test 2: Isolated STT run transcript validation  
        test2_result = self.test_isolated_stt_transcript()
        
        # Test 3: Chained run transcript validation
        test3_result = self.test_chained_mode_transcript()
        
        # Test 4: API structure validation
        test4_result = self.test_runs_api_structure()
        
        # Print detailed summary
        print("\n" + "=" * 80)
        print("📊 TRANSCRIPT VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        # Detailed results per test
        print("\n📋 DETAILED RESULTS:")
        print(f"1. Isolated TTS Transcript: {'✅ PASSED' if test1_result else '❌ FAILED'}")
        print(f"2. Isolated STT Transcript: {'✅ PASSED' if test2_result else '❌ FAILED'}")
        print(f"3. Chained Mode Transcript: {'✅ PASSED' if test3_result else '❌ FAILED'}")
        print(f"4. API Structure Validation: {'✅ PASSED' if test4_result else '❌ FAILED'}")
        
        # Return per item results as requested
        print("\n📝 PER ITEM RESULTS (as requested):")
        for result in self.test_results:
            if "run_item_id" in result.get("details", ""):
                print(f"- {result['name']}: {result['details']}")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All transcript validation tests passed! Feature is production-ready.")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} test(s) failed. Check the details above.")
            return 1

def main():
    """Main test execution"""
    # Check if we're in the correct directory
    if not os.path.exists("storage"):
        print("Creating storage directories...")
        os.makedirs("storage/transcripts", exist_ok=True)
    
    tester = TranscriptValidationTester()
    return tester.run_comprehensive_transcript_validation()

if __name__ == "__main__":
    sys.exit(main())