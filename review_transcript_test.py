#!/usr/bin/env python3
"""
Comprehensive Transcript File Validation Tests - Review Request Implementation
Testing transcript files are consistently produced across modes to ensure frontend Show Transcript button works
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

class ReviewRequestTranscriptTester:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_run_ids = []
        self.per_item_results = []

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

    def wait_for_run_completion(self, run_id: str, max_wait: int = 90) -> Optional[Dict]:
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
                        print(f"   Waiting... Status: {status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                except Exception as e:
                    print(f"   Error checking run status: {str(e)}")
                    time.sleep(check_interval)
            else:
                print(f"   Error fetching run details (attempt {attempt + 1})")
                time.sleep(check_interval)
        
        print(f"   Run {run_id} did not complete within {max_wait} seconds")
        return None

    def validate_transcript_for_item(self, run_item_id: str, test_name: str) -> Dict[str, Any]:
        """Validate transcript file and API access for a specific run item"""
        result = {
            "run_item_id": run_item_id,
            "transcript_api_status": None,
            "transcript_content_preview": "",
            "file_exists_on_disk": False,
            "file_path": ""
        }
        
        # Test API access
        transcript_filename = f"transcript_{run_item_id}.txt"
        success, response, status_code = self.make_request('GET', f'/api/transcript/{transcript_filename}', headers={})
        
        result["transcript_api_status"] = status_code
        
        if success and status_code == 200:
            transcript_content = response.text if response else ""
            result["transcript_content_preview"] = transcript_content[:80] + ("..." if len(transcript_content) > 80 else "")
            
            # Check if file exists on disk (backend runs from backend/ directory)
            transcript_path = f"backend/storage/transcripts/{transcript_filename}"
            result["file_path"] = transcript_path
            result["file_exists_on_disk"] = os.path.exists(transcript_path)
            
            if result["file_exists_on_disk"] and len(transcript_content) > 0:
                self.log_test(f"{test_name} - Item {run_item_id[:8]}", True, 
                            f"✅ API: {status_code}, Content: '{result['transcript_content_preview']}', File: {transcript_path}")
                return result
            else:
                self.log_test(f"{test_name} - Item {run_item_id[:8]}", False, 
                            f"❌ API: {status_code}, File exists: {result['file_exists_on_disk']}, Content length: {len(transcript_content)}")
        else:
            self.log_test(f"{test_name} - Item {run_item_id[:8]}", False, 
                        f"❌ API returned {status_code}")
        
        return result

    def test_isolated_tts_run(self):
        """Test 1: Create isolated TTS run and validate transcript files"""
        print("\n🔍 Test 1: Isolated TTS Run (mode=isolated, service=tts, vendors=elevenlabs)")
        
        run_data = {
            "mode": "isolated",
            "vendors": ["elevenlabs"],
            "config": {"service": "tts"},
            "text_inputs": ["Testing isolated TTS transcript generation with ElevenLabs"]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("Isolated TTS - Run Creation", False, f"Failed to create run: {status_code}")
            return []
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            print(f"   Created run: {run_id}")
        except:
            self.log_test("Isolated TTS - Run Creation", False, "Invalid response format")
            return []
        
        # Wait for completion
        run = self.wait_for_run_completion(run_id, max_wait=90)
        if not run:
            self.log_test("Isolated TTS - Processing", False, "Run did not complete successfully")
            return []
        
        # Validate transcript for each item
        items = run.get('items', [])
        results = []
        for item in items:
            run_item_id = item.get('id')
            if run_item_id:
                result = self.validate_transcript_for_item(run_item_id, "Isolated TTS")
                results.append(result)
                self.per_item_results.append(result)
        
        return results

    def test_isolated_stt_run(self):
        """Test 2: Create isolated STT run and validate transcript files"""
        print("\n🔍 Test 2: Isolated STT Run (mode=isolated, service=stt, vendors=deepgram)")
        
        run_data = {
            "mode": "isolated",
            "vendors": ["deepgram"],
            "config": {"service": "stt"},
            "text_inputs": ["Testing isolated STT transcript generation with Deepgram"]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("Isolated STT - Run Creation", False, f"Failed to create run: {status_code}")
            return []
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            print(f"   Created run: {run_id}")
        except:
            self.log_test("Isolated STT - Run Creation", False, "Invalid response format")
            return []
        
        # Wait for completion
        run = self.wait_for_run_completion(run_id, max_wait=90)
        if not run:
            self.log_test("Isolated STT - Processing", False, "Run did not complete successfully")
            return []
        
        # Validate transcript for each item
        items = run.get('items', [])
        results = []
        for item in items:
            run_item_id = item.get('id')
            if run_item_id:
                result = self.validate_transcript_for_item(run_item_id, "Isolated STT")
                results.append(result)
                self.per_item_results.append(result)
        
        return results

    def test_chained_run(self):
        """Test 3: Create chained run and validate transcript files"""
        print("\n🔍 Test 3: Chained Run (mode=chained, vendors=elevenlabs,deepgram)")
        
        run_data = {
            "mode": "chained",
            "vendors": ["elevenlabs", "deepgram"],
            "text_inputs": ["Testing chained mode transcript generation end-to-end"]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("Chained Run - Run Creation", False, f"Failed to create run: {status_code}")
            return []
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            print(f"   Created run: {run_id}")
        except:
            self.log_test("Chained Run - Run Creation", False, "Invalid response format")
            return []
        
        # Wait for completion
        run = self.wait_for_run_completion(run_id, max_wait=120)
        if not run:
            self.log_test("Chained Run - Processing", False, "Run did not complete successfully")
            return []
        
        # Validate transcript for each item
        items = run.get('items', [])
        results = []
        for item in items:
            run_item_id = item.get('id')
            if run_item_id:
                result = self.validate_transcript_for_item(run_item_id, "Chained Run")
                results.append(result)
                self.per_item_results.append(result)
        
        return results

    def test_api_runs_structure(self):
        """Test 4: Confirm /api/runs structure is unchanged (no regressions)"""
        print("\n🔍 Test 4: /api/runs Structure Validation (no regressions)")
        
        success, response, status_code = self.make_request('GET', '/api/runs')
        
        if not success:
            self.log_test("API Runs Structure", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                
                # Check for required top-level structure
                if 'runs' not in data:
                    self.log_test("API Runs Structure", False, "Missing 'runs' field in response")
                    return False
                
                runs = data['runs']
                if not isinstance(runs, list):
                    self.log_test("API Runs Structure", False, "'runs' field is not a list")
                    return False
                
                # Check structure of individual runs if any exist
                if runs:
                    run = runs[0]
                    required_fields = ['id', 'mode', 'vendor_list_json', 'status', 'started_at']
                    missing_fields = [field for field in required_fields if field not in run]
                    
                    if missing_fields:
                        self.log_test("API Runs Structure", False, 
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
                                self.log_test("API Runs Structure", False, 
                                            f"Missing required fields in run item: {item_missing_fields}")
                                return False
                
                self.log_test("API Runs Structure", True, 
                            f"API structure validated. Found {len(runs)} runs with correct structure")
                return True
                
            except Exception as e:
                self.log_test("API Runs Structure", False, f"JSON parsing error: {str(e)}")
        else:
            self.log_test("API Runs Structure", False, f"Status code: {status_code}")
        
        return False

    def run_review_request_validation(self):
        """Run the comprehensive transcript validation as per review request"""
        print("🚀 TRANSCRIPT FILE VALIDATION - REVIEW REQUEST IMPLEMENTATION")
        print(f"Testing against: {self.base_url}")
        print("=" * 80)
        print("Validating transcript files are consistently produced across modes")
        print("to ensure the frontend Show Transcript button is meaningful for all items")
        print("=" * 80)
        
        # Test 1: Isolated TTS run
        tts_results = self.test_isolated_tts_run()
        
        # Test 2: Isolated STT run  
        stt_results = self.test_isolated_stt_run()
        
        # Test 3: Chained run
        chained_results = self.test_chained_run()
        
        # Test 4: API structure validation
        api_structure_ok = self.test_api_runs_structure()
        
        # Print comprehensive summary as requested
        print("\n" + "=" * 80)
        print("📊 REVIEW REQUEST VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        # Return per item results as specifically requested
        print("\n📝 PER ITEM RESULTS (as requested in review):")
        print("-" * 80)
        
        for result in self.per_item_results:
            run_item_id = result['run_item_id']
            api_status = result['transcript_api_status']
            content_preview = result['transcript_content_preview']
            file_exists = result['file_exists_on_disk']
            
            print(f"• run_item_id: {run_item_id}")
            print(f"  /api/transcript status: {api_status} + first 80 chars: '{content_preview}'")
            print(f"  storage/transcripts/transcript_{run_item_id}.txt exists on disk: {file_exists}")
            print()
        
        # Summary by test type
        print("📋 SUMMARY BY TEST TYPE:")
        print(f"1. Isolated TTS (ElevenLabs): {len(tts_results)} items tested")
        print(f"2. Isolated STT (Deepgram): {len(stt_results)} items tested")
        print(f"3. Chained (ElevenLabs→Deepgram): {len(chained_results)} items tested")
        print(f"4. /api/runs structure unchanged: {'✅ PASSED' if api_structure_ok else '❌ FAILED'}")
        
        # Final validation
        all_items_valid = all(
            result['transcript_api_status'] == 200 and 
            result['file_exists_on_disk'] and 
            len(result['transcript_content_preview']) > 0
            for result in self.per_item_results
        )
        
        if all_items_valid and api_structure_ok:
            print("\n🎉 ALL VALIDATION PASSED!")
            print("✅ Transcript files are consistently produced across all modes")
            print("✅ Frontend Show Transcript button will work for all items")
            print("✅ /api/runs structure is unchanged (no regressions)")
            return 0
        else:
            print(f"\n⚠️  VALIDATION ISSUES FOUND:")
            if not all_items_valid:
                print("❌ Some transcript files are not properly created or accessible")
            if not api_structure_ok:
                print("❌ /api/runs structure has regressions")
            return 1

def main():
    """Main test execution"""
    tester = ReviewRequestTranscriptTester()
    return tester.run_review_request_validation()

if __name__ == "__main__":
    sys.exit(main())