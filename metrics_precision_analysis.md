# TTS/STT Metrics Precision Analysis & Issues

## Executive Summary

**CRITICAL**: The current metric calculation implementation has several precision issues that must be addressed before production deployment. This document analyzes each metric calculation and provides recommendations for fixes.

## Current Metrics Overview

The system calculates the following metrics across three modes:

### Metrics by Mode:
- **Isolated TTS**: `tts_latency`, `audio_duration`, `tts_rtf`, `wer`, `accuracy`, `confidence`
- **Isolated STT**: `stt_latency`, `audio_duration`, `stt_rtf`, `wer`, `accuracy`, `confidence`  
- **Chained E2E**: `e2e_latency`, `tts_latency`, `stt_latency`, `audio_duration`, `tts_rtf`, `stt_rtf`, `wer`, `confidence`

## CRITICAL ISSUES IDENTIFIED

### 1. 🚨 WER (Word Error Rate) Calculation - HIGH SEVERITY

**Current Implementation**: Custom Levenshtein distance algorithm (lines 519-537)

**Problems**:
- ❌ No punctuation normalization
- ❌ Basic case conversion only (.lower())  
- ❌ No handling of multiple whitespaces
- ❌ No special character normalization
- ❌ Doesn't follow ASR evaluation standards

**Industry Standard**: Should use `jiwer` library which implements proper ASR evaluation

**Impact**: WER scores could be 20-50% off from industry standard calculations

**Example Issue**:
```python
# Current: 
reference = "Hello world."
hypothesis = "hello world"
# WER = 0.5 (1 substitution / 2 words) - WRONG!

# Should be: WER = 0.0 after proper normalization
```

### 2. 🚨 Audio Duration Calculation - HIGH SEVERITY

**Current Implementation**: Multi-tier fallback with hardcoded assumptions (lines 539-591)

**Problems**:
- ❌ MP3 bitrate assumption (32kbps) often wrong - could be 128-320kbps
- ❌ PCM format assumptions (24kHz mono 16-bit) may not match actual
- ❌ File size fallbacks unreliable for compressed formats
- ❌ Duration bounds (3600s limit) could reject valid content
- ❌ Complex fallback logic prone to edge case failures

**Impact**: RTF calculations completely unreliable if duration is wrong

**Better Approach**: Use proper audio analysis libraries consistently

### 3. 🚨 RTF (Real-Time Factor) Calculation - MEDIUM SEVERITY

**Current Formula**: `rtf = latency / audio_duration`

**Problems**:
- ❌ Depends on potentially inaccurate duration calculation
- ❌ No bounds checking (RTF should typically be 0.1x - 10x)
- ❌ Returns `None` for "unrealistic" durations, hiding potential issues

**Industry Standard**: RTF should be validated against reasonable bounds

### 4. 🚨 Timing Precision - MEDIUM SEVERITY

**Current Implementation**: Using `time.time()` for latency measurement

**Problems**:
- ❌ `time.time()` affected by system clock adjustments
- ❌ Lower precision than available alternatives
- ❌ Not monotonic - can go backwards

**Better Approach**: Use `time.perf_counter()` for high-precision monotonic timing

### 5. ⚠️ Confidence Score Handling - LOW SEVERITY

**Problems**:
- ❌ Hardcoded fallback values (e.g., 0.95 for ElevenLabs)
- ❌ Inconsistent confidence handling across vendors
- ❌ No validation of confidence ranges (should be 0.0-1.0)

### 6. ⚠️ Threshold Inconsistencies - LOW SEVERITY

**Problems**:
- ❌ WER threshold = 0.1 for isolated TTS mode
- ❌ WER threshold = 0.15 for chained mode
- ❌ No documented rationale for different thresholds

## Accuracy Calculation Issues

**Current Formula**: `accuracy = (1 - wer) * 100`

**Problems**:
- ❌ Depends on inaccurate WER calculation
- ❌ Doesn't account for ASR-specific accuracy measures
- ❌ No consideration of different accuracy types (word-level vs character-level)

## PRODUCTION READINESS ASSESSMENT

| Metric | Current Status | Severity | Production Ready? |
|--------|---------------|----------|-------------------|
| WER | ❌ Inaccurate algorithm | HIGH | **NO** |
| Audio Duration | ❌ Unreliable fallbacks | HIGH | **NO** |
| RTF | ❌ Depends on duration | MEDIUM | **NO** |
| Latency | ❌ Imprecise timing | MEDIUM | **NO** |
| Accuracy | ❌ Depends on WER | HIGH | **NO** |
| Confidence | ⚠️ Hardcoded values | LOW | MAYBE |

## IMMEDIATE ACTIONS REQUIRED

### Priority 1 (Must Fix Before Production):
1. **Replace WER calculation with jiwer library**
2. **Fix audio duration calculation reliability**
3. **Switch to perf_counter() for timing**
4. **Add RTF bounds validation**

### Priority 2 (Should Fix):
5. **Standardize confidence handling**
6. **Align WER thresholds across modes**
7. **Add metric validation ranges**

## TESTING REQUIREMENTS

Before production deployment, ALL metrics must be validated with:
1. **Edge cases**: Empty strings, very short/long audio, unusual formats
2. **Cross-validation**: Compare results with industry standard tools
3. **Precision testing**: Verify accuracy to at least 3 decimal places
4. **Load testing**: Ensure precision maintained under concurrent load

## Next Steps

1. **Implement fixes** for Priority 1 issues
2. **Create comprehensive test suite** with known-good reference data
3. **Validate metrics** against industry standard implementations
4. **Document precision guarantees** for each metric type