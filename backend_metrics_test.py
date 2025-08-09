#!/usr/bin/env python3
"""
Focused Backend Testing for Latency Metrics, RTF, Dashboard Stats, and Export
Based on specific review request requirements
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

class MetricsAPITester:
    def __init__(self, base_url: str = None):
        # Prefer explicit argument, then env vars, then localhost
        env_base = (
            base_url
            or os.environ.get("BACKEND_BASE_URL")
            or os.environ.get("REACT_APP_BACKEND_URL")
            or "http://localhost:8001"
        )
        # Trim trailing slash if any
        self.base_url = env_base.rstrip("/")
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
                    headers: Optional[Dict] = None, timeout: int = 60) -> tuple:
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

    def create_chained_run_and_wait(self, vendors: List[str], text: str = "The quick brown fox jumps over the lazy dog") -> Optional[Dict]:
        """Create a chained run with specified vendors and wait for completion"""
        print(f"\n🔄 Creating chained run with vendors: {vendors}")
        
        run_data = {
            "mode": "chained",
            "vendors": vendors,
            "text_inputs": [text]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            print(f"   Failed to create run: {status_code}")
            return None
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            print(f"   Created run: {run_id}")
        except:
            print("   Invalid response format")
            return None
        
        # Poll until completed
        max_wait_time = 120  # 2 minutes
        check_interval = 5
        
        for attempt in range(max_wait_time // check_interval):
            success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
            
            if success and status_code == 200:
                try:
                    data = response.json()
                    run = data['run']
                    status = run.get('status', 'unknown')
                    
                    if status == 'completed':
                        print(f"   Run completed after {(attempt + 1) * check_interval}s")
                        return run
                    elif status == 'failed':
                        print("   Run failed during processing")
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
        
        print("   Run did not complete within timeout")
        return None

    def create_isolated_run_and_wait(self, vendor: str, text: str = "Hello world test") -> Optional[Dict]:
        """Create an isolated run with specified vendor and wait for completion"""
        print(f"\n🔄 Creating isolated run with vendor: {vendor}")
        
        run_data = {
            "mode": "isolated",
            "vendors": [vendor],
            "text_inputs": [text]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            print(f"   Failed to create run: {status_code}")
            return None
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
            print(f"   Created run: {run_id}")
        except:
            print("   Invalid response format")
            return None
        
        # Poll until completed
        max_wait_time = 90
        check_interval = 5
        
        for attempt in range(max_wait_time // check_interval):
            success, response, status_code = self.make_request('GET', f'/api/runs/{run_id}')
            
            if success and status_code == 200:
                try:
                    data = response.json()
                    run = data['run']
                    status = run.get('status', 'unknown')
                    
                    if status == 'completed':
                        print(f"   Run completed after {(attempt + 1) * check_interval}s")
                        return run
                    elif status == 'failed':
                        print("   Run failed during processing")
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
        
        print("   Run did not complete within timeout")
        return None

    def extract_metrics_from_run(self, run: Dict) -> Dict[str, Dict]:
        """Extract metrics from run items"""
        metrics_by_item = {}
        
        for item in run.get('items', []):
            item_id = item.get('id')
            vendor = item.get('vendor')
            metrics = {}
            
            # Extract from metrics field if available
            if 'metrics' in item:
                for metric in item['metrics']:
                    metrics[metric['metric_name']] = metric['value']
            
            # Also extract from metrics_summary string
            metrics_summary = item.get('metrics_summary', '')
            if metrics_summary:
                for kv in metrics_summary.split('|'):
                    if ':' in kv:
                        k, v = kv.split(':', 1)
                        try:
                            metrics[k] = float(v)
                        except:
                            metrics[k] = v
            
            metrics_by_item[item_id] = {
                'vendor': vendor,
                'metrics': metrics,
                'audio_path': item.get('audio_path'),
                'transcript': item.get('transcript')
            }
        
        return metrics_by_item

    def test_isolated_tts_latency_correctness(self):
        """Test 1: In isolated TTS runs, ensure only tts_latency is stored and not generic latency"""
        print("\n🔍 Testing Isolated TTS Latency Correctness...")
        
        # Test ElevenLabs TTS isolated
        run = self.create_isolated_run_and_wait("elevenlabs", "Testing isolated TTS latency metrics")
        
        if not run:
            self.log_test("Isolated TTS Latency", False, "Failed to create/complete run")
            return False
        
        metrics_data = self.extract_metrics_from_run(run)
        
        for item_id, data in metrics_data.items():
            metrics = data['metrics']
            vendor = data['vendor']
            
            if vendor == 'elevenlabs':
                # Should have tts_latency but not generic latency or stt_latency
                has_tts_latency = 'tts_latency' in metrics
                has_generic_latency = 'latency' in metrics
                has_stt_latency = 'stt_latency' in metrics
                
                if has_tts_latency and not has_generic_latency and not has_stt_latency:
                    tts_latency = metrics['tts_latency']
                    self.log_test("Isolated TTS Latency", True, 
                                f"Correct metrics for {vendor}: tts_latency={tts_latency}s, no generic/stt latency")
                    return True
                else:
                    self.log_test("Isolated TTS Latency", False, 
                                f"Incorrect metrics for {vendor}: tts_latency={has_tts_latency}, generic={has_generic_latency}, stt={has_stt_latency}")
                    return False
        
        self.log_test("Isolated TTS Latency", False, "No ElevenLabs items found in run")
        return False

    def test_isolated_stt_latency_correctness(self):
        """Test 2: In isolated STT runs, ensure stt_latency is stored"""
        print("\n🔍 Testing Isolated STT Latency Correctness...")
        
        # Test Deepgram STT isolated
        run = self.create_isolated_run_and_wait("deepgram", "Testing isolated STT latency metrics")
        
        if not run:
            self.log_test("Isolated STT Latency", False, "Failed to create/complete run")
            return False
        
        metrics_data = self.extract_metrics_from_run(run)
        
        for item_id, data in metrics_data.items():
            metrics = data['metrics']
            vendor = data['vendor']
            
            if vendor == 'deepgram':
                # Should have stt_latency
                has_stt_latency = 'stt_latency' in metrics
                
                if has_stt_latency:
                    stt_latency = metrics['stt_latency']
                    self.log_test("Isolated STT Latency", True, 
                                f"Correct metrics for {vendor}: stt_latency={stt_latency}s")
                    return True
                else:
                    self.log_test("Isolated STT Latency", False, 
                                f"Missing stt_latency for {vendor}. Available metrics: {list(metrics.keys())}")
                    return False
        
        self.log_test("Isolated STT Latency", False, "No Deepgram items found in run")
        return False

    def test_chained_latency_correctness(self):
        """Test 3: In chained runs, ensure tts_latency + stt_latency = e2e_latency within ~20ms"""
        print("\n🔍 Testing Chained Latency Correctness...")
        
        # Create chained run with elevenlabs,deepgram as requested
        run = self.create_chained_run_and_wait(["elevenlabs", "deepgram"], "Testing chained latency metrics accuracy")
        
        if not run:
            self.log_test("Chained Latency Correctness", False, "Failed to create/complete run")
            return False
        
        metrics_data = self.extract_metrics_from_run(run)
        
        for item_id, data in metrics_data.items():
            metrics = data['metrics']
            
            # Should have all three latency metrics
            tts_latency = metrics.get('tts_latency')
            stt_latency = metrics.get('stt_latency')
            e2e_latency = metrics.get('e2e_latency')
            
            if tts_latency is not None and stt_latency is not None and e2e_latency is not None:
                calculated_e2e = tts_latency + stt_latency
                difference = abs(e2e_latency - calculated_e2e)
                tolerance = 0.02  # 20ms tolerance
                
                if difference <= tolerance:
                    self.log_test("Chained Latency Correctness", True, 
                                f"Latency math correct: TTS({tts_latency}s) + STT({stt_latency}s) = E2E({e2e_latency}s), diff={difference:.3f}s")
                    return True
                else:
                    self.log_test("Chained Latency Correctness", False, 
                                f"Latency math incorrect: TTS({tts_latency}s) + STT({stt_latency}s) ≠ E2E({e2e_latency}s), diff={difference:.3f}s > {tolerance}s")
                    return False
            else:
                self.log_test("Chained Latency Correctness", False, 
                            f"Missing latency metrics: TTS={tts_latency}, STT={stt_latency}, E2E={e2e_latency}")
                return False
        
        self.log_test("Chained Latency Correctness", False, "No items found in chained run")
        return False

    def test_rtf_computation(self):
        """Test 4: RTF computed - tts_rtf and/or stt_rtf present when audio_duration > 0 and values reasonable (>0)"""
        print("\n🔍 Testing RTF Computation...")
        
        # Test both isolated TTS and chained mode
        runs_to_test = [
            ("elevenlabs", "isolated", "Testing RTF computation for TTS"),
            (["elevenlabs", "deepgram"], "chained", "Testing RTF computation for chained")
        ]
        
        rtf_tests_passed = 0
        rtf_tests_total = 0
        
        for vendors, mode, text in runs_to_test:
            if mode == "isolated":
                run = self.create_isolated_run_and_wait(vendors, text)
            else:
                run = self.create_chained_run_and_wait(vendors, text)
            
            if not run:
                continue
            
            metrics_data = self.extract_metrics_from_run(run)
            
            for item_id, data in metrics_data.items():
                metrics = data['metrics']
                audio_duration = metrics.get('audio_duration', 0)
                tts_rtf = metrics.get('tts_rtf')
                stt_rtf = metrics.get('stt_rtf')
                
                rtf_tests_total += 1
                
                if audio_duration > 0:
                    rtf_found = False
                    rtf_details = []
                    
                    if tts_rtf is not None and tts_rtf > 0:
                        rtf_found = True
                        rtf_details.append(f"tts_rtf={tts_rtf:.3f}")
                    
                    if stt_rtf is not None and stt_rtf > 0:
                        rtf_found = True
                        rtf_details.append(f"stt_rtf={stt_rtf:.3f}")
                    
                    if rtf_found:
                        rtf_tests_passed += 1
                        print(f"   ✅ RTF computed for {data['vendor']}: {', '.join(rtf_details)} (duration={audio_duration:.3f}s)")
                    else:
                        print(f"   ❌ No valid RTF for {data['vendor']}: tts_rtf={tts_rtf}, stt_rtf={stt_rtf} (duration={audio_duration:.3f}s)")
                else:
                    print(f"   ⚠️  No audio duration for {data['vendor']}: {audio_duration}")
        
        if rtf_tests_total > 0 and rtf_tests_passed == rtf_tests_total:
            self.log_test("RTF Computation", True, f"All {rtf_tests_passed}/{rtf_tests_total} items have valid RTF values")
            return True
        elif rtf_tests_passed > 0:
            self.log_test("RTF Computation", False, f"Only {rtf_tests_passed}/{rtf_tests_total} items have valid RTF values")
            return False
        else:
            self.log_test("RTF Computation", False, "No valid RTF values found")
            return False

    def test_dashboard_stats_non_zero_latency(self):
        """Test 5: Dashboard stats - /api/dashboard/stats returns non-zero avg_latency after at least one chained run"""
        print("\n🔍 Testing Dashboard Stats Non-Zero Latency...")
        
        # First ensure we have at least one chained run
        run = self.create_chained_run_and_wait(["elevenlabs", "deepgram"], "Dashboard stats test run")
        
        if not run:
            self.log_test("Dashboard Stats Latency", False, "Failed to create chained run for stats test")
            return False
        
        # Now check dashboard stats
        success, response, status_code = self.make_request('GET', '/api/dashboard/stats')
        
        if not success or status_code != 200:
            self.log_test("Dashboard Stats Latency", False, f"Failed to get dashboard stats: {status_code}")
            return False
        
        try:
            data = response.json()
            avg_latency = data.get('avg_latency', 0)
            
            if avg_latency > 0:
                self.log_test("Dashboard Stats Latency", True, 
                            f"Dashboard shows non-zero avg_latency: {avg_latency}s")
                return True
            else:
                self.log_test("Dashboard Stats Latency", False, 
                            f"Dashboard shows zero avg_latency: {avg_latency}s after chained run")
                return False
        except Exception as e:
            self.log_test("Dashboard Stats Latency", False, f"Error parsing dashboard stats: {str(e)}")
            return False

    def test_dashboard_insights_endpoint(self):
        """Test 6: New endpoint /api/dashboard/insights returns service_mix, vendor_usage, top_vendor_pairings structures"""
        print("\n🔍 Testing Dashboard Insights Endpoint...")
        
        success, response, status_code = self.make_request('GET', '/api/dashboard/insights')
        
        if not success or status_code != 200:
            self.log_test("Dashboard Insights Endpoint", False, f"Failed to get insights: {status_code}")
            return False
        
        try:
            data = response.json()
            
            # Check required structures
            required_keys = ['service_mix', 'vendor_usage', 'top_vendor_pairings']
            missing_keys = [key for key in required_keys if key not in data]
            
            if missing_keys:
                self.log_test("Dashboard Insights Endpoint", False, 
                            f"Missing required keys: {missing_keys}")
                return False
            
            # Validate structure types
            service_mix = data['service_mix']
            vendor_usage = data['vendor_usage']
            top_vendor_pairings = data['top_vendor_pairings']
            
            # service_mix should be a dict with service types
            if not isinstance(service_mix, dict):
                self.log_test("Dashboard Insights Endpoint", False, 
                            f"service_mix is not a dict: {type(service_mix)}")
                return False
            
            # vendor_usage should have tts and stt keys
            if not isinstance(vendor_usage, dict) or 'tts' not in vendor_usage or 'stt' not in vendor_usage:
                self.log_test("Dashboard Insights Endpoint", False, 
                            f"vendor_usage structure invalid: {vendor_usage}")
                return False
            
            # top_vendor_pairings should be a list
            if not isinstance(top_vendor_pairings, list):
                self.log_test("Dashboard Insights Endpoint", False, 
                            f"top_vendor_pairings is not a list: {type(top_vendor_pairings)}")
                return False
            
            self.log_test("Dashboard Insights Endpoint", True, 
                        f"All structures present: service_mix={service_mix}, vendor_usage keys={list(vendor_usage.keys())}, pairings count={len(top_vendor_pairings)}")
            return True
            
        except Exception as e:
            self.log_test("Dashboard Insights Endpoint", False, f"Error parsing insights: {str(e)}")
            return False

    def test_export_endpoint_csv_pdf(self):
        """Test 7: Export endpoint /api/export returns a CSV and a PDF with data for all and selected"""
        print("\n🔍 Testing Export Endpoint CSV and PDF...")
        
        # Test CSV export (all data)
        csv_payload = {"format": "csv", "all": True}
        success, response, status_code = self.make_request('POST', '/api/export', data=csv_payload)
        
        csv_success = False
        if success and status_code == 200:
            content_type = response.headers.get('content-type', '')
            content_length = len(response.content) if response else 0
            
            if 'text/csv' in content_type and content_length > 0:
                csv_success = True
                print(f"   ✅ CSV export successful: {content_length} bytes, {content_type}")
            else:
                print(f"   ❌ CSV export failed: {content_type}, {content_length} bytes")
        else:
            print(f"   ❌ CSV export request failed: {status_code}")
        
        # Test PDF export (all data)
        pdf_payload = {"format": "pdf", "all": True}
        success, response, status_code = self.make_request('POST', '/api/export', data=pdf_payload)
        
        pdf_success = False
        if success and status_code == 200:
            content_type = response.headers.get('content-type', '')
            content_length = len(response.content) if response else 0
            
            if 'application/pdf' in content_type and content_length > 0:
                pdf_success = True
                print(f"   ✅ PDF export successful: {content_length} bytes, {content_type}")
            else:
                print(f"   ❌ PDF export failed: {content_type}, {content_length} bytes")
        else:
            print(f"   ❌ PDF export request failed: {status_code}")
        
        if csv_success and pdf_success:
            self.log_test("Export Endpoint CSV/PDF", True, "Both CSV and PDF exports working")
            return True
        elif csv_success or pdf_success:
            self.log_test("Export Endpoint CSV/PDF", False, f"Only {'CSV' if csv_success else 'PDF'} export working")
            return False
        else:
            self.log_test("Export Endpoint CSV/PDF", False, "Both CSV and PDF exports failed")
            return False

    def run_metrics_tests(self):
        """Run all metrics-focused tests based on review request"""
        print("🚀 Starting Focused Metrics Testing...")
        print(f"Testing against: {self.base_url}")
        print("=" * 80)
        
        # Test 1: Isolated TTS latency correctness
        self.test_isolated_tts_latency_correctness()
        
        # Test 2: Isolated STT latency correctness  
        self.test_isolated_stt_latency_correctness()
        
        # Test 3: Chained latency math correctness
        self.test_chained_latency_correctness()
        
        # Test 4: RTF computation
        self.test_rtf_computation()
        
        # Test 5: Dashboard stats non-zero latency
        self.test_dashboard_stats_non_zero_latency()
        
        # Test 6: Dashboard insights endpoint
        self.test_dashboard_insights_endpoint()
        
        # Test 7: Export endpoint CSV/PDF
        self.test_export_endpoint_csv_pdf()
        
        # Print summary
        print("\n" + "=" * 80)
        print("📊 METRICS TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        if self.created_run_ids:
            print(f"\nCreated {len(self.created_run_ids)} test runs: {self.created_run_ids}")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All metrics tests passed! Backend metrics are working correctly.")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} test(s) failed. Check the details above.")
            return 1

def main():
    """Main test execution"""
    # Allow optional CLI arg for base_url
    base = sys.argv[1] if len(sys.argv) > 1 else None
    tester = MetricsAPITester(base_url=base)
    return tester.run_metrics_tests()

if __name__ == "__main__":
    sys.exit(main())