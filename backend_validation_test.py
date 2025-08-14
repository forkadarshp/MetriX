#!/usr/bin/env python3
"""
Backend Validation Test for Review Request
Specific tests for:
1. Create chained run (elevenlabs -> deepgram)
2. Verify metrics_json includes required fields
3. Test latency percentiles endpoints
"""

import requests
import json
import time
import sys
import os
from typing import Dict, Any, Optional

class BackendValidationTester:
    def __init__(self, base_url: str = "https://setup-explorer.preview.emergentagent.com"):
        self.base_url = base_url
        self.test_results = []
        self.created_run_id = None

    def log_result(self, test_name: str, success: bool, details: str = "", data: Any = None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
        if data:
            print(f"   Data: {json.dumps(data, indent=2)}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "data": data
        })

    def make_request(self, method: str, endpoint: str, data: Any = None, timeout: int = 30) -> tuple:
        """Make HTTP request"""
        url = f"{self.base_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method == 'GET':
                response = requests.get(url, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            else:
                return False, None, 0
            
            return True, response, response.status_code
        except Exception as e:
            print(f"   Request error: {str(e)}")
            return False, None, 0

    def test_1_create_chained_run(self):
        """1) Create one chained run (elevenlabs -> deepgram) to generate recent data"""
        print("\n🔍 Test 1: Creating chained run (ElevenLabs -> Deepgram)")
        
        run_data = {
            "mode": "chained",
            "vendors": ["elevenlabs", "deepgram"],
            "text_inputs": ["The quick brown fox jumps over the lazy dog for testing purposes."]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_result("Create Chained Run", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            self.created_run_id = data['run_id']
            self.log_result("Create Chained Run", True, f"Run created: {self.created_run_id}")
            
            # Wait for processing to complete
            print("   Waiting for run to complete...")
            max_wait = 120  # 2 minutes
            check_interval = 5
            
            for attempt in range(max_wait // check_interval):
                success, response, status_code = self.make_request('GET', f'/api/runs/{self.created_run_id}')
                
                if success and status_code == 200:
                    run_data = response.json()
                    run_status = run_data.get('run', {}).get('status', 'unknown')
                    
                    if run_status == 'completed':
                        print(f"   Run completed after {(attempt + 1) * check_interval} seconds")
                        return True
                    elif run_status == 'failed':
                        self.log_result("Create Chained Run", False, "Run failed during processing")
                        return False
                    else:
                        print(f"   Status: {run_status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                else:
                    time.sleep(check_interval)
            
            self.log_result("Create Chained Run", False, "Run did not complete within timeout")
            return False
            
        except Exception as e:
            self.log_result("Create Chained Run", False, f"Error: {str(e)}")
            return False

    def test_2_verify_metrics_json(self):
        """2) GET /api/runs and verify metrics_json includes required fields"""
        print("\n🔍 Test 2: Verifying metrics_json fields in most recent chained item")
        
        success, response, status_code = self.make_request('GET', '/api/runs')
        
        if not success or status_code != 200:
            self.log_result("Verify Metrics JSON", False, f"Failed to get runs: {status_code}")
            return False
        
        try:
            data = response.json()
            runs = data.get('runs', [])
            
            if not runs:
                self.log_result("Verify Metrics JSON", False, "No runs found")
                return False
            
            # Find the most recent chained run
            most_recent_chained = None
            for run in runs:
                if run.get('mode') == 'chained' and run.get('items'):
                    most_recent_chained = run
                    break
            
            if not most_recent_chained:
                self.log_result("Verify Metrics JSON", False, "No chained runs found")
                return False
            
            # Check the first item in the chained run
            items = most_recent_chained.get('items', [])
            if not items:
                self.log_result("Verify Metrics JSON", False, "No items in chained run")
                return False
            
            item = items[0]
            metrics_json_str = item.get('metrics_json', '')
            
            if not metrics_json_str:
                self.log_result("Verify Metrics JSON", False, "No metrics_json found")
                return False
            
            try:
                metrics_json = json.loads(metrics_json_str)
            except:
                self.log_result("Verify Metrics JSON", False, "Invalid JSON in metrics_json")
                return False
            
            # Check required fields
            required_fields = ['service_type', 'tts_vendor', 'stt_vendor', 'tts_model', 'stt_model', 'voice_id', 'language']
            found_fields = []
            missing_fields = []
            
            for field in required_fields:
                if field in metrics_json and metrics_json[field] is not None:
                    found_fields.append(field)
                else:
                    missing_fields.append(field)
            
            # Check if service_type is e2e
            service_type_correct = metrics_json.get('service_type') == 'e2e'
            
            if service_type_correct and len(found_fields) >= 5:  # At least 5 out of 7 fields
                self.log_result("Verify Metrics JSON", True, 
                              f"Found {len(found_fields)}/{len(required_fields)} fields. Present: {found_fields}",
                              metrics_json)
                return True
            else:
                self.log_result("Verify Metrics JSON", False, 
                              f"Missing fields: {missing_fields}. Service type: {metrics_json.get('service_type')}",
                              metrics_json)
                return False
                
        except Exception as e:
            self.log_result("Verify Metrics JSON", False, f"Error: {str(e)}")
            return False

    def test_3_latency_percentiles_e2e(self):
        """3) GET /api/dashboard/latency_percentiles with metric=e2e_latency, days=7"""
        print("\n🔍 Test 3: Testing latency percentiles for e2e_latency")
        
        success, response, status_code = self.make_request('GET', '/api/dashboard/latency_percentiles?metric=e2e_latency&days=7')
        
        if not success or status_code != 200:
            self.log_result("E2E Latency Percentiles", False, f"Request failed: {status_code}")
            return False
        
        try:
            data = response.json()
            
            # Check required fields
            required_fields = ['metric', 'days', 'count', 'p50', 'p90']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_result("E2E Latency Percentiles", False, f"Missing fields: {missing_fields}", data)
                return False
            
            # Check values
            metric_correct = data['metric'] == 'e2e_latency'
            days_correct = data['days'] == 7
            count_valid = data['count'] >= 1
            p50_valid = data['p50'] is None or isinstance(data['p50'], (int, float))
            p90_valid = data['p90'] is None or isinstance(data['p90'], (int, float))
            
            if metric_correct and days_correct and count_valid and p50_valid and p90_valid:
                self.log_result("E2E Latency Percentiles", True, 
                              f"Count: {data['count']}, P50: {data['p50']}, P90: {data['p90']}", data)
                return True
            else:
                self.log_result("E2E Latency Percentiles", False, 
                              f"Invalid values - metric: {metric_correct}, days: {days_correct}, count: {count_valid}", data)
                return False
                
        except Exception as e:
            self.log_result("E2E Latency Percentiles", False, f"Error: {str(e)}")
            return False

    def test_4_latency_percentiles_tts(self):
        """4) Repeat with metric=tts_latency"""
        print("\n🔍 Test 4: Testing latency percentiles for tts_latency")
        
        success, response, status_code = self.make_request('GET', '/api/dashboard/latency_percentiles?metric=tts_latency&days=7')
        
        if not success or status_code != 200:
            self.log_result("TTS Latency Percentiles", False, f"Request failed: {status_code}")
            return False
        
        try:
            data = response.json()
            
            # Check required fields
            required_fields = ['metric', 'days', 'count', 'p50', 'p90']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_result("TTS Latency Percentiles", False, f"Missing fields: {missing_fields}", data)
                return False
            
            # Check values
            metric_correct = data['metric'] == 'tts_latency'
            days_correct = data['days'] == 7
            count_valid = data['count'] >= 1
            p50_valid = data['p50'] is None or isinstance(data['p50'], (int, float))
            p90_valid = data['p90'] is None or isinstance(data['p90'], (int, float))
            
            if metric_correct and days_correct and count_valid and p50_valid and p90_valid:
                self.log_result("TTS Latency Percentiles", True, 
                              f"Count: {data['count']}, P50: {data['p50']}, P90: {data['p90']}", data)
                return True
            else:
                self.log_result("TTS Latency Percentiles", False, 
                              f"Invalid values - metric: {metric_correct}, days: {days_correct}, count: {count_valid}", data)
                return False
                
        except Exception as e:
            self.log_result("TTS Latency Percentiles", False, f"Error: {str(e)}")
            return False

    def test_5_latency_percentiles_stt(self):
        """5) Repeat with metric=stt_latency"""
        print("\n🔍 Test 5: Testing latency percentiles for stt_latency")
        
        success, response, status_code = self.make_request('GET', '/api/dashboard/latency_percentiles?metric=stt_latency&days=7')
        
        if not success or status_code != 200:
            self.log_result("STT Latency Percentiles", False, f"Request failed: {status_code}")
            return False
        
        try:
            data = response.json()
            
            # Check required fields
            required_fields = ['metric', 'days', 'count', 'p50', 'p90']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_result("STT Latency Percentiles", False, f"Missing fields: {missing_fields}", data)
                return False
            
            # Check values
            metric_correct = data['metric'] == 'stt_latency'
            days_correct = data['days'] == 7
            count_valid = data['count'] >= 1
            p50_valid = data['p50'] is None or isinstance(data['p50'], (int, float))
            p90_valid = data['p90'] is None or isinstance(data['p90'], (int, float))
            
            if metric_correct and days_correct and count_valid and p50_valid and p90_valid:
                self.log_result("STT Latency Percentiles", True, 
                              f"Count: {data['count']}, P50: {data['p50']}, P90: {data['p90']}", data)
                return True
            else:
                self.log_result("STT Latency Percentiles", False, 
                              f"Invalid values - metric: {metric_correct}, days: {days_correct}, count: {count_valid}", data)
                return False
                
        except Exception as e:
            self.log_result("STT Latency Percentiles", False, f"Error: {str(e)}")
            return False

    def run_validation_tests(self):
        """Run all validation tests"""
        print("🚀 Starting Backend Validation Tests for Review Request")
        print(f"Testing against: {self.base_url}")
        print("=" * 70)
        
        # Run tests in sequence
        test_1_success = self.test_1_create_chained_run()
        test_2_success = self.test_2_verify_metrics_json()
        test_3_success = self.test_3_latency_percentiles_e2e()
        test_4_success = self.test_4_latency_percentiles_tts()
        test_5_success = self.test_5_latency_percentiles_stt()
        
        # Summary
        total_tests = 5
        passed_tests = sum([test_1_success, test_2_success, test_3_success, test_4_success, test_5_success])
        
        print("\n" + "=" * 70)
        print("📊 VALIDATION TEST SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {(passed_tests / total_tests * 100):.1f}%")
        
        if passed_tests == total_tests:
            print("\n🎉 All validation tests passed!")
            return 0
        else:
            print(f"\n⚠️  {total_tests - passed_tests} test(s) failed.")
            return 1

def main():
    """Main test execution"""
    tester = BackendValidationTester()
    return tester.run_validation_tests()

if __name__ == "__main__":
    sys.exit(main())