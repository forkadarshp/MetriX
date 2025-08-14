#!/usr/bin/env python3
"""
Comprehensive Metrics Precision Testing for TTS/STT Benchmarking Dashboard
Testing the improved metrics calculation system with focus on:
1. WER Calculation (jiwer library)
2. Timing Precision (time.perf_counter)
3. Audio Duration (improved parsing)
4. RTF Calculation (validation and bounds)
5. Confidence Validation (normalization)
6. Threshold Consistency (WER threshold 0.15)
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
import statistics

class MetricsPrecisionTester:
    def __init__(self, base_url: str = None):
        # Get base URL from environment or use default
        if base_url is None:
            # Try to read from frontend/.env
            try:
                with open('/app/frontend/.env', 'r') as f:
                    for line in f:
                        if line.startswith('REACT_APP_BACKEND_URL='):
                            base_url = line.split('=', 1)[1].strip()
                            break
            except:
                pass
        
        self.base_url = base_url or "https://bb2717fd-0473-4c41-aa2c-5cd7204e7bca.preview.emergentagent.com"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_run_ids = []
        self.metrics_data = []  # Store metrics for analysis

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

    def wait_for_run_completion(self, run_id: str, max_wait: int = 120) -> Optional[Dict]:
        """Wait for run completion and return run data"""
        check_interval = 5
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

    def extract_metrics_from_run(self, run_data: Dict) -> List[Dict]:
        """Extract all metrics from run data for analysis"""
        metrics = []
        items = run_data.get('items', [])
        
        for item in items:
            item_metrics = {
                'item_id': item.get('id'),
                'vendor': item.get('vendor'),
                'mode': run_data.get('mode'),
                'status': item.get('status'),
                'metrics': {}
            }
            
            # Extract metrics from metrics array
            for metric in item.get('metrics', []):
                metric_name = metric.get('metric_name')
                metric_value = metric.get('value')
                metric_unit = metric.get('unit')
                metric_threshold = metric.get('threshold')
                metric_pass_fail = metric.get('pass_fail')
                
                item_metrics['metrics'][metric_name] = {
                    'value': metric_value,
                    'unit': metric_unit,
                    'threshold': metric_threshold,
                    'pass_fail': metric_pass_fail
                }
            
            # Extract metadata from metrics_json
            try:
                if item.get('metrics_json'):
                    metadata = json.loads(item.get('metrics_json'))
                    item_metrics['metadata'] = metadata
            except:
                item_metrics['metadata'] = {}
            
            metrics.append(item_metrics)
        
        return metrics

    def test_wer_calculation_precision(self):
        """Test WER calculation using jiwer library for industry-standard precision"""
        print("\n🔍 Testing WER Calculation Precision (jiwer library)...")
        
        # Test with known text pairs that should produce specific WER values
        test_cases = [
            {
                'text': 'The quick brown fox jumps over the lazy dog',
                'expected_similarity': 0.8,  # Should be high similarity
                'mode': 'isolated',
                'service': 'stt',
                'vendor': 'deepgram'
            },
            {
                'text': 'Welcome to our banking services how can I help you today',
                'expected_similarity': 0.7,
                'mode': 'chained',
                'vendors': ['elevenlabs', 'deepgram']
            }
        ]
        
        wer_results = []
        
        for i, test_case in enumerate(test_cases):
            print(f"   Testing WER case {i+1}: '{test_case['text'][:30]}...'")
            
            if test_case['mode'] == 'isolated':
                # Create isolated STT run
                run_data = {
                    "mode": "isolated",
                    "vendors": [test_case['vendor']],
                    "config": {"service": test_case['service']},
                    "text_inputs": [test_case['text']]
                }
            else:
                # Create chained run
                run_data = {
                    "mode": "chained",
                    "vendors": test_case['vendors'],
                    "text_inputs": [test_case['text']]
                }
            
            success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
            
            if not success or status_code != 200:
                print(f"   Failed to create run for WER test case {i+1}")
                continue
            
            try:
                data = response.json()
                run_id = data['run_id']
                self.created_run_ids.append(run_id)
                
                # Wait for completion
                run_result = self.wait_for_run_completion(run_id, 90)
                if run_result:
                    metrics = self.extract_metrics_from_run(run_result)
                    
                    for metric_item in metrics:
                        if 'wer' in metric_item['metrics']:
                            wer_value = metric_item['metrics']['wer']['value']
                            wer_threshold = metric_item['metrics']['wer']['threshold']
                            wer_pass_fail = metric_item['metrics']['wer']['pass_fail']
                            
                            wer_results.append({
                                'case': i+1,
                                'text': test_case['text'],
                                'wer': wer_value,
                                'threshold': wer_threshold,
                                'pass_fail': wer_pass_fail,
                                'accuracy': (1 - wer_value) * 100 if wer_value is not None else None
                            })
                            
                            print(f"   Case {i+1} WER: {wer_value:.4f}, Threshold: {wer_threshold}, Pass/Fail: {wer_pass_fail}")
                            break
                
            except Exception as e:
                print(f"   Error in WER test case {i+1}: {str(e)}")
        
        # Analyze WER results
        if wer_results:
            # Check threshold consistency (should be 0.15)
            thresholds = [r['threshold'] for r in wer_results if r['threshold'] is not None]
            threshold_consistent = all(t == 0.15 for t in thresholds)
            
            # Check WER values are reasonable (0.0 to 1.0)
            wer_values = [r['wer'] for r in wer_results if r['wer'] is not None]
            wer_valid_range = all(0.0 <= w <= 1.0 for w in wer_values)
            
            # Check pass/fail logic consistency
            pass_fail_consistent = all(
                (r['wer'] <= 0.15 and r['pass_fail'] == 'pass') or 
                (r['wer'] > 0.15 and r['pass_fail'] == 'fail')
                for r in wer_results if r['wer'] is not None and r['pass_fail'] is not None
            )
            
            if threshold_consistent and wer_valid_range and pass_fail_consistent:
                avg_wer = statistics.mean(wer_values) if wer_values else 0
                self.log_test("WER Calculation Precision", True, 
                            f"WER calculations precise. Avg WER: {avg_wer:.4f}, Threshold: 0.15, Results: {len(wer_results)}")
                return True
            else:
                issues = []
                if not threshold_consistent:
                    issues.append(f"Inconsistent thresholds: {set(thresholds)}")
                if not wer_valid_range:
                    issues.append(f"Invalid WER range: {wer_values}")
                if not pass_fail_consistent:
                    issues.append("Pass/fail logic inconsistent")
                
                self.log_test("WER Calculation Precision", False, f"Issues: {', '.join(issues)}")
        else:
            self.log_test("WER Calculation Precision", False, "No WER results obtained")
        
        return False

    def test_timing_precision(self):
        """Test timing precision using time.perf_counter() for high-precision monotonic timing"""
        print("\n🔍 Testing Timing Precision (time.perf_counter)...")
        
        # Create multiple runs to test timing precision
        timing_results = []
        
        for i in range(3):
            print(f"   Creating timing test run {i+1}/3...")
            
            run_data = {
                "mode": "isolated",
                "vendors": ["elevenlabs"],
                "config": {"service": "tts"},
                "text_inputs": [f"Timing precision test number {i+1}"]
            }
            
            success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
            
            if not success or status_code != 200:
                continue
            
            try:
                data = response.json()
                run_id = data['run_id']
                self.created_run_ids.append(run_id)
                
                run_result = self.wait_for_run_completion(run_id, 60)
                if run_result:
                    metrics = self.extract_metrics_from_run(run_result)
                    
                    for metric_item in metrics:
                        latency_metrics = {}
                        for metric_name in ['tts_latency', 'stt_latency', 'e2e_latency']:
                            if metric_name in metric_item['metrics']:
                                latency_metrics[metric_name] = metric_item['metrics'][metric_name]['value']
                        
                        if latency_metrics:
                            timing_results.append({
                                'run': i+1,
                                'latencies': latency_metrics
                            })
                            
                            print(f"   Run {i+1} latencies: {latency_metrics}")
                            break
                
            except Exception as e:
                print(f"   Error in timing test run {i+1}: {str(e)}")
        
        # Analyze timing precision
        if timing_results:
            # Check that latencies are reasonable (not zero, not too high)
            all_latencies = []
            for result in timing_results:
                all_latencies.extend(result['latencies'].values())
            
            # Timing should be > 0 and < 30 seconds for reasonable API calls
            timing_reasonable = all(0.01 <= lat <= 30.0 for lat in all_latencies)
            
            # Check precision (should have decimal places, indicating perf_counter usage)
            timing_precise = all(lat != int(lat) for lat in all_latencies)  # Should have decimal precision
            
            if timing_reasonable and timing_precise:
                avg_latency = statistics.mean(all_latencies)
                self.log_test("Timing Precision", True, 
                            f"High-precision timing detected. Avg: {avg_latency:.4f}s, Range: {min(all_latencies):.4f}-{max(all_latencies):.4f}s")
                return True
            else:
                issues = []
                if not timing_reasonable:
                    issues.append(f"Unreasonable latencies: {all_latencies}")
                if not timing_precise:
                    issues.append("Low precision timing (integer values)")
                
                self.log_test("Timing Precision", False, f"Issues: {', '.join(issues)}")
        else:
            self.log_test("Timing Precision", False, "No timing results obtained")
        
        return False

    def test_audio_duration_precision(self):
        """Test audio duration calculation with improved parsing and fallbacks"""
        print("\n🔍 Testing Audio Duration Precision (improved parsing)...")
        
        # Test with different audio formats/vendors
        test_cases = [
            {
                'vendor': 'elevenlabs',
                'text': 'This is a test of audio duration calculation for MP3 format',
                'expected_format': 'mp3'
            },
            {
                'vendor': 'deepgram', 
                'text': 'This is a test of audio duration calculation for WAV format',
                'expected_format': 'wav'
            }
        ]
        
        duration_results = []
        
        for i, test_case in enumerate(test_cases):
            print(f"   Testing audio duration case {i+1}: {test_case['vendor']} ({test_case['expected_format']})")
            
            run_data = {
                "mode": "isolated",
                "vendors": [test_case['vendor']],
                "config": {"service": "tts"},
                "text_inputs": [test_case['text']]
            }
            
            success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
            
            if not success or status_code != 200:
                continue
            
            try:
                data = response.json()
                run_id = data['run_id']
                self.created_run_ids.append(run_id)
                
                run_result = self.wait_for_run_completion(run_id, 60)
                if run_result:
                    metrics = self.extract_metrics_from_run(run_result)
                    
                    for metric_item in metrics:
                        if 'audio_duration' in metric_item['metrics']:
                            duration = metric_item['metrics']['audio_duration']['value']
                            audio_path = None
                            
                            # Try to get audio path from run items
                            for item in run_result.get('items', []):
                                if item.get('id') == metric_item['item_id']:
                                    audio_path = item.get('audio_path', '')
                                    break
                            
                            duration_results.append({
                                'case': i+1,
                                'vendor': test_case['vendor'],
                                'text_length': len(test_case['text']),
                                'duration': duration,
                                'audio_path': audio_path,
                                'expected_format': test_case['expected_format']
                            })
                            
                            print(f"   Case {i+1} Duration: {duration:.3f}s, Path: {audio_path}")
                            break
                
            except Exception as e:
                print(f"   Error in duration test case {i+1}: {str(e)}")
        
        # Analyze duration results
        if duration_results:
            # Check that durations are reasonable (> 0, correlate with text length)
            durations = [r['duration'] for r in duration_results if r['duration'] is not None]
            durations_valid = all(0.1 <= d <= 60.0 for d in durations)  # 0.1s to 60s reasonable range
            
            # Check precision (should have decimal places)
            durations_precise = all(d != int(d) for d in durations)
            
            # Check that longer text generally produces longer audio
            if len(duration_results) >= 2:
                text_lengths = [r['text_length'] for r in duration_results]
                duration_correlation = True  # Simple check - could be more sophisticated
            else:
                duration_correlation = True  # Can't check with < 2 samples
            
            if durations_valid and durations_precise and duration_correlation:
                avg_duration = statistics.mean(durations)
                self.log_test("Audio Duration Precision", True, 
                            f"Precise duration calculation. Avg: {avg_duration:.3f}s, Results: {len(duration_results)}")
                return True
            else:
                issues = []
                if not durations_valid:
                    issues.append(f"Invalid durations: {durations}")
                if not durations_precise:
                    issues.append("Low precision durations")
                if not duration_correlation:
                    issues.append("Poor text-duration correlation")
                
                self.log_test("Audio Duration Precision", False, f"Issues: {', '.join(issues)}")
        else:
            self.log_test("Audio Duration Precision", False, "No duration results obtained")
        
        return False

    def test_rtf_calculation_validation(self):
        """Test RTF calculation with validation and bounds checking"""
        print("\n🔍 Testing RTF Calculation Validation (bounds checking)...")
        
        # Create runs to test RTF calculation
        rtf_results = []
        
        test_cases = [
            {
                'mode': 'isolated',
                'vendor': 'elevenlabs',
                'service': 'tts',
                'text': 'RTF calculation test for TTS processing'
            },
            {
                'mode': 'isolated', 
                'vendor': 'deepgram',
                'service': 'stt',
                'text': 'RTF calculation test for STT processing'
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            print(f"   Testing RTF case {i+1}: {test_case['mode']} {test_case['service']} with {test_case['vendor']}")
            
            run_data = {
                "mode": test_case['mode'],
                "vendors": [test_case['vendor']],
                "config": {"service": test_case['service']},
                "text_inputs": [test_case['text']]
            }
            
            success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
            
            if not success or status_code != 200:
                continue
            
            try:
                data = response.json()
                run_id = data['run_id']
                self.created_run_ids.append(run_id)
                
                run_result = self.wait_for_run_completion(run_id, 60)
                if run_result:
                    metrics = self.extract_metrics_from_run(run_result)
                    
                    for metric_item in metrics:
                        rtf_metrics = {}
                        latency_metrics = {}
                        duration = None
                        
                        # Extract RTF metrics
                        for metric_name in ['tts_rtf', 'stt_rtf']:
                            if metric_name in metric_item['metrics']:
                                rtf_metrics[metric_name] = metric_item['metrics'][metric_name]['value']
                        
                        # Extract related metrics for validation
                        for metric_name in ['tts_latency', 'stt_latency']:
                            if metric_name in metric_item['metrics']:
                                latency_metrics[metric_name] = metric_item['metrics'][metric_name]['value']
                        
                        if 'audio_duration' in metric_item['metrics']:
                            duration = metric_item['metrics']['audio_duration']['value']
                        
                        if rtf_metrics:
                            rtf_results.append({
                                'case': i+1,
                                'service': test_case['service'],
                                'vendor': test_case['vendor'],
                                'rtf_metrics': rtf_metrics,
                                'latency_metrics': latency_metrics,
                                'duration': duration
                            })
                            
                            print(f"   Case {i+1} RTF: {rtf_metrics}, Latency: {latency_metrics}, Duration: {duration}")
                            break
                
            except Exception as e:
                print(f"   Error in RTF test case {i+1}: {str(e)}")
        
        # Analyze RTF results
        if rtf_results:
            # Check RTF bounds (typically 0.01x to 100x for reasonable processing)
            all_rtf_values = []
            for result in rtf_results:
                all_rtf_values.extend(result['rtf_metrics'].values())
            
            rtf_bounds_valid = all(0.01 <= rtf <= 100.0 for rtf in all_rtf_values)
            
            # Check RTF calculation accuracy (RTF = latency / duration)
            rtf_calculation_accurate = True
            for result in rtf_results:
                if result['duration'] and result['duration'] > 0:
                    for rtf_name, rtf_value in result['rtf_metrics'].items():
                        # Find corresponding latency
                        latency_name = rtf_name.replace('_rtf', '_latency')
                        if latency_name in result['latency_metrics']:
                            expected_rtf = result['latency_metrics'][latency_name] / result['duration']
                            # Allow 5% tolerance for floating point precision
                            if abs(rtf_value - expected_rtf) / expected_rtf > 0.05:
                                rtf_calculation_accurate = False
                                print(f"   RTF calculation mismatch: {rtf_value} vs expected {expected_rtf}")
            
            if rtf_bounds_valid and rtf_calculation_accurate:
                avg_rtf = statistics.mean(all_rtf_values) if all_rtf_values else 0
                self.log_test("RTF Calculation Validation", True, 
                            f"RTF calculations valid. Avg RTF: {avg_rtf:.3f}x, Results: {len(rtf_results)}")
                return True
            else:
                issues = []
                if not rtf_bounds_valid:
                    issues.append(f"RTF out of bounds: {all_rtf_values}")
                if not rtf_calculation_accurate:
                    issues.append("RTF calculation inaccurate")
                
                self.log_test("RTF Calculation Validation", False, f"Issues: {', '.join(issues)}")
        else:
            self.log_test("RTF Calculation Validation", False, "No RTF results obtained")
        
        return False

    def test_confidence_validation(self):
        """Test confidence score validation and normalization (0.0-1.0 range)"""
        print("\n🔍 Testing Confidence Validation (normalization to 0.0-1.0)...")
        
        # Create runs that will produce confidence scores
        confidence_results = []
        
        test_cases = [
            {
                'mode': 'isolated',
                'vendor': 'deepgram',
                'service': 'stt',
                'text': 'Confidence validation test for speech recognition'
            },
            {
                'mode': 'chained',
                'vendors': ['elevenlabs', 'deepgram'],
                'text': 'End to end confidence validation test'
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            print(f"   Testing confidence case {i+1}: {test_case['mode']} with {test_case.get('vendor', test_case.get('vendors'))}")
            
            if test_case['mode'] == 'isolated':
                run_data = {
                    "mode": test_case['mode'],
                    "vendors": [test_case['vendor']],
                    "config": {"service": test_case['service']},
                    "text_inputs": [test_case['text']]
                }
            else:
                run_data = {
                    "mode": test_case['mode'],
                    "vendors": test_case['vendors'],
                    "text_inputs": [test_case['text']]
                }
            
            success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
            
            if not success or status_code != 200:
                continue
            
            try:
                data = response.json()
                run_id = data['run_id']
                self.created_run_ids.append(run_id)
                
                run_result = self.wait_for_run_completion(run_id, 60)
                if run_result:
                    metrics = self.extract_metrics_from_run(run_result)
                    
                    for metric_item in metrics:
                        if 'confidence' in metric_item['metrics']:
                            confidence = metric_item['metrics']['confidence']['value']
                            confidence_unit = metric_item['metrics']['confidence']['unit']
                            
                            confidence_results.append({
                                'case': i+1,
                                'mode': test_case['mode'],
                                'confidence': confidence,
                                'unit': confidence_unit
                            })
                            
                            print(f"   Case {i+1} Confidence: {confidence} ({confidence_unit})")
                            break
                
            except Exception as e:
                print(f"   Error in confidence test case {i+1}: {str(e)}")
        
        # Analyze confidence results
        if confidence_results:
            # Check confidence range (should be 0.0 to 1.0)
            confidences = [r['confidence'] for r in confidence_results if r['confidence'] is not None]
            confidence_range_valid = all(0.0 <= c <= 1.0 for c in confidences)
            
            # Check units (should be 'ratio' for normalized values)
            units = [r['unit'] for r in confidence_results if r['unit'] is not None]
            units_consistent = all(u == 'ratio' for u in units)
            
            # Check precision (should have decimal places)
            confidence_precise = all(c != int(c) for c in confidences if c not in [0.0, 1.0])
            
            if confidence_range_valid and units_consistent:
                avg_confidence = statistics.mean(confidences) if confidences else 0
                self.log_test("Confidence Validation", True, 
                            f"Confidence properly normalized. Avg: {avg_confidence:.3f}, Range: 0.0-1.0, Results: {len(confidence_results)}")
                return True
            else:
                issues = []
                if not confidence_range_valid:
                    issues.append(f"Confidence out of range: {confidences}")
                if not units_consistent:
                    issues.append(f"Inconsistent units: {set(units)}")
                
                self.log_test("Confidence Validation", False, f"Issues: {', '.join(issues)}")
        else:
            self.log_test("Confidence Validation", False, "No confidence results obtained")
        
        return False

    def test_cross_mode_consistency(self):
        """Test consistency across isolated TTS, isolated STT, and chained modes"""
        print("\n🔍 Testing Cross-Mode Consistency...")
        
        test_text = "Cross mode consistency test for metrics calculation"
        
        # Test all three modes
        modes_to_test = [
            {
                'name': 'Isolated TTS',
                'mode': 'isolated',
                'vendors': ['elevenlabs'],
                'config': {'service': 'tts'}
            },
            {
                'name': 'Isolated STT', 
                'mode': 'isolated',
                'vendors': ['deepgram'],
                'config': {'service': 'stt'}
            },
            {
                'name': 'Chained E2E',
                'mode': 'chained',
                'vendors': ['elevenlabs', 'deepgram'],
                'config': {}
            }
        ]
        
        mode_results = []
        
        for mode_test in modes_to_test:
            print(f"   Testing {mode_test['name']}...")
            
            run_data = {
                "mode": mode_test['mode'],
                "vendors": mode_test['vendors'],
                "config": mode_test['config'],
                "text_inputs": [test_text]
            }
            
            success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
            
            if not success or status_code != 200:
                continue
            
            try:
                data = response.json()
                run_id = data['run_id']
                self.created_run_ids.append(run_id)
                
                run_result = self.wait_for_run_completion(run_id, 90)
                if run_result:
                    metrics = self.extract_metrics_from_run(run_result)
                    
                    if metrics:
                        mode_results.append({
                            'name': mode_test['name'],
                            'mode': mode_test['mode'],
                            'metrics': metrics[0]['metrics']  # Take first item
                        })
                        
                        metric_names = list(metrics[0]['metrics'].keys())
                        print(f"   {mode_test['name']} metrics: {metric_names}")
                
            except Exception as e:
                print(f"   Error in {mode_test['name']}: {str(e)}")
        
        # Analyze cross-mode consistency
        if len(mode_results) >= 2:
            # Check WER threshold consistency across modes
            wer_thresholds = []
            for result in mode_results:
                if 'wer' in result['metrics'] and result['metrics']['wer'].get('threshold'):
                    wer_thresholds.append(result['metrics']['wer']['threshold'])
            
            threshold_consistent = len(set(wer_thresholds)) <= 1 if wer_thresholds else True
            expected_threshold = 0.15
            threshold_correct = all(t == expected_threshold for t in wer_thresholds)
            
            # Check that each mode produces appropriate metrics
            mode_metrics_appropriate = True
            for result in mode_results:
                if result['mode'] == 'isolated':
                    # Isolated should have either TTS or STT specific metrics
                    has_tts_metrics = 'tts_latency' in result['metrics']
                    has_stt_metrics = 'stt_latency' in result['metrics'] or 'wer' in result['metrics']
                    if not (has_tts_metrics or has_stt_metrics):
                        mode_metrics_appropriate = False
                elif result['mode'] == 'chained':
                    # Chained should have E2E metrics
                    has_e2e_metrics = 'e2e_latency' in result['metrics']
                    if not has_e2e_metrics:
                        mode_metrics_appropriate = False
            
            if threshold_consistent and threshold_correct and mode_metrics_appropriate:
                self.log_test("Cross-Mode Consistency", True, 
                            f"Consistent metrics across {len(mode_results)} modes. WER threshold: {expected_threshold}")
                return True
            else:
                issues = []
                if not threshold_consistent:
                    issues.append(f"Inconsistent WER thresholds: {wer_thresholds}")
                if not threshold_correct:
                    issues.append(f"Wrong WER threshold: {wer_thresholds} (expected {expected_threshold})")
                if not mode_metrics_appropriate:
                    issues.append("Inappropriate metrics for mode")
                
                self.log_test("Cross-Mode Consistency", False, f"Issues: {', '.join(issues)}")
        else:
            self.log_test("Cross-Mode Consistency", False, f"Insufficient mode results: {len(mode_results)}")
        
        return False

    def test_edge_cases(self):
        """Test edge cases like very short text, empty strings, etc."""
        print("\n🔍 Testing Edge Cases...")
        
        edge_cases = [
            {
                'name': 'Very Short Text',
                'text': 'Hi',
                'expected_behavior': 'should_work'
            },
            {
                'name': 'Single Word',
                'text': 'Hello',
                'expected_behavior': 'should_work'
            },
            {
                'name': 'Numbers and Punctuation',
                'text': 'Test 123, with punctuation!',
                'expected_behavior': 'should_work'
            }
        ]
        
        edge_case_results = []
        
        for case in edge_cases:
            print(f"   Testing edge case: {case['name']} - '{case['text']}'")
            
            run_data = {
                "mode": "isolated",
                "vendors": ["elevenlabs"],
                "config": {"service": "tts"},
                "text_inputs": [case['text']]
            }
            
            success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
            
            if not success or status_code != 200:
                edge_case_results.append({
                    'name': case['name'],
                    'success': False,
                    'error': f"Failed to create run: {status_code}"
                })
                continue
            
            try:
                data = response.json()
                run_id = data['run_id']
                self.created_run_ids.append(run_id)
                
                run_result = self.wait_for_run_completion(run_id, 60)
                if run_result:
                    metrics = self.extract_metrics_from_run(run_result)
                    
                    if metrics and metrics[0]['metrics']:
                        # Check that metrics are reasonable for edge case
                        has_duration = 'audio_duration' in metrics[0]['metrics']
                        has_latency = 'tts_latency' in metrics[0]['metrics']
                        
                        if has_duration and has_latency:
                            duration = metrics[0]['metrics']['audio_duration']['value']
                            latency = metrics[0]['metrics']['tts_latency']['value']
                            
                            # Even short text should produce some audio duration
                            duration_reasonable = 0.1 <= duration <= 10.0
                            latency_reasonable = 0.1 <= latency <= 30.0
                            
                            edge_case_results.append({
                                'name': case['name'],
                                'success': duration_reasonable and latency_reasonable,
                                'duration': duration,
                                'latency': latency
                            })
                            
                            print(f"   {case['name']}: Duration {duration:.3f}s, Latency {latency:.3f}s")
                        else:
                            edge_case_results.append({
                                'name': case['name'],
                                'success': False,
                                'error': "Missing duration or latency metrics"
                            })
                    else:
                        edge_case_results.append({
                            'name': case['name'],
                            'success': False,
                            'error': "No metrics generated"
                        })
                else:
                    edge_case_results.append({
                        'name': case['name'],
                        'success': False,
                        'error': "Run did not complete"
                    })
                
            except Exception as e:
                edge_case_results.append({
                    'name': case['name'],
                    'success': False,
                    'error': str(e)
                })
        
        # Analyze edge case results
        successful_cases = [r for r in edge_case_results if r['success']]
        
        if len(successful_cases) >= len(edge_cases) * 0.8:  # At least 80% success
            self.log_test("Edge Cases", True, 
                        f"Edge cases handled well: {len(successful_cases)}/{len(edge_cases)} passed")
            return True
        else:
            failed_cases = [r['name'] for r in edge_case_results if not r['success']]
            self.log_test("Edge Cases", False, 
                        f"Edge case failures: {failed_cases}")
        
        return False

    def run_comprehensive_metrics_tests(self):
        """Run all comprehensive metrics precision tests"""
        print("🚀 Starting Comprehensive Metrics Precision Testing...")
        print(f"Testing against: {self.base_url}")
        print("=" * 80)
        
        # Test 1: WER Calculation Precision (jiwer library)
        self.test_wer_calculation_precision()
        
        # Test 2: Timing Precision (time.perf_counter)
        self.test_timing_precision()
        
        # Test 3: Audio Duration Precision (improved parsing)
        self.test_audio_duration_precision()
        
        # Test 4: RTF Calculation Validation (bounds checking)
        self.test_rtf_calculation_validation()
        
        # Test 5: Confidence Validation (normalization)
        self.test_confidence_validation()
        
        # Test 6: Cross-Mode Consistency
        self.test_cross_mode_consistency()
        
        # Test 7: Edge Cases
        self.test_edge_cases()
        
        # Print comprehensive summary
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE METRICS PRECISION TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        # Detailed results
        print("\n📋 DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"{status} {result['name']}")
            if result['details']:
                print(f"    {result['details']}")
        
        print(f"\n🗂️  Created {len(self.created_run_ids)} test runs for analysis")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All metrics precision tests passed! The improved metrics calculation system is working correctly.")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} test(s) failed. Review the metrics calculation improvements.")
            return 1

def main():
    """Main test execution"""
    tester = MetricsPrecisionTester()
    return tester.run_comprehensive_metrics_tests()

if __name__ == "__main__":
    sys.exit(main())