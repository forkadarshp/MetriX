### Metrics Findings and Calculation Guide

This document reassesses the current metric calculations in `backend/server.py` and defines a production-grade interpretation for each metric. It also highlights caveats and concrete recommendations to ensure accurate, consistent results in production.

## Scope
- TTS metrics: latency, time-to-first-byte, audio duration, TTS real-time factor
- STT metrics: latency, confidence, WER/accuracy, STT real-time factor
- E2E metrics: combined latencies
- Aggregations: percentiles and dashboard summaries

## Timing primitives
- All timings use `time.perf_counter()` (high-precision monotonic). This is the right choice for latency measurements and avoids issues with system clock changes.

## Data dictionary (authoritative definitions)

| Metric name | Unit | What it measures (concept) | How measured (current) | Includes | Excludes | Key caveats |
| --- | --- | --- | --- | --- | --- | --- |
| `tts_latency` | seconds | API time to synthesize speech | From request start to last audio byte received. ElevenLabs: iterate generator; Deepgram: streaming `POST` via `httpx` | Network roundtrip, server processing time at vendor | Local file I/O (writing audio to disk) | For non-streaming vendors, equivalent to request duration; for streaming, measured until entire stream finishes |
| `tts_ttfb` | seconds | Time to first audio byte of TTS stream | Captured when first chunk is seen in stream loop | Network handshake, vendor queueing until first byte | Remaining stream time, local file I/O | Only populated where streaming is implemented (ElevenLabs, Deepgram in current code) |
| `stt_latency` | seconds | Time to obtain final STT result | From STT request start to completion | Network upload of the audio buffer + vendor processing time | Local file I/O (reading audio off disk happens before timing) | Upload time is included and can dominate for large files; no STT TTFB captured yet |
| `e2e_latency` | seconds | End-to-end time for chained TTS→STT | Sum(`tts_latency` + `stt_latency`) | Vendor API time for TTS + STT | Any local file I/O between TTS and STT, queueing in our app | Not wall-clock; excludes local write/read time |
| `audio_duration` | seconds | Playback length of the generated audio | Prefer TTS-provided duration (Deepgram WAV calc), else `get_audio_duration_seconds` (Mutagen → WAV → size-based) | Accurate duration when Mutagen/WAV is available | N/A | MP3/OGG size-based fallback is approximate; WAV and Mutagen are most reliable |
| `tts_rtf` | x (ratio) | Real-Time Factor for TTS | `tts_latency / audio_duration` with validation | — | — | If duration is approximate (e.g., MP3 without Mutagen), RTF can be skewed |
| `stt_rtf` | x (ratio) | Real-Time Factor for STT | `stt_latency / audio_duration` with validation | — | — | Includes upload time; not pure compute time |
| `wer` | ratio (0..1) | Word Error Rate | Uses `jiwer.wer(ref, hyp)` when available; otherwise a normalized Levenshtein distance over tokenized words | Lower is better; 0 = perfect | — | jiwer handles normalization/punctuation better; fallback is less accurate |
| `accuracy` | percent (0..100) | Accuracy derived from WER | `100 * (1 - wer)` | — | — | Directly tied to WER quality |
| `confidence` | ratio (0..1) | Vendor-reported confidence | Normalized via `validate_confidence`: clamps to [0,1], converts 2..100 to percent | Vendor’s scoring schema | — | Vendor scales differ; never equate across vendors without calibration |
| `p50`, `p90` | seconds | Percentiles of a metric in time window | Order values, linear interpolation over index | — | — | Simple implementation; sensitive to outliers; computed over last N days |

## Current implementation and references
- TTS (ElevenLabs) latency and TTFB: streaming generator, timing excludes file I/O.
- TTS (Deepgram Speak) latency and TTFB: streaming via `httpx`, excludes file I/O.
- STT (Deepgram) latency: reads file to memory first, starts timer before request, includes upload; no TTFB currently.
- Duration: `get_audio_duration_seconds` attempts Mutagen → WAV → size-based estimates; Deepgram WAV duration optionally returned based on bytes-per-second calc.
- RTF: `calculate_rtf` validates inputs and warns on extreme values but still returns the ratio.
- WER: prefers `jiwer`; fallback uses normalized word-level Levenshtein.
- E2E: in chained mode, `e2e_latency = tts_latency + stt_latency` (excludes local I/O between phases).

Code locations (for maintainers):
- `calculate_wer` and fallback: `backend/server.py` lines ~573–634
- `get_audio_duration_seconds`: `backend/server.py` lines ~636–728
- `calculate_rtf`: `backend/server.py` lines ~730–765
- ElevenLabs TTS with TTFB: `backend/server.py` lines ~237–299 (synthesis)
- Deepgram STT: `backend/server.py` lines ~342–398
- Deepgram TTS with TTFB: `backend/server.py` lines ~399–505
- Isolated-mode metrics: `backend/server.py` lines ~1211–1416
- Chained-mode metrics: `backend/server.py` lines ~1418–1548
- Percentiles endpoint: `backend/server.py` lines ~984–1039

