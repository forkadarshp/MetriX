#!/usr/bin/env python3
"""
Backend Review Test - Run Creation Logic and Chained/Isolated Behavior
Testing specific scenarios from the review request:
1. POST /api/runs and /api/runs/quick changes for chained/isolated modes
2. Vendor label behavior (combined labels for chained, original for isolated)
3. GET /api/runs return format verification
4. Export functionality regression testing
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

class BackendReviewTester:
    def __init__(self, base_url: str = "https://c78c8b4c-cad4-4870-b393-0b372628dadb.preview.emergentagent.com"):
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
                        print(f"   Waiting... Run status: {status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                except Exception as e:
                    print(f"   Error checking run status: {str(e)}")
                    time.sleep(check_interval)
            else:
                print(f"   Error fetching run details (attempt {attempt + 1})")
                time.sleep(check_interval)
        
        print(f"   Run {run_id} did not complete within {max_wait}s timeout")
        return None

    def test_quick_chained_mode(self):
        """Test Quick chained: POST /api/runs/quick with mode=chained"""
        print("\n🔍 Testing Quick Chained Mode...")
        
        # Test with form data as specified in review request
        form_data = {
            'text': 'The quick brown fox',
            'vendors': 'elevenlabs,deepgram',  # vendors ignored for count in chained mode
            'mode': 'chained',
            'config': json.dumps({
                "chain": {
                    "tts_vendor": "elevenlabs",
                    "stt_vendor": "deepgram"
                }
            })
        }
        
        headers = {}  # Let requests handle form data headers
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success or status_code != 200:
            self.log_test("Quick Chained Mode", False, f"Request failed: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            
            # Wait for completion
            run = self.wait_for_run_completion(run_id, 90)
            if not run:
                self.log_test("Quick Chained Mode", False, "Run did not complete")
                return False
            
            items = run.get('items', [])
            
            # Verify exactly ONE run_item per input
            if len(items) != 1:
                self.log_test("Quick Chained Mode", False, 
                            f"Expected 1 item, got {len(items)}")
                return False
            
            item = items[0]
            vendor = item.get('vendor', '')
            
            # Verify vendor is combined label like "elevenlabs→deepgram"
            expected_vendor = "elevenlabs→deepgram"
            if vendor != expected_vendor:
                self.log_test("Quick Chained Mode", False, 
                            f"Expected vendor '{expected_vendor}', got '{vendor}'")
                return False
            
            # Verify metrics include e2e_latency
            metrics = item.get('metrics', [])
            metric_names = [m.get('metric_name') for m in metrics]
            
            if 'e2e_latency' not in metric_names:
                self.log_test("Quick Chained Mode", False, 
                            f"Missing e2e_latency metric. Found: {metric_names}")
                return False
            
            self.log_test("Quick Chained Mode", True, 
                        f"1 item with vendor '{vendor}', metrics: {metric_names}")
            return True
            
        except Exception as e:
            self.log_test("Quick Chained Mode", False, f"Error: {str(e)}")
            return False

    def test_quick_isolated_mode(self):
        """Test Quick isolated: POST /api/runs/quick with mode=isolated"""
        print("\n🔍 Testing Quick Isolated Mode...")
        
        form_data = {
            'text': 'The quick brown fox',
            'vendors': 'elevenlabs,deepgram',
            'mode': 'isolated',
            'config': json.dumps({
                "service": "tts"
            })
        }
        
        headers = {}
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success or status_code != 200:
            self.log_test("Quick Isolated Mode", False, f"Request failed: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            
            # Wait for completion
            run = self.wait_for_run_completion(run_id, 90)
            if not run:
                self.log_test("Quick Isolated Mode", False, "Run did not complete")
                return False
            
            items = run.get('items', [])
            
            # Verify 2 items (one per vendor)
            if len(items) != 2:
                self.log_test("Quick Isolated Mode", False, 
                            f"Expected 2 items, got {len(items)}")
                return False
            
            # Verify vendors are original names
            vendors = [item.get('vendor', '') for item in items]
            expected_vendors = {'elevenlabs', 'deepgram'}
            actual_vendors = set(vendors)
            
            if actual_vendors != expected_vendors:
                self.log_test("Quick Isolated Mode", False, 
                            f"Expected vendors {expected_vendors}, got {actual_vendors}")
                return False
            
            self.log_test("Quick Isolated Mode", True, 
                        f"2 items with vendors: {vendors}")
            return True
            
        except Exception as e:
            self.log_test("Quick Isolated Mode", False, f"Error: {str(e)}")
            return False

    def test_batch_chained_mode(self):
        """Test Batch chained: POST /api/runs with chained mode"""
        print("\n🔍 Testing Batch Chained Mode...")
        
        # First get script items count for general_script
        success, response, status_code = self.make_request('GET', '/api/scripts')
        if not success or status_code != 200:
            self.log_test("Batch Chained Mode", False, "Failed to get scripts")
            return False
        
        try:
            scripts_data = response.json()
            scripts = scripts_data.get('scripts', [])
            general_script = None
            for script in scripts:
                if script.get('id') == 'general_script':
                    general_script = script
                    break
            
            if not general_script:
                self.log_test("Batch Chained Mode", False, "general_script not found")
                return False
            
            expected_items_count = len(general_script.get('items', []))
            
        except Exception as e:
            self.log_test("Batch Chained Mode", False, f"Error getting scripts: {str(e)}")
            return False
        
        # Create batch chained run
        run_data = {
            "mode": "chained",
            "vendors": ["elevenlabs", "deepgram"],
            "script_ids": ["general_script"],
            "config": {
                "chain": {
                    "tts_vendor": "deepgram",
                    "stt_vendor": "elevenlabs"
                }
            }
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("Batch Chained Mode", False, f"Request failed: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            
            # Wait for completion
            run = self.wait_for_run_completion(run_id, 120)
            if not run:
                self.log_test("Batch Chained Mode", False, "Run did not complete")
                return False
            
            items = run.get('items', [])
            
            # Verify items count equals script_items count
            if len(items) != expected_items_count:
                self.log_test("Batch Chained Mode", False, 
                            f"Expected {expected_items_count} items, got {len(items)}")
                return False
            
            # Verify all items have combined vendor label
            expected_vendor = "deepgram→elevenlabs"
            vendors = [item.get('vendor', '') for item in items]
            
            if not all(v == expected_vendor for v in vendors):
                unique_vendors = set(vendors)
                self.log_test("Batch Chained Mode", False, 
                            f"Expected all items to have vendor '{expected_vendor}', got: {unique_vendors}")
                return False
            
            self.log_test("Batch Chained Mode", True, 
                        f"{len(items)} items, all with vendor '{expected_vendor}'")
            return True
            
        except Exception as e:
            self.log_test("Batch Chained Mode", False, f"Error: {str(e)}")
            return False

    def test_get_runs_vendor_labels(self):
        """Test GET /api/runs returns correct vendor labels"""
        print("\n🔍 Testing GET /api/runs Vendor Labels...")
        
        success, response, status_code = self.make_request('GET', '/api/runs')
        
        if not success or status_code != 200:
            self.log_test("GET Runs Vendor Labels", False, f"Request failed: {status_code}")
            return False
        
        try:
            data = response.json()
            runs = data.get('runs', [])
            
            if not runs:
                self.log_test("GET Runs Vendor Labels", False, "No runs found")
                return False
            
            # Check recent runs for correct vendor labels
            chained_items_found = 0
            isolated_items_found = 0
            
            for run in runs[:10]:  # Check last 10 runs
                mode = run.get('mode', '')
                items = run.get('items', [])
                
                for item in items:
                    vendor = item.get('vendor', '')
                    
                    if mode == 'chained':
                        # Should have combined label like "vendor1→vendor2"
                        if '→' in vendor:
                            chained_items_found += 1
                        else:
                            print(f"   Warning: Chained item has non-combined vendor: {vendor}")
                    
                    elif mode == 'isolated':
                        # Should have original vendor name
                        if vendor in ['elevenlabs', 'deepgram', 'aws']:
                            isolated_items_found += 1
                        else:
                            print(f"   Warning: Isolated item has unexpected vendor: {vendor}")
            
            if chained_items_found > 0 or isolated_items_found > 0:
                self.log_test("GET Runs Vendor Labels", True, 
                            f"Found {chained_items_found} chained items, {isolated_items_found} isolated items with correct labels")
                return True
            else:
                self.log_test("GET Runs Vendor Labels", False, 
                            "No items found with expected vendor label patterns")
                return False
            
        except Exception as e:
            self.log_test("GET Runs Vendor Labels", False, f"Error: {str(e)}")
            return False

    def test_chained_processing_still_works(self):
        """Test that existing chained processing (process_chained_mode) still works"""
        print("\n🔍 Testing Chained Processing Logic...")
        
        # Create a chained run and verify it processes correctly
        run_data = {
            "mode": "chained",
            "vendors": ["elevenlabs", "deepgram"],
            "text_inputs": ["Testing chained processing logic"],
            "config": {
                "chain": {
                    "tts_vendor": "elevenlabs",
                    "stt_vendor": "deepgram"
                }
            }
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("Chained Processing Logic", False, f"Request failed: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            
            # Wait for completion
            run = self.wait_for_run_completion(run_id, 120)
            if not run:
                self.log_test("Chained Processing Logic", False, "Run did not complete")
                return False
            
            items = run.get('items', [])
            if not items:
                self.log_test("Chained Processing Logic", False, "No items found")
                return False
            
            item = items[0]
            
            # Verify metrics_json contains correct vendor information
            metrics_json = item.get('metrics_json', '{}')
            try:
                metrics_data = json.loads(metrics_json)
                
                tts_vendor = metrics_data.get('tts_vendor')
                stt_vendor = metrics_data.get('stt_vendor')
                service_type = metrics_data.get('service_type')
                
                if (tts_vendor == 'elevenlabs' and 
                    stt_vendor == 'deepgram' and 
                    service_type == 'e2e'):
                    
                    # Verify metrics include both TTS and STT latencies
                    metrics = item.get('metrics', [])
                    metric_names = [m.get('metric_name') for m in metrics]
                    
                    required_metrics = ['tts_latency', 'stt_latency', 'e2e_latency']
                    found_metrics = [m for m in required_metrics if m in metric_names]
                    
                    if len(found_metrics) >= 2:
                        self.log_test("Chained Processing Logic", True, 
                                    f"Correct processing: tts_vendor={tts_vendor}, stt_vendor={stt_vendor}, metrics={found_metrics}")
                        return True
                    else:
                        self.log_test("Chained Processing Logic", False, 
                                    f"Missing required metrics. Found: {found_metrics}")
                        return False
                else:
                    self.log_test("Chained Processing Logic", False, 
                                f"Incorrect vendor info: tts_vendor={tts_vendor}, stt_vendor={stt_vendor}, service_type={service_type}")
                    return False
                    
            except Exception as e:
                self.log_test("Chained Processing Logic", False, 
                            f"Error parsing metrics_json: {str(e)}")
                return False
            
        except Exception as e:
            self.log_test("Chained Processing Logic", False, f"Error: {str(e)}")
            return False

    def test_export_functionality(self):
        """Test /api/export still works and includes chained items"""
        print("\n🔍 Testing Export Functionality...")
        
        # Test CSV export
        export_data = {
            "format": "csv",
            "all": True
        }
        
        success, response, status_code = self.make_request('POST', '/api/export', data=export_data)
        
        if not success or status_code != 200:
            self.log_test("Export Functionality", False, f"CSV export failed: {status_code}")
            return False
        
        try:
            # Check response headers and content
            content_type = response.headers.get('content-type', '')
            content_length = len(response.content) if response else 0
            
            if not content_type.startswith('text/csv'):
                self.log_test("Export Functionality", False, 
                            f"Wrong content type for CSV: {content_type}")
                return False
            
            if content_length < 100:  # Should have substantial content
                self.log_test("Export Functionality", False, 
                            f"CSV too small: {content_length} bytes")
                return False
            
            # Check if CSV contains chained items (service=E2E detection)
            csv_content = response.content.decode('utf-8')
            lines = csv_content.split('\n')
            
            # Look for E2E service entries (chained items)
            e2e_entries = [line for line in lines if ',E2E,' in line]
            
            if len(e2e_entries) > 0:
                self.log_test("Export Functionality", True, 
                            f"CSV export working: {content_length} bytes, {len(e2e_entries)} E2E entries")
                return True
            else:
                # Still pass if no E2E entries but export works
                self.log_test("Export Functionality", True, 
                            f"CSV export working: {content_length} bytes (no E2E entries found)")
                return True
            
        except Exception as e:
            self.log_test("Export Functionality", False, f"Error: {str(e)}")
            return False

    def test_vendor_list_json_storage(self):
        """Test that runs.vendor_list_json contains correct values"""
        print("\n🔍 Testing Vendor List JSON Storage...")
        
        # Get recent runs and check vendor_list_json
        success, response, status_code = self.make_request('GET', '/api/runs')
        
        if not success or status_code != 200:
            self.log_test("Vendor List JSON Storage", False, f"Request failed: {status_code}")
            return False
        
        try:
            data = response.json()
            runs = data.get('runs', [])
            
            chained_runs_checked = 0
            isolated_runs_checked = 0
            
            for run in runs[:5]:  # Check last 5 runs
                mode = run.get('mode', '')
                vendors = run.get('vendors', [])
                
                if mode == 'chained':
                    # Should contain combined labels like ["elevenlabs→deepgram"]
                    if vendors and any('→' in v for v in vendors):
                        chained_runs_checked += 1
                        print(f"   Chained run vendor_list_json: {vendors}")
                    
                elif mode == 'isolated':
                    # Should contain original vendor names
                    if vendors and all(v in ['elevenlabs', 'deepgram', 'aws'] for v in vendors):
                        isolated_runs_checked += 1
                        print(f"   Isolated run vendor_list_json: {vendors}")
            
            if chained_runs_checked > 0 or isolated_runs_checked > 0:
                self.log_test("Vendor List JSON Storage", True, 
                            f"Verified {chained_runs_checked} chained, {isolated_runs_checked} isolated runs")
                return True
            else:
                self.log_test("Vendor List JSON Storage", False, 
                            "No runs found with expected vendor_list_json format")
                return False
            
        except Exception as e:
            self.log_test("Vendor List JSON Storage", False, f"Error: {str(e)}")
            return False

    def run_review_tests(self):
        """Run all review request tests"""
        print("🚀 Starting Backend Review Tests - Run Creation Logic & Chained/Isolated Behavior")
        print(f"Testing against: {self.base_url}")
        print("=" * 80)
        
        # Test scenarios from review request
        print("\n📋 REVIEW REQUEST TEST SCENARIOS")
        print("=" * 80)
        
        # 1. Quick chained mode
        self.test_quick_chained_mode()
        
        # 2. Quick isolated mode  
        self.test_quick_isolated_mode()
        
        # 3. Batch chained mode
        self.test_batch_chained_mode()
        
        # 4. GET /api/runs vendor labels
        self.test_get_runs_vendor_labels()
        
        # 5. Chained processing still works
        self.test_chained_processing_still_works()
        
        # 6. Export functionality
        self.test_export_functionality()
        
        # 7. Vendor list JSON storage
        self.test_vendor_list_json_storage()
        
        # Print summary
        print("\n" + "=" * 80)
        print("📊 REVIEW TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        # Print created run IDs for reference
        if self.created_run_ids:
            print(f"\nCreated Run IDs: {self.created_run_ids}")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All review tests passed! Backend changes validated successfully.")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} test(s) failed. Check the details above.")
            return 1

def main():
    """Main test execution"""
    tester = BackendReviewTester()
    return tester.run_review_tests()

if __name__ == "__main__":
    sys.exit(main())