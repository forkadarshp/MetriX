# TTS/STT Benchmarking Dashboard - Process Documentation

## Overview

This document provides comprehensive documentation for all three testing processes in the TTS/STT Benchmarking Dashboard:

1. **End-to-End (E2E/Chained) Testing** - Full pipeline: Text → TTS → Audio → STT → Text
2. **Isolated TTS Testing** - Text-to-Speech only with STT evaluation
3. **Isolated STT Testing** - Speech-to-Text only with TTS preparation

---

## 1. End-to-End (E2E/Chained) Testing Process

### Purpose
Test complete TTS→STT pipeline to measure end-to-end latency and quality metrics.

### Process Flow
```
Input Text → TTS Vendor → Audio File → STT Vendor → Output Text → Metrics
```

### Detailed Steps

#### Step 1: Input Processing
- **Input**: User-provided text or script items
- **Configuration**: 
  - `mode: "chained"`
  - `config.chain.tts_vendor`: TTS provider (e.g., "elevenlabs", "deepgram")
  - `config.chain.stt_vendor`: STT provider (e.g., "deepgram", "elevenlabs")
  - Model configurations for each vendor

#### Step 2: TTS Generation
- **Timing**: Start `time.perf_counter()`
- **Process**: Convert input text to audio using selected TTS vendor
- **Parameters**:
  - Model ID (e.g., `eleven_flash_v2_5`, `aura-2`)
  - Voice ID (e.g., `21m00Tcm4TlvDq8ikWAM`, `thalia`)
  - Output format and quality settings
- **Output**: Audio file saved to `storage/audio/`
- **Metrics Captured**:
  - `tts_latency`: Time from TTS request to audio completion
  - Audio metadata (model, voice, format)

#### Step 3: STT Transcription
- **Timing**: Start new `time.perf_counter()`
- **Process**: Transcribe generated audio using selected STT vendor
- **Parameters**:
  - Model ID (e.g., `nova-3`, `scribe_v1`)
  - Language settings
  - Enhanced features (punctuation, formatting)
- **Output**: Transcript text
- **Metrics Captured**:
  - `stt_latency`: Time from STT request to transcript completion
  - Confidence score from STT API

#### Step 4: Quality Assessment
- **WER Calculation**: 
  ```python
  wer = calculate_wer(original_text, transcribed_text)
  ```
  - Uses jiwer library for industry-standard calculation
  - Handles punctuation, case, and whitespace normalization
  
- **Accuracy Calculation**:
  ```python
  accuracy = (1 - wer) * 100  # Percentage
  ```

#### Step 5: Performance Metrics
- **Audio Duration**: Extracted using mutagen library or wave module
- **End-to-End Latency**: 
  ```python
  e2e_latency = tts_latency + stt_latency
  ```
- **RTF Calculations**:
  ```python
  tts_rtf = calculate_rtf(tts_latency, audio_duration, "TTS RTF")
  stt_rtf = calculate_rtf(stt_latency, audio_duration, "STT RTF")
  ```

#### Step 6: Storage and Artifacts
- **Database Storage**: All metrics stored in `metrics` table
- **Audio Artifact**: Saved to `storage/audio/audio_{item_id}.{ext}`
- **Transcript Artifact**: Saved to `storage/transcripts/transcript_{item_id}.txt`
- **Metadata**: Vendor info, models, parameters stored in `run_items.metrics_json`

### Metrics Generated

| Metric | Unit | Description | Threshold |
|--------|------|-------------|-----------|
| `wer` | ratio | Word Error Rate (0.0 = perfect) | ≤ 0.15 |
| `accuracy` | percent | Transcription accuracy (100% = perfect) | ≥ 85% |
| `confidence` | ratio | STT confidence score | 0.0 - 1.0 |
| `e2e_latency` | seconds | Total pipeline latency | - |
| `tts_latency` | seconds | TTS processing time | - |
| `stt_latency` | seconds | STT processing time | - |
| `audio_duration` | seconds | Generated audio length | - |
| `tts_rtf` | x | TTS Real-Time Factor | < 1.0 preferred |
| `stt_rtf` | x | STT Real-Time Factor | < 1.0 preferred |

---

## 2. Isolated TTS Testing Process

### Purpose
Evaluate TTS quality and performance independently, with automatic quality assessment via STT.

### Process Flow
```
Input Text → TTS Vendor → Audio File → STT Evaluation → Quality Metrics
```

### Detailed Steps

#### Step 1: Input Configuration
- **Input**: Text to synthesize
- **Configuration**:
  - `mode: "isolated"`
  - `service: "tts"`
  - `vendors`: List of TTS vendors to test
  - Model configurations per vendor

