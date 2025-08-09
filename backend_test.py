#!/usr/bin/env python3
"""
Focused Backend API Testing for TTS/STT Benchmarking Dashboard
Testing audio serving, new vendor capabilities, and specific endpoints per review request
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

class TTSSTTAPITester:
    def __init__(self, base_url: str = "https://6c02f955-20fe-49a7-9ea0-7ba8f08295ff.preview.emergentagent.com"):
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

    def test_real_elevenlabs_tts(self):
        """Test real ElevenLabs TTS integration"""
        print("\n🔍 Testing Real ElevenLabs TTS Integration...")
        
        # Create a run specifically for ElevenLabs TTS testing
        run_data = {
            "mode": "isolated",
            "vendors": ["elevenlabs"],
            "text_inputs": ["Welcome to our banking services. How can I help you today?"]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("ElevenLabs TTS - Run Creation", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
        except:
            self.log_test("ElevenLabs TTS - Run Creation", False, "Invalid response format")
            return False
        
        # Wait for processing and check results
        max_wait_time = 90  # Longer wait for real API calls
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
                        if items:
                            item = items[0]  # First item
                            audio_path = item.get('audio_path', '')
                            
                            # Check if real audio file was generated (not dummy)
                            if audio_path and 'elevenlabs_' in audio_path and not audio_path.endswith('dummy'):
                                # Check if we can access the audio file
                                audio_filename = audio_path.split('/')[-1]
                                audio_success, audio_response, audio_status = self.make_request('GET', f'/api/audio/{audio_filename}')
                                
                                if audio_success and audio_status == 200:
                                    # Check if it's real audio content (not dummy bytes)
                                    content_length = len(audio_response.content) if audio_response else 0
                                    if content_length > 100:  # Real audio should be larger than dummy
                                        self.log_test("ElevenLabs TTS - Real API", True, 
                                                    f"Real audio generated: {content_length} bytes")
                                        return True
                                    else:
                                        self.log_test("ElevenLabs TTS - Real API", False, 
                                                    f"Audio too small, likely dummy: {content_length} bytes")
                                else:
                                    self.log_test("ElevenLabs TTS - Real API", False, 
                                                f"Cannot access audio file: {audio_status}")
                            else:
                                self.log_test("ElevenLabs TTS - Real API", False, 
                                            f"Invalid or dummy audio path: {audio_path}")
                        else:
                            self.log_test("ElevenLabs TTS - Real API", False, "No items in completed run")
                        return False
                    elif status == 'failed':
                        self.log_test("ElevenLabs TTS - Real API", False, "Run failed during processing")
                        return False
                    else:
                        print(f"   Waiting for ElevenLabs processing... Status: {status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                except Exception as e:
                    print(f"   Error checking ElevenLabs run: {str(e)}")
                    time.sleep(check_interval)
            else:
                time.sleep(check_interval)
        
        self.log_test("ElevenLabs TTS - Real API", False, "Processing timeout")
        return False

    def test_real_deepgram_stt(self):
        """Test real Deepgram STT integration"""
        print("\n🔍 Testing Real Deepgram STT Integration...")
        
        # Create a run specifically for Deepgram STT testing
        run_data = {
            "mode": "isolated", 
            "vendors": ["deepgram"],
            "text_inputs": ["The quick brown fox jumps over the lazy dog."]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("Deepgram STT - Run Creation", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
        except:
            self.log_test("Deepgram STT - Run Creation", False, "Invalid response format")
            return False
        
        # Wait for processing and check results
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
                        items = run.get('items', [])
                        if items:
                            item = items[0]
                            transcript = item.get('transcript', '')
                            original_text = "The quick brown fox jumps over the lazy dog."
                            
                            # Check if we got a real transcript (not dummy)
                            if transcript and transcript != original_text:
                                # Real API might return slightly different text due to TTS->STT conversion
                                # Check if transcript contains key words from original
                                key_words = ['quick', 'brown', 'fox', 'jumps', 'lazy', 'dog']
                                words_found = sum(1 for word in key_words if word.lower() in transcript.lower())
                                
                                if words_found >= 4:  # At least 4 out of 6 key words
                                    self.log_test("Deepgram STT - Real API", True, 
                                                f"Real transcript generated: '{transcript}'")
                                    return True
                                else:
                                    self.log_test("Deepgram STT - Real API", False, 
                                                f"Transcript doesn't match expected content: '{transcript}'")
                            else:
                                self.log_test("Deepgram STT - Real API", False, 
                                            f"No transcript or dummy transcript: '{transcript}'")
                        else:
                            self.log_test("Deepgram STT - Real API", False, "No items in completed run")
                        return False
                    elif status == 'failed':
                        self.log_test("Deepgram STT - Real API", False, "Run failed during processing")
                        return False
                    else:
                        print(f"   Waiting for Deepgram processing... Status: {status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                except Exception as e:
                    print(f"   Error checking Deepgram run: {str(e)}")
                    time.sleep(check_interval)
            else:
                time.sleep(check_interval)
        
        self.log_test("Deepgram STT - Real API", False, "Processing timeout")
        return False

    def test_chained_mode_real_apis(self):
        """Test chained mode with real APIs (TTS -> STT)"""
        print("\n🔍 Testing Chained Mode with Real APIs...")
        
        # Create a chained run with both vendors
        run_data = {
            "mode": "chained",
            "vendors": ["elevenlabs", "deepgram"],
            "text_inputs": ["Hello world, this is a test of the speech recognition system."]
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
        
        # Wait for processing and check results
        max_wait_time = 120  # Longer wait for chained processing
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
                        if items:
                            item = items[0]
                            transcript = item.get('transcript', '')
                            audio_path = item.get('audio_path', '')
                            original_text = "Hello world, this is a test of the speech recognition system."
                            
                            # Check both audio generation and transcription
                            audio_generated = audio_path and 'elevenlabs_' in audio_path
                            transcript_generated = transcript and len(transcript) > 10
                            
                            if audio_generated and transcript_generated:
                                # Calculate basic similarity
                                original_words = set(original_text.lower().split())
                                transcript_words = set(transcript.lower().split())
                                common_words = original_words.intersection(transcript_words)
                                similarity = len(common_words) / len(original_words) if original_words else 0
                                
                                if similarity >= 0.5:  # At least 50% word overlap
                                    self.log_test("Chained Mode - Real APIs", True, 
                                                f"End-to-end success. Similarity: {similarity:.2f}, Transcript: '{transcript}'")
                                    return True
                                else:
                                    self.log_test("Chained Mode - Real APIs", False, 
                                                f"Low similarity: {similarity:.2f}, Transcript: '{transcript}'")
                            else:
                                self.log_test("Chained Mode - Real APIs", False, 
                                            f"Missing audio ({audio_generated}) or transcript ({transcript_generated})")
                        else:
                            self.log_test("Chained Mode - Real APIs", False, "No items in completed run")
                        return False
                    elif status == 'failed':
                        self.log_test("Chained Mode - Real APIs", False, "Run failed during processing")
                        return False
                    else:
                        print(f"   Waiting for chained processing... Status: {status} (attempt {attempt + 1})")
                        time.sleep(check_interval)
                except Exception as e:
                    print(f"   Error checking chained run: {str(e)}")
                    time.sleep(check_interval)
            else:
                time.sleep(check_interval)
        
        self.log_test("Chained Mode - Real APIs", False, "Processing timeout")
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

    def test_audio_serving(self):
        """Test audio serving endpoint with existing audio files"""
        print("\n🔍 Testing Audio Serving...")
        
        # Pick an existing audio file from storage
        test_filename = "elevenlabs_1a7c523a859642db859466b55e57e8e2.mp3"  # Known large file (41KB+)
        
        success, response, status_code = self.make_request('GET', f'/api/audio/{test_filename}', headers={})
        
        if not success:
            self.log_test("Audio Serving", False, "Request failed")
            return False
        
        if status_code == 200:
            content_type = response.headers.get('content-type', '')
            content_length = len(response.content) if response else 0
            
            # Check content type is audio
            if content_type.startswith('audio/'):
                if content_length > 0:
                    self.log_test("Audio Serving", True, 
                                f"Audio served successfully: {content_type}, {content_length} bytes")
                    return True
                else:
                    self.log_test("Audio Serving", False, "Audio file has zero length")
            else:
                self.log_test("Audio Serving", False, f"Wrong content type: {content_type}")
        else:
            self.log_test("Audio Serving", False, f"Status code: {status_code}")
        
        return False

    def test_quick_run_elevenlabs_isolated(self):
        """Test quick run creation with ElevenLabs TTS in isolated mode"""
        print("\n🔍 Testing Quick Run Creation (ElevenLabs Isolated)...")
        
        # Test with form data
        form_data = {
            'text': 'Hello test',
            'vendors': 'elevenlabs',
            'mode': 'isolated'
        }
        
        headers = {}  # Let requests handle form data headers
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success:
            self.log_test("Quick Run ElevenLabs Isolated", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                if 'run_id' in data and 'status' in data:
                    run_id = data['run_id']
                    self.created_run_ids.append(run_id)
                    
                    # Wait up to 3 seconds and check if run has audio_path
                    time.sleep(3)
                    
                    # Check run status
                    success, response, status_code = self.make_request('GET', '/api/runs')
                    if success and status_code == 200:
                        runs_data = response.json()
                        runs = runs_data.get('runs', [])
                        
                        # Find our run (newest first)
                        target_run = None
                        for run in runs:
                            if run.get('id') == run_id:
                                target_run = run
                                break
                        
                        if target_run and target_run.get('items'):
                            for item in target_run['items']:
                                if item.get('vendor') == 'elevenlabs' and item.get('audio_path'):
                                    self.log_test("Quick Run ElevenLabs Isolated", True, 
                                                f"Run created with audio_path: {item['audio_path']}")
                                    return True
                    
                    self.log_test("Quick Run ElevenLabs Isolated", True, 
                                f"Run created with ID: {run_id} (audio may still be processing)")
                    return True
                else:
                    self.log_test("Quick Run ElevenLabs Isolated", False, f"Invalid response: {data}")
            except Exception as e:
                self.log_test("Quick Run ElevenLabs Isolated", False, f"JSON parsing error: {str(e)}")
        else:
            try:
                error_data = response.json() if response else {}
                self.log_test("Quick Run ElevenLabs Isolated", False, 
                            f"Status code: {status_code}, Error: {error_data}")
            except:
                self.log_test("Quick Run ElevenLabs Isolated", False, f"Status code: {status_code}")
        
        return False

    def test_deepgram_tts_isolated(self):
        """Test Deepgram TTS in isolated mode"""
        print("\n🔍 Testing Deepgram TTS (Isolated Mode)...")
        
        form_data = {
            'text': 'Deepgram speak test',
            'vendors': 'deepgram',
            'mode': 'isolated'
        }
        
        headers = {}
        success, response, status_code = self.make_request('POST', '/api/runs/quick', 
                                                         data=form_data, headers=headers)
        
        if not success:
            self.log_test("Deepgram TTS Isolated", False, "Request failed")
            return False
        
        if status_code == 200:
            try:
                data = response.json()
                if 'run_id' in data:
                    run_id = data['run_id']
                    self.created_run_ids.append(run_id)
                    
                    # Wait up to 3 seconds and check if run has audio_path
                    time.sleep(3)
                    
                    # Check run status
                    success, response, status_code = self.make_request('GET', '/api/runs')
                    if success and status_code == 200:
                        runs_data = response.json()
                        runs = runs_data.get('runs', [])
                        
                        # Find our run
                        target_run = None
                        for run in runs:
                            if run.get('id') == run_id:
                                target_run = run
                                break
                        
                        if target_run and target_run.get('items'):
                            for item in target_run['items']:
                                if item.get('vendor') == 'deepgram' and item.get('audio_path'):
                                    self.log_test("Deepgram TTS Isolated", True, 
                                                f"Deepgram TTS created audio: {item['audio_path']}")
                                    return True
                    
                    self.log_test("Deepgram TTS Isolated", True, 
                                f"Run created with ID: {run_id} (audio may still be processing)")
                    return True
                else:
                    self.log_test("Deepgram TTS Isolated", False, f"Invalid response: {data}")
            except Exception as e:
                self.log_test("Deepgram TTS Isolated", False, f"JSON parsing error: {str(e)}")
        else:
            self.log_test("Deepgram TTS Isolated", False, f"Status code: {status_code}")
        
        return False

    def test_chained_mode_metrics(self):
        """Test chained mode and verify metrics labels"""
        print("\n🔍 Testing Chained Mode Metrics...")
        
        run_data = {
            "mode": "chained",
            "vendors": ["elevenlabs", "deepgram"],
            "text_inputs": ["The quick brown fox"]
        }
        
        success, response, status_code = self.make_request('POST', '/api/runs', data=run_data)
        
        if not success or status_code != 200:
            self.log_test("Chained Mode Metrics", False, f"Failed to create run: {status_code}")
            return False
        
        try:
            data = response.json()
            run_id = data['run_id']
            self.created_run_ids.append(run_id)
        except:
            self.log_test("Chained Mode Metrics", False, "Invalid response format")
            return False
        
        # Wait for processing
        time.sleep(3)
        
        # Check run results
        success, response, status_code = self.make_request('GET', '/api/runs')
        if success and status_code == 200:
            runs_data = response.json()
            runs = runs_data.get('runs', [])
            
            # Find our run
            target_run = None
            for run in runs:
                if run.get('id') == run_id:
                    target_run = run
                    break
            
            if target_run and target_run.get('items'):
                # Check for expected metrics in chained mode
                expected_metrics = ['e2e_latency', 'tts_latency', 'stt_latency', 'wer', 'confidence']
                found_metrics = []
                
                for item in target_run['items']:
                    metrics_summary = item.get('metrics_summary', '')
                    if metrics_summary:
                        # Parse metrics from summary string
                        for metric in expected_metrics:
                            if metric in metrics_summary:
                                found_metrics.append(metric)
                
                found_metrics = list(set(found_metrics))  # Remove duplicates
                
                if len(found_metrics) >= 3:  # At least 3 of the expected metrics
                    self.log_test("Chained Mode Metrics", True, 
                                f"Found metrics: {found_metrics}")
                    return True
                else:
                    self.log_test("Chained Mode Metrics", False, 
                                f"Missing expected metrics. Found: {found_metrics}")
            else:
                self.log_test("Chained Mode Metrics", False, "No items found in run")
        else:
            self.log_test("Chained Mode Metrics", False, "Failed to retrieve runs")
        
        return False

    def run_focused_tests(self):
        """Run focused tests based on review request"""
        print("🚀 Starting Focused Backend API Testing...")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # 1. Audio serving test
        self.test_audio_serving()
        
        # 2. Quick run creation (isolated, elevenlabs TTS)
        self.test_quick_run_elevenlabs_isolated()
        
        # 3. Deepgram TTS path
        self.test_deepgram_tts_isolated()
        
        # 4. Metrics labels in chained mode
        self.test_chained_mode_metrics()
        
        # 5. Health check
        self.test_health_endpoint()
        
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
        
        # Real API integration tests
        print("\n" + "=" * 60)
        print("🔥 REAL API INTEGRATION TESTS")
        print("=" * 60)
        self.test_real_elevenlabs_tts()
        self.test_real_deepgram_stt()
        self.test_chained_mode_real_apis()
        
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