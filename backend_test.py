#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for TTS/STT Benchmarking Dashboard
Tests all endpoints, database operations, and vendor adapters
"""

import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any, Optional

class TTSSTTAPITester:
    def __init__(self, base_url: str = "https://9ad19b5d-33f9-4b8f-a49a-377656e2c9bc.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_run_ids = []  # Track created runs for cleanup

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

    def test_health_endpoint(self):
        """Test health check endpoint"""
        print("\n🔍 Testing Health Endpoint...")
        
        success, response, status_code = self.make_request('GET', '/api/health')
        
        if not success:
            self.log_test("Health Check", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                if 'status' in data and data['status'] == 'healthy':
                    self.log_test("Health Check", True, f"Status: {data['status']}")
                    return True
                else:
                    self.log_test("Health Check", False, f"Invalid response: {data}")
            except:
                self.log_test("Health Check", False, "Invalid JSON response")
        else:
            self.log_test("Health Check", False, f"Status code: {status_code}")
        
        return False

    def test_dashboard_stats(self):
        """Test dashboard statistics endpoint"""
        print("\n🔍 Testing Dashboard Stats...")
        
        success, response, status_code = self.make_request('GET', '/api/dashboard/stats')
        
        if not success:
            self.log_test("Dashboard Stats", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                required_fields = ['total_runs', 'completed_runs', 'total_items', 'avg_wer', 
                                 'avg_accuracy', 'avg_latency', 'success_rate']
                
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    self.log_test("Dashboard Stats", True, 
                                f"All fields present. Total runs: {data['total_runs']}")
                    return True
                else:
                    self.log_test("Dashboard Stats", False, 
                                f"Missing fields: {missing_fields}")
            except Exception as e:
                self.log_test("Dashboard Stats", False, f"JSON parsing error: {str(e)}")
        else:
            self.log_test("Dashboard Stats", False, f"Status code: {status_code}")
        
        return False

    def test_scripts_endpoint(self):
        """Test scripts endpoint"""
        print("\n🔍 Testing Scripts Endpoint...")
        
        success, response, status_code = self.make_request('GET', '/api/scripts')
        
        if not success:
            self.log_test("Scripts Endpoint", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                if 'scripts' in data and isinstance(data['scripts'], list):
                    scripts = data['scripts']
                    if len(scripts) >= 2:  # Should have banking_script and general_script
                        script_names = [s.get('name', '') for s in scripts]
                        self.log_test("Scripts Endpoint", True, 
                                    f"Found {len(scripts)} scripts: {script_names}")
                        return True
                    else:
                        self.log_test("Scripts Endpoint", False, 
                                    f"Expected at least 2 scripts, got {len(scripts)}")
                else:
                    self.log_test("Scripts Endpoint", False, "Invalid response structure")
            except Exception as e:
                self.log_test("Scripts Endpoint", False, f"JSON parsing error: {str(e)}")
        else:
            self.log_test("Scripts Endpoint", False, f"Status code: {status_code}")
        
        return False

    def test_quick_run_creation(self):
        """Test quick run creation"""
        print("\n🔍 Testing Quick Run Creation...")
        
        # Test with form data
        form_data = {
            'text': 'Hello world, this is a test of the speech recognition system.',
            'vendors': 'elevenlabs,deepgram',
            'mode': 'isolated'
        }
        
        headers = {}  # Let requests handle form data headers
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success:
            self.log_test("Quick Run Creation", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                if 'run_id' in data and 'status' in data:
                    run_id = data['run_id']
                    self.created_run_ids.append(run_id)
                    self.log_test("Quick Run Creation", True, 
                                f"Run created with ID: {run_id}")
                    return True
                else:
                    self.log_test("Quick Run Creation", False, f"Invalid response: {data}")
            except Exception as e:
                self.log_test("Quick Run Creation", False, f"JSON parsing error: {str(e)}")
        else:
            try:
                error_data = response.json() if response else {}
                self.log_test("Quick Run Creation", False, 
                            f"Status code: {status_code}, Error: {error_data}")
            except:
                self.log_test("Quick Run Creation", False, f"Status code: {status_code}")
        
        return False

    def test_batch_run_creation(self):
        """Test batch run creation"""
        print("\n🔍 Testing Batch Run Creation...")
        
        run_data = {
            "mode": "chained",
            "vendors": ["elevenlabs", "deepgram"],
            "script_ids": ["banking_script", "general_script"]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success:
            self.log_test("Batch Run Creation", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                if 'run_id' in data and 'status' in data:
                    run_id = data['run_id']
                    self.created_run_ids.append(run_id)
                    self.log_test("Batch Run Creation", True, 
                                f"Batch run created with ID: {run_id}")
                    return True
                else:
                    self.log_test("Batch Run Creation", False, f"Invalid response: {data}")
            except Exception as e:
                self.log_test("Batch Run Creation", False, f"JSON parsing error: {str(e)}")
        else:
            try:
                error_data = response.json() if response else {}
                self.log_test("Batch Run Creation", False, 
                            f"Status code: {status_code}, Error: {error_data}")
            except:
                self.log_test("Batch Run Creation", False, f"Status code: {status_code}")
        
        return False

    def test_runs_listing(self):
        """Test runs listing endpoint"""
        print("\n🔍 Testing Runs Listing...")
        
        success, response, status_code = self.make_request('GET', '/api/runs')
        
        if not success:
            self.log_test("Runs Listing", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                if 'runs' in data and isinstance(data['runs'], list):
                    runs = data['runs']
                    self.log_test("Runs Listing", True, f"Found {len(runs)} runs")
                    return True
                else:
                    self.log_test("Runs Listing", False, "Invalid response structure")
            except Exception as e:
                self.log_test("Runs Listing", False, f"JSON parsing error: {str(e)}")
        else:
            self.log_test("Runs Listing", False, f"Status code: {status_code}")
        
        return False

    def test_run_details(self):
        """Test run details endpoint"""
        print("\n🔍 Testing Run Details...")
        
        if not self.created_run_ids:
            self.log_test("Run Details", False, "No run IDs available for testing")
            return False
        
        run_id = self.created_run_ids[0]
        success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
        
        if not success:
            self.log_test("Run Details", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                if 'run' in data and 'id' in data['run']:
                    run = data['run']
                    items_count = len(run.get('items', []))
                    self.log_test("Run Details", True, 
                                f"Run details retrieved with {items_count} items")
                    return True
                else:
                    self.log_test("Run Details", False, "Invalid response structure")
            except Exception as e:
                self.log_test("Run Details", False, f"JSON parsing error: {str(e)}")
        else:
            self.log_test("Run Details", False, f"Status code: {status_code}")
        
        return False

    def test_processing_completion(self):
        """Test that runs complete processing"""
        print("\n🔍 Testing Run Processing Completion...")
        
        if not self.created_run_ids:
            self.log_test("Run Processing", False, "No run IDs available for testing")
            return False
        
        run_id = self.created_run_ids[0]
        max_wait_time = 60  # Wait up to 60 seconds
        check_interval = 5  # Check every 5 seconds
        
        for attempt in range(max_wait_time // check_interval):
            success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
            
            if success and status_code == 200:
                try:
                    data = response.json()
                    run = data['run']
                    status = run.get('status', 'unknown')
                    
                    if status == 'completed':
                        items = run.get('items', [])
                        completed_items = [item for item in items if item.get('status') == 'completed']
                        self.log_test("Run Processing", True, 
                                    f"Run completed with {len(completed_items)}/{len(items)} items processed")
                        return True
                    elif status == 'failed':
                        self.log_test("Run Processing", False, "Run failed during processing")
                        return False
                    else:
                        print(f"   Waiting... Run status: {status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                except Exception as e:
                    print(f"   Error checking run status: {str(e)}")
                    time.sleep(check_interval)
            else:
                print(f"   Error fetching run details (attempt {attempt + 1})")
                time.sleep(check_interval)
        
        self.log_test("Run Processing", False, "Run did not complete within timeout")
        return False

    def test_error_handling(self):
        """Test error handling for invalid requests"""
        print("\n🔍 Testing Error Handling...")
        
        # Test invalid run ID
        success, response, status_code = self.make_request('GET', '/api/runs/invalid-id')
        
        if status_code == 404:
            self.log_test("Error Handling - Invalid Run ID", True, "Correctly returned 404")
        else:
            self.log_test("Error Handling - Invalid Run ID", False, 
                        f"Expected 404, got {status_code}")
        
        # Test invalid quick run data
        form_data = {
            'text': '',  # Empty text should cause error
            'vendors': '',  # Empty vendors
            'mode': 'invalid_mode'
        }
        
        headers = {}
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if status_code >= 400:
            self.log_test("Error Handling - Invalid Quick Run", True, 
                        f"Correctly returned error status {status_code}")
        else:
            self.log_test("Error Handling - Invalid Quick Run", False, 
                        f"Expected error status, got {status_code}")

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting TTS/STT Backend API Testing...")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # Core endpoint tests
        self.test_health_endpoint()
        self.test_dashboard_stats()
        self.test_scripts_endpoint()
        
        # Run creation tests
        self.test_quick_run_creation()
        self.test_batch_run_creation()
        
        # Run retrieval tests
        self.test_runs_listing()
        self.test_run_details()
        
        # Processing tests
        self.test_processing_completion()
        
        # Error handling tests
        self.test_error_handling()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All tests passed! Backend is working correctly.")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} test(s) failed. Check the details above.")
            return 1

def main():
    """Main test execution"""
    tester = TTSSTTAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())