## Interpretation guidance
- Latency metrics are intentionally measured as vendor-API-only timings. This provides a clean, vendor-comparable number but omits local disk/network overhead your application introduces. For operational SLOs, consider adding wall-clock timing variants (see recommendations).
- STT latency currently includes upload time; TTS latency excludes download file I/O. These asymmetries are by design and should be documented wherever metrics are presented.
- RTF is only as good as your duration. Prefer WAV or formats with reliable metadata (Mutagen). Avoid size-based estimates for production KPIs.
- Confidence is vendor-defined; treat as a hint, not a cross-vendor comparable metric.

## Known caveats and risks
- Audio duration accuracy:
  - WAV via `wave` is reliable.
  - Mutagen generally reliable across compressed formats.
  - Size-based estimation (e.g., assuming 128 kbps) is approximate and can be off by 10–50% depending on codec/bitrate.
- STT latency includes upload. For large audio files or slow links, this can dwarf processing time.
- E2E latency excludes local file write/read between TTS and STT. Real user experience will be slightly slower than `e2e_latency` suggests.
- No STT TTFB yet. Vendors that stream partial hypotheses can provide much lower TTFB than final-result latency indicates.
- Dummy vendor paths are simulated; do not use these results for production baselines.

## Thresholds and pass/fail
- WER threshold currently set at `0.15` (15%). This may be appropriate for clean audio and general English but should be revisited per domain, language, and acoustic conditions.

## Aggregations and dashboard
- Percentiles: p50 and p90 computed via linear interpolation after sorting values for the selected metric over the lookback window (default 7 days). Sensitive to outliers and small sample sizes.
- Success rate: derived from run statuses (`completed / total`). Not a stored metric.
- Service mix and vendor usage: derived counts from presence of metric names per run item.

## Production-grade recommendations
1) Capture wall-clock timings alongside API timings
   - Add: `tts_wallclock`, `stt_wallclock`, `e2e_wallclock` measured with timers that bracket local file I/O and orchestration.
   - Keep existing API-only metrics for vendor comparability.

2) Break down STT timing
   - Add: `stt_upload_time` (bytes sent / upload duration), `stt_processing_time` (vendor compute), optionally `stt_ttfb` (time to first partial if streaming API is used).

3) Symmetric I/O capture for TTS
   - Add: `tts_download_time` (time to stream audio to client) and optionally `tts_decode_time` if post-processing/format conversion is performed locally.

4) Prefer reliable duration sources
   - Standardize on WAV (PCM) or ensure Mutagen is installed in production. Avoid size-based estimation in KPI reports; treat it as best-effort only.

5) Normalize and document text preprocessing for WER
   - When using `jiwer`, explicitly configure consistent normalization (e.g., case-folding, punctuation handling) to match your business requirements.

6) Record versioned metadata
   - Persist vendor model IDs, voices, language, and our own app version with each metric row to enable regression analysis.

7) Outlier handling
   - Consider winsorization or trimming for percentile dashboards to reduce volatility from transient spikes.

8) Units and presentation
   - Store seconds; present ms on the UI for readability. Always show number of samples used in aggregations.

9) Sampling methodology
   - For performance studies, run multiple trials per condition and use median (p50) with p90 bands. Avoid single-run conclusions.

10) Health/guardrails
   - Add validation to flag negative or zero durations, and unusually high RTFs (>100) for review. Current code logs warnings; you can also persist a `flag_anomaly` boolean.

## Example changes to implement (backlog)
- Add new metrics (API and wall-clock):
  - `tts_wallclock`, `stt_wallclock`, `e2e_wallclock`
  - `stt_upload_time`, `stt_processing_time`, `stt_ttfb`
  - `tts_download_time`
- Capture timestamps:
  - `tts_started_at`, `tts_ended_at`, `stt_started_at`, `stt_ended_at` for precise tracing.
- Enforce WAV output for TTS when accuracy of `audio_duration` is critical, or ensure Mutagen is deployed.
- Add STT streaming path for vendors that support it to measure `stt_ttfb`.

## Operational guidance
- Use API-only metrics for vendor comparisons and model changes.
- Use wall-clock metrics for SLOs, capacity planning, and user experience.
- Track both sets simultaneously in production to avoid blind spots.

## Validation checklist before go-live
- Mutagen installed and functioning for all relevant audio types.
- WAV preferred for TTS in benchmarking runs, unless the product mandates compressed formats.
- Percentile endpoints validated against known distributions.
- WER normalization configured and tested on domain-specific text.
- Metrics export clearly labels whether values are API-only or wall-clock.

## Glossary
- TTFB: Time to First Byte — initial response latency for a streamed or chunked response.
- RTF: Real-Time Factor — processing speed relative to audio length. RTF < 1 means faster than real time.

If you need, we can implement the backlog items above to bring the system to production-grade fidelity without changing the existing vendor-comparable metrics.