#### Step 2: TTS Generation
- **Process**: Same as E2E Step 2
- **Multiple Vendors**: If multiple vendors selected, creates separate run items
- **Timing**: High-precision measurement using `time.perf_counter()`

#### Step 3: Automatic Quality Assessment
- **STT Evaluation**: Uses Deepgram Nova-3 as default evaluator
- **Process**: 
  - Transcribe generated audio
  - Compare with original text
  - Calculate quality metrics
- **Parameters**:
  ```python
  stt_params = {
      "model": "nova-3",
      "smart_format": True,
      "punctuate": True, 
      "language": "en-US"
  }
  ```

#### Step 4: TTS-Specific Metrics
- **TTS Latency**: Pure TTS processing time
- **Audio Duration**: Precise duration calculation
- **TTS RTF**: Processing efficiency
- **Quality Assessment**: WER, accuracy, confidence from STT evaluation

### Metrics Generated

| Metric | Unit | Description | Threshold |
|--------|------|-------------|-----------|
| `tts_latency` | seconds | TTS processing time | - |
| `audio_duration` | seconds | Generated audio length | - |
| `tts_rtf` | x | TTS Real-Time Factor | < 1.0 preferred |
| `wer` | ratio | Quality assessment via STT | ≤ 0.15 |
| `accuracy` | percent | Quality assessment via STT | ≥ 85% |
| `confidence` | ratio | STT evaluator confidence | 0.0 - 1.0 |

---

## 3. Isolated STT Testing Process

### Purpose
Evaluate STT accuracy and performance independently, using standardized audio generation.

### Process Flow
```
Input Text → TTS Preparation → Audio File → STT Vendor → Transcript → Quality Metrics
```

### Detailed Steps

#### Step 1: Input Configuration
- **Input**: Text to transcribe (ground truth)
- **Configuration**:
  - `mode: "isolated"`
  - `service: "stt"`
  - `vendors`: List of STT vendors to test
  - Model configurations per vendor

#### Step 2: Audio Preparation
- **TTS Generation**: Uses ElevenLabs as default audio generator
- **Standardization**: Consistent voice and model for fair STT comparison
- **Parameters**:
  ```python
  tts_params = {
      "model_id": "eleven_flash_v2_5",
      "voice": "21m00Tcm4TlvDq8ikWAM"
  }
  ```

#### Step 3: STT Processing
- **Process**: Transcribe prepared audio using selected STT vendor
- **Multiple Vendors**: If multiple vendors selected, uses same audio file
- **Timing**: Precise measurement of STT-only performance

#### Step 4: Quality Assessment
- **Direct Comparison**: Compare STT output with original input text
- **Metrics**: WER, accuracy, and vendor-provided confidence

### Metrics Generated

| Metric | Unit | Description | Threshold |
|--------|------|-------------|-----------|
| `stt_latency` | seconds | STT processing time | - |
| `audio_duration` | seconds | Input audio length | - |
| `stt_rtf` | x | STT Real-Time Factor | < 1.0 preferred |
| `wer` | ratio | Transcription accuracy | ≤ 0.15 |
| `accuracy` | percent | Transcription accuracy | ≥ 85% |
| `confidence` | ratio | STT vendor confidence | 0.0 - 1.0 |

---

## Metric Calculation Details

### Word Error Rate (WER)
```python
def calculate_wer(reference: str, hypothesis: str) -> float:
    """Industry-standard WER calculation using jiwer library."""
    if JIWER_AVAILABLE:
        return jiwer.wer(reference, hypothesis)
    else:
        # Fallback with basic normalization
        return levenshtein_distance_normalized(reference, hypothesis)
```

**Normalization Steps** (when using jiwer):
1. Lowercase conversion
2. Punctuation removal
3. Whitespace normalization
4. Special character handling

### Real-Time Factor (RTF)
```python
def calculate_rtf(latency: float, audio_duration: float) -> float:
    """RTF = processing_time / audio_duration"""
    if audio_duration <= 0:
        return None
    
    rtf = latency / audio_duration
    
    # Validation: RTF should typically be 0.01 - 100
    if rtf < 0.01 or rtf > 100:
        logger.warning(f"Unusual RTF value: {rtf}")
    
    return rtf
```

**Interpretation**:
- RTF < 1.0: Faster than real-time (good)
- RTF = 1.0: Real-time processing
- RTF > 1.0: Slower than real-time

### Audio Duration Calculation
**Priority Order**:
1. **Mutagen Library**: Most reliable for all formats
2. **Wave Module**: For WAV files specifically  
3. **Size-based Estimation**: Last resort with format-specific assumptions

```python
def get_audio_duration_seconds(audio_path: str) -> float:
    # Try mutagen first (supports MP3, MP4, FLAC, OGG, etc.)
    if MutagenFile:
        duration = mutagen_duration(audio_path)
        if validate_duration(duration):
            return duration
    
    # Try wave module for WAV
    if is_wav_file(audio_path):
        duration = wave_duration(audio_path)
        if validate_duration(duration):
            return duration
    
    # Size-based fallback with format-specific bitrate assumptions
    return estimate_duration_from_size(audio_path)
```

### Confidence Score Validation
```python
def validate_confidence(confidence: float, vendor: str) -> float:
    """Normalize confidence to 0.0-1.0 range."""
    if confidence is None:
        return 0.0
    
    if confidence > 1.0 and confidence <= 100.0:
        return confidence / 100.0  # Convert percentage
    
    return max(0.0, min(1.0, confidence))  # Clamp to valid range
```

---

## Database Schema

### Core Tables
- **`runs`**: Test execution metadata
- **`run_items`**: Individual test instances
- **`metrics`**: Calculated performance metrics
- **`artifacts`**: Audio and transcript files

### Relationships
```sql
runs (1) → (*) run_items (1) → (*) metrics
run_items (1) → (*) artifacts
```

---

## Error Handling and Edge Cases

### Audio Duration Edge Cases
- **Zero/negative duration**: Return 0.0, log warning
- **Unrealistic duration** (>24 hours): Return 0.0, log warning
- **File not found**: Return 0.0, log warning
- **Corrupted audio**: Fallback to size estimation

### WER Calculation Edge Cases
- **Empty reference**: Return 1.0 if hypothesis exists, 0.0 if both empty
- **Empty hypothesis**: Return 1.0
- **Identical text**: Return 0.0
- **Case/punctuation differences**: Normalized by jiwer

### RTF Calculation Edge Cases
- **Zero audio duration**: Return None
- **Negative values**: Return None, log warning
- **Extreme values**: Log warning but return value

---

## Quality Assurance

### Validation Requirements
1. **Metric Precision**: All calculations accurate to 3 decimal places
2. **Timing Precision**: Using `time.perf_counter()` for monotonic timing
3. **Edge Case Handling**: Graceful degradation for all error conditions
4. **Cross-validation**: Results comparable to industry standard tools

### Testing Protocol
- **Unit Tests**: Individual metric calculations
- **Integration Tests**: Full process workflows
- **Performance Tests**: Load and precision testing
- **Edge Case Tests**: Error conditions and boundary values

---

## Performance Optimization

### Timing Precision
- **High-precision timing**: `time.perf_counter()` instead of `time.time()`
- **Monotonic clock**: Unaffected by system time adjustments
- **Microsecond precision**: Better than millisecond accuracy

### Audio Processing
- **Container-aware parsing**: Format-specific duration extraction
- **Efficient fallbacks**: Size-based estimation when parsing fails
- **Caching**: Duration calculations cached per file

### Database Optimization
- **Batch inserts**: Multiple metrics inserted together
- **Indexed queries**: Fast retrieval by run_id, vendor, metric type
- **JSON storage**: Flexible metadata without schema changes

---

## Production Deployment Checklist

### ✅ Prerequisites
- [ ] jiwer library installed for accurate WER calculation
- [ ] mutagen library installed for audio duration parsing
- [ ] All vendor API keys configured
- [ ] Database schema initialized

### ✅ Validation Tests
- [ ] Metrics validation test suite passes 100%
- [ ] Cross-validation with industry standard tools
- [ ] Performance benchmarks within acceptable ranges
- [ ] Edge case handling verified

### ✅ Monitoring
- [ ] Metric calculation errors logged and monitored
- [ ] Unusual RTF values flagged for investigation
- [ ] Audio duration parsing failures tracked
- [ ] API response time monitoring

---

## Troubleshooting Guide

### Common Issues

#### WER Scores Too High
- **Check text normalization**: Verify punctuation/case handling
- **Audio quality**: Ensure clean TTS generation
- **Model selection**: Use appropriate STT models for content type

#### Unrealistic RTF Values
- **Audio duration errors**: Check duration calculation accuracy
- **Timing issues**: Verify perf_counter usage
- **Processing delays**: Check for I/O bottlenecks

#### Confidence Score Issues
- **Range validation**: Ensure 0.0-1.0 normalization
- **Vendor differences**: Account for different confidence scales
- **Missing values**: Implement appropriate defaults

### Debug Tools
- **Metrics validation script**: `/app/metrics_validation_test.py`
- **Process documentation**: This document
- **Backend logs**: Check for calculation warnings
- **Database inspection**: Verify stored metric values