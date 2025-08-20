import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './components/ui/select';
import { Textarea } from './components/ui/textarea';
import { Badge } from './components/ui/badge';
import { Progress } from './components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Alert, AlertDescription } from './components/ui/alert';
import { Separator } from './components/ui/separator';
import { Play, Pause, Volume2, BarChart3, Activity, Clock, Target, Zap, Mic, Speaker, FileText, Star, User, MessageSquare } from 'lucide-react';
import './App.css';

function ExportToolbar({ runs }) {
  const API_BASE_URL = import.meta?.env?.REACT_APP_BACKEND_URL || process.env.REACT_APP_BACKEND_URL;
  const collectIds = () => {
    const ids = [];
    (runs || []).forEach((run) => (run.items || []).forEach((it) => ids.push(it.id)));
    return ids;
  };
  const download = async (format, all=false) => {
    try {
      const body = all ? { format, all: true } : { format, run_item_ids: collectIds() };
      const resp = await fetch(`${API_BASE_URL}/api/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!resp.ok) throw new Error('Export failed');
      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `benchmark_export.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Export error', e);
      alert('Export failed');
    }
  };
  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={() => download('csv', false)}>CSV (Selected)</Button>
      <Button variant="outline" size="sm" onClick={() => download('csv', true)}>CSV (All)</Button>
      <Button variant="outline" size="sm" onClick={() => download('pdf', false)}>PDF (Selected)</Button>
      <Button variant="outline" size="sm" onClick={() => download('pdf', true)}>PDF (All)</Button>
    </div>
  );
}


const API_BASE_URL = import.meta?.env?.REACT_APP_BACKEND_URL || process.env.REACT_APP_BACKEND_URL;

function App() {
  const [dashboardStats, setDashboardStats] = useState({});
  const [insights, setInsights] = useState({ service_mix: {}, vendor_usage: { tts: {}, stt: {} }, top_vendor_pairings: [] });
  const [runs, setRuns] = useState([]);
  const [scripts, setScripts] = useState([]);
  const [filters, setFilters] = useState({ vendor: 'all', service: 'all' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  
  // Form states
  const [quickTestForm, setQuickTestForm] = useState({
    text: 'Welcome to our banking services. How can I help you today?',
    vendors: ['elevenlabs', 'deepgram'],
    mode: 'isolated',
    service: 'tts',
    models: {
      elevenlabs: { tts_model: 'eleven_flash_v2_5', stt_model: 'scribe_v1', voice_id: '21m00Tcm4TlvDq8ikWAM' },
      deepgram: { tts_model: 'aura-2-thalia-en', stt_model: 'nova-3' },
      azure_openai: { tts_model: 'tts-1', stt_model: 'whisper-1', voice: 'alloy' }
    },
    chain: { tts_vendor: 'elevenlabs', stt_vendor: 'deepgram' }
  });
  
  const [batchTestForm, setBatchTestForm] = useState({
    vendors: ['elevenlabs', 'deepgram'],
    mode: 'isolated',
    service: 'tts',
    scriptIds: [],
    batchScriptInput: '',
    batchScriptFormat: 'txt',
    models: {
      elevenlabs: { tts_model: 'eleven_flash_v2_5', stt_model: 'scribe_v1', voice_id: '21m00Tcm4TlvDq8ikWAM' },
      deepgram: { tts_model: 'aura-2-thalia-en', stt_model: 'nova-3' },
      azure_openai: { tts_model: 'tts-1', stt_model: 'whisper-1', voice: 'alloy' }
    },
    chain: { tts_vendor: 'elevenlabs', stt_vendor: 'deepgram' }
  });

  // Fetch functions
  const fetchDashboardStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/dashboard/stats`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setDashboardStats(data);
    } catch (err) {
      console.error('Error fetching dashboard stats:', err);
    }
  }, []);

  const fetchInsights = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/dashboard/insights`);
      if (!response.ok) throw new Error('Failed to fetch insights');
      const data = await response.json();
      setInsights(data);
    } catch (err) {
      console.error('Error fetching dashboard insights:', err);
    }
  }, []);

  const fetchRuns = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/runs`);
      if (!response.ok) throw new Error('Failed to fetch runs');
      const data = await response.json();
      setRuns(data.runs || []);
    } catch (err) {
      console.error('Error fetching runs:', err);
    }
  }, []);

  const fetchScripts = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/scripts`);
      if (!response.ok) throw new Error('Failed to fetch scripts');
      const data = await response.json();
      setScripts(data.scripts || []);
    } catch (err) {
      console.error('Error fetching scripts:', err);
    }
  }, []);

  useEffect(() => {
    fetchDashboardStats();
    fetchInsights();
    fetchRuns();
    fetchScripts();
  }, [fetchDashboardStats, fetchRuns, fetchScripts]);

  // Auto refresh dashboard stats every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (activeTab === 'dashboard') {
        fetchDashboardStats();
        fetchInsights();
        fetchRuns();
      }
    }, 30000);
    
    return () => clearInterval(interval);
  }, [activeTab, fetchDashboardStats, fetchRuns]);

  const handleQuickTest = async () => {
    if (!quickTestForm.text.trim()) {
      setError('Please enter text to test');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('text', quickTestForm.text);
      formData.append('vendors', quickTestForm.vendors.join(','));
      formData.append('mode', quickTestForm.mode);
      // attach config as JSON
      const config = { service: quickTestForm.mode === 'isolated' ? quickTestForm.service : undefined, models: quickTestForm.models, chain: quickTestForm.chain };
      formData.append('config', JSON.stringify(config));

      const response = await fetch(`${API_BASE_URL}/api/runs/quick`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to create test');
      }

      const result = await response.json();
      
      // Refresh runs and switch to results tab
      setTimeout(() => {
        fetchRuns();
        setActiveTab('results');
      }, 1000);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBatchTest = async () => {
    const hasScriptIds = batchTestForm.scriptIds.length > 0;
    const hasPastedBatch = !!(batchTestForm.batchScriptInput && batchTestForm.batchScriptInput.trim());
    if (!hasScriptIds && !hasPastedBatch) {
      setError('Add at least one input: select scripts or paste batch script content');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const runData = {
        mode: batchTestForm.mode,
        vendors: batchTestForm.vendors,
        script_ids: batchTestForm.scriptIds,
        config: {
          service: batchTestForm.mode === 'isolated' ? batchTestForm.service : undefined,
          models: batchTestForm.models,
          chain: batchTestForm.chain
        }
      };

      if (hasPastedBatch) {
        runData.batch_script_input = batchTestForm.batchScriptInput;
        runData.batch_script_format = batchTestForm.batchScriptFormat || 'txt';
      }

      const response = await fetch(`${API_BASE_URL}/api/runs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(runData)
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to create batch test');
      }

      // Refresh runs and switch to results tab
      setTimeout(() => {
        fetchRuns();
        setActiveTab('results');
      }, 1000);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-emerald-500/10 text-emerald-700 border-emerald-200';
      case 'running': return 'bg-blue-500/10 text-blue-700 border-blue-200';
      case 'failed': return 'bg-red-500/10 text-red-700 border-red-200';
      default: return 'bg-gray-500/10 text-gray-700 border-gray-200';
    }
  };

  const formatLatency = (latency) => {
    if (!latency) return 'N/A';
    return `${(latency * 1000).toFixed(0)}ms`;
  };



  const StatCard = ({ icon: Icon, title, value, subtitle, trend }) => (
    <Card className="relative overflow-hidden">
      <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-500/5 to-purple-500/5 rounded-full translate-x-16 -translate-y-16" />
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-gray-600">{title}</CardTitle>
        <Icon className="h-4 w-4 text-blue-600" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-gray-900">{value}</div>
        {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        {trend && (
          <div className="flex items-center mt-2">
            <span className="text-xs text-emerald-600">↗ {trend}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );

  const RunResultCard = ({ run }) => {
    const [expanded, setExpanded] = useState(false);

    const classifyService = (item) => {
      if (item.transcript && !item.audio_path) return 'stt';
      if (item.audio_path && !item.transcript) return 'tts';
      if (item.audio_path && item.transcript) return 'e2e';
      return 'unknown';
    };

    const renderServiceBadge = (item) => {
      const service = item.transcript && item.audio_path
        ? 'E2E'
        : item.transcript
        ? 'STT'
        : item.audio_path
        ? 'TTS'
        : 'Unknown';
      const color = service === 'E2E' ? 'bg-indigo-500/10 text-indigo-700 border-indigo-200'
        : service === 'STT' ? 'bg-green-500/10 text-green-700 border-green-200'
        : service === 'TTS' ? 'bg-purple-500/10 text-purple-700 border-purple-200'
        : 'bg-gray-500/10 text-gray-700 border-gray-200';
      return <Badge variant="outline" className={color}>{service}</Badge>;
    };

    const MetricBadge = ({ name, value }) => {
      const num = parseFloat(value);
      
      // Enhanced badge with color coding and tooltips
      const enhancedBadge = (label, val, color, tooltip) => {
        const badgeClass = `text-xs ${color}`;
        return (
          <Badge variant="secondary" className={badgeClass} title={tooltip}>
            {label}: {val}
          </Badge>
        );
      };
      
      if (name === 'wer') {
        const percentage = (num * 100).toFixed(1);
        const color = num <= 0.1 ? 'bg-green-100 text-green-800 border-green-200' : 
                     num <= 0.3 ? 'bg-yellow-100 text-yellow-800 border-yellow-200' : 
                     'bg-red-100 text-red-800 border-red-200';
        const tooltip = `Word Error Rate: ${percentage}% - ${num <= 0.1 ? 'Excellent' : num <= 0.3 ? 'Good' : 'Needs Improvement'}. Lower is better.`;
        return enhancedBadge('WER', `${percentage}%`, color, tooltip);
      }
      

      
      if (name === 'confidence') {
        const percentage = (num * 100).toFixed(0);
        const color = num >= 0.8 ? 'bg-green-100 text-green-800 border-green-200' : 
                     num >= 0.6 ? 'bg-yellow-100 text-yellow-800 border-yellow-200' : 
                     'bg-red-100 text-red-800 border-red-200';
        const tooltip = `Model Confidence: ${percentage}% - ${num >= 0.8 ? 'High' : num >= 0.6 ? 'Medium' : 'Low'} confidence in transcription result.`;
        return enhancedBadge('Confidence', `${percentage}%`, color, tooltip);
      }
      
      // Enhanced latency badges
      if (name === 'e2e_latency') {
        const ms = (num * 1000).toFixed(0);
        const color = num <= 1 ? 'bg-green-100 text-green-800 border-green-200' : 
                     num <= 3 ? 'bg-yellow-100 text-yellow-800 border-yellow-200' : 
                     'bg-red-100 text-red-800 border-red-200';
        const tooltip = `End-to-End Latency: ${ms}ms - ${num <= 1 ? 'Fast' : num <= 3 ? 'Average' : 'Slow'} processing time.`;
        return enhancedBadge('E2E Latency', `${ms}ms`, color, tooltip);
      }
      
      if (name === 'tts_latency') {
        const ms = (num * 1000).toFixed(0);
        const color = num <= 0.5 ? 'bg-green-100 text-green-800 border-green-200' : 
                     num <= 2 ? 'bg-yellow-100 text-yellow-800 border-yellow-200' : 
                     'bg-red-100 text-red-800 border-red-200';
        const tooltip = `Text-to-Speech Latency: ${ms}ms - Time to generate audio from text.`;
        return enhancedBadge('TTS Latency', `${ms}ms`, color, tooltip);
      }
      
      if (name === 'stt_latency') {
        const ms = (num * 1000).toFixed(0);
        const color = num <= 0.5 ? 'bg-green-100 text-green-800 border-green-200' : 
                     num <= 2 ? 'bg-yellow-100 text-yellow-800 border-yellow-200' : 
                     'bg-red-100 text-red-800 border-red-200';
        const tooltip = `Speech-to-Text Latency: ${ms}ms - Time to transcribe audio to text.`;
        return enhancedBadge('STT Latency', `${ms}ms`, color, tooltip);
      }
      
      if (name === 'latency') {
        const ms = (num * 1000).toFixed(0);
        const color = num <= 1 ? 'bg-green-100 text-green-800 border-green-200' : 
                     num <= 3 ? 'bg-yellow-100 text-yellow-800 border-yellow-200' : 
                     'bg-red-100 text-red-800 border-red-200';
        const tooltip = `Processing Latency: ${ms}ms`;
        return enhancedBadge('Latency', `${ms}ms`, color, tooltip);
      }
      
      if (name === 'audio_duration') {
        const duration = num.toFixed(2);
        const tooltip = `Audio Duration: ${duration}s - Length of generated/processed audio file.`;
        return enhancedBadge('Audio Length', `${duration}s`, 'bg-blue-100 text-blue-800 border-blue-200', tooltip);
      }
      
      if (name === 'ttfb' || name === 'tts_ttfb') {
        const ms = (num * 1000).toFixed(0);
        const color = num <= 0.5 ? 'bg-green-100 text-green-800 border-green-200' : 
                     num <= 1.5 ? 'bg-yellow-100 text-yellow-800 border-yellow-200' : 
                     'bg-red-100 text-red-800 border-red-200';
        const tooltip = `Time to First Byte: ${ms}ms - ${num <= 0.5 ? 'Fast' : num <= 1.5 ? 'Average' : 'Slow'} initial response time. Measures server response latency.`;
        return enhancedBadge('TTFB', `${ms}ms`, color, tooltip);
      }
      
      if (name === 'rtf' || name === 'tts_rtf' || name === 'stt_rtf') {
        const rtfValue = num.toFixed(2);
        const color = num <= 0.5 ? 'bg-green-100 text-green-800 border-green-200' : 
                     num <= 1.0 ? 'bg-yellow-100 text-yellow-800 border-yellow-200' : 
                     'bg-red-100 text-red-800 border-red-200';
        const efficiency = num <= 0.5 ? 'Excellent' : num <= 1.0 ? 'Good' : 'Needs Improvement';
        const tooltip = `Real-Time Factor: ${rtfValue}x - ${efficiency} processing efficiency. ${num < 1 ? 'Faster than real-time' : 'Slower than real-time'}.`;
        return enhancedBadge('RTF', `${rtfValue}x`, color, tooltip);
      }
      
      return (
        <Badge variant="secondary" className="text-xs">
          {name}: {isNaN(num) ? value : num.toFixed(3)}
        </Badge>
      );
    };

    const AudioControls = ({ item, uniqueUserCount = 0, onRatingUpdate }) => {
      const [playing, setPlaying] = useState(false);
      const [showTranscript, setShowTranscript] = useState(false);
      const [transcriptText, setTranscriptText] = useState('');
      const [transcriptLoading, setTranscriptLoading] = useState(false);
      const [transcriptError, setTranscriptError] = useState('');
      const [showRatingModal, setShowRatingModal] = useState(false);
      const audioRef = React.useRef(null);
      const hasAudio = !!item.audio_path;
      const hasTranscript = !!item.transcript || !!item.audio_path;
      const audioFilename = hasAudio ? String(item.audio_path).split('/').pop() : null;
      const audioSrc = hasAudio ? `${API_BASE_URL}/api/audio/${audioFilename}` : null;

      const togglePlay = () => {
        if (!hasAudio) return;
        const el = audioRef.current;
        if (!el) return;
        if (playing) {
          el.pause();
          setPlaying(false);
        } else {
          el.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
        }
      };

      const fetchTranscriptWithRetry = async (retries = 2) => {
        if (!hasTranscript) return;
        
        setTranscriptLoading(true);
        setTranscriptError('');
        
        for (let attempt = 0; attempt <= retries; attempt++) {
          try {
            // First, check if we have an inline transcript
            if (item.transcript && item.transcript.trim()) {
              setTranscriptText(item.transcript);
              setTranscriptLoading(false);
              return;
            }
            
            // Try to fetch transcript file from API
            const tName = `transcript_${item.id}.txt`;
            console.log(`Attempting to fetch transcript: ${API_BASE_URL}/api/transcript/${tName}`);
            
            const resp = await fetch(`${API_BASE_URL}/api/transcript/${tName}`, {
              headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
              }
            });
            
            if (resp.ok) {
              const txt = await resp.text();
              if (txt && txt.trim()) {
                console.log('Successfully fetched transcript:', txt.substring(0, 100) + '...');
                setTranscriptText(txt);
                setTranscriptLoading(false);
                return;
              }
            } else {
              console.log(`Transcript API returned ${resp.status}: ${resp.statusText}`);
            }
            
            // If we're on the last attempt and still no transcript, set fallback
            if (attempt === retries) {
              if (item.transcript) {
                setTranscriptText(item.transcript);
              } else {
                setTranscriptError('Transcript not available yet. It may still be generating.');
                setTranscriptText('');
              }
            } else {
              // Wait before retry
              await new Promise(resolve => setTimeout(resolve, 1000));
            }
            
          } catch (e) {
            console.error(`Transcript fetch attempt ${attempt + 1} failed:`, e);
            
            if (attempt === retries) {
              // Last attempt failed
              if (item.transcript && item.transcript.trim()) {
                setTranscriptText(item.transcript);
              } else {
                setTranscriptError('Failed to load transcript. Please try again.');
                setTranscriptText('');
              }
            } else {
              // Wait before retry
              await new Promise(resolve => setTimeout(resolve, 1000));
            }
          }
        }
        
        setTranscriptLoading(false);
      };

      useEffect(() => {
        if (showTranscript) {
          fetchTranscriptWithRetry();
        }
      }, [showTranscript, item.id]);

      const getTranscriptDisplay = () => {
        if (transcriptLoading) {
          return (
            <div className="flex items-center space-x-2 text-blue-600">
              <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600"></div>
              <span>Loading transcript...</span>
            </div>
          );
        }
        
        if (transcriptError) {
          return (
            <div className="text-orange-600 text-xs">
              {transcriptError}
              <button 
                onClick={fetchTranscriptWithRetry}
                className="ml-2 underline hover:no-underline"
              >
                Retry
              </button>
            </div>
          );
        }
        
        if (transcriptText && transcriptText.trim()) {
          return (
            <div className="text-gray-800">
              <div className="font-medium text-xs text-gray-500 mb-1">Transcript:</div>
              <div>{transcriptText}</div>
            </div>
          );
        }
        
        return (
          <div className="text-gray-500 text-xs">
            Transcript will appear here once available.
            <br />
            <span className="text-xs text-gray-400">
              {hasTranscript ? 'Processing...' : 'No transcript available for this item.'}
            </span>
          </div>
        );
      };

      return (
        <div className="flex items-center space-x-2">
          {hasAudio && (
            <>
              <audio ref={audioRef} src={audioSrc} onEnded={() => setPlaying(false)} preload="none" />
              <Button variant="outline" size="sm" onClick={togglePlay}>
                {playing ? <Pause className="h-3 w-3 mr-1" /> : <Play className="h-3 w-3 mr-1" />}
                {playing ? 'Pause' : 'Play'}
              </Button>
            </>
          )}
          <>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => setShowTranscript(!showTranscript)}
              disabled={transcriptLoading}
            >
              <FileText className="h-3 w-3 mr-1" />
              {transcriptLoading ? 'Loading...' : showTranscript ? 'Hide Transcript' : 'Show Transcript'}
            </Button>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => setShowRatingModal(true)}
              className="bg-amber-50 hover:bg-amber-100 text-amber-700 border-amber-200"
            >
              <Star className="h-3 w-3 mr-1" />
              Rate
              {uniqueUserCount > 0 && (
                <span className="ml-1 text-xs bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded-full">
                  {uniqueUserCount}
                </span>
              )}
            </Button>
            {showTranscript && (
              <div className="ml-2 max-w-xl text-xs bg-white p-3 rounded border shadow-sm">
                {getTranscriptDisplay()}
              </div>
            )}
          </>
          <RatingModal 
            item={item} 
            isOpen={showRatingModal} 
            onClose={() => setShowRatingModal(false)}
            onRatingUpdate={onRatingUpdate}
          />
        </div>
      );
    };

    const RatingModal = ({ item, isOpen, onClose, onRatingUpdate }) => {
      const [subjectiveMetrics, setSubjectiveMetrics] = useState([]);
      const [userRatings, setUserRatings] = useState({});
      const [userName, setUserName] = useState('');
      const [comments, setComments] = useState({});
      const [loading, setLoading] = useState(false);
      const [existingRatings, setExistingRatings] = useState({});
      const [averageRatings, setAverageRatings] = useState({});

      const serviceType = classifyService(item);
      const actualServiceType = serviceType === 'e2e' ? 'tts' : serviceType;

      useEffect(() => {
        if (isOpen && actualServiceType !== 'unknown') {
          fetchSubjectiveMetrics();
          fetchExistingRatings();
        }
      }, [isOpen, actualServiceType, item.id]);

      const fetchSubjectiveMetrics = async () => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/subjective-metrics/${actualServiceType}`);
          if (response.ok) {
            const data = await response.json();
            setSubjectiveMetrics(data.subjective_metrics || []);
          }
        } catch (error) {
          console.error('Error fetching subjective metrics:', error);
        }
      };

      const fetchExistingRatings = async () => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/user-ratings/${item.id}`);
          if (response.ok) {
            const data = await response.json();
            const avgRatings = {};
            data.average_ratings.forEach(rating => {
              avgRatings[rating.subjective_metric_id] = {
                avg: rating.avg_rating,
                count: rating.rating_count
              };
            });
            setAverageRatings(avgRatings);
          }
        } catch (error) {
          console.error('Error fetching existing ratings:', error);
        }
      };

      const handleRatingChange = (metricId, rating) => {
        setUserRatings(prev => ({
          ...prev,
          [metricId]: rating
        }));
      };

      const handleCommentChange = (metricId, comment) => {
        setComments(prev => ({
          ...prev,
          [metricId]: comment
        }));
      };

      const handleSubmit = async () => {
        if (!userName.trim()) {
          alert('Please enter your name');
          return;
        }

        // Check if all metrics have been rated
        const missingRatings = subjectiveMetrics.filter(metric => !userRatings[metric.id]);
        if (missingRatings.length > 0) {
          const missingNames = missingRatings.map(metric => metric.name).join(', ');
          alert(`Please rate all metrics. Missing ratings for: ${missingNames}`);
          return;
        }

        setLoading(true);
        try {
          const response = await fetch(`${API_BASE_URL}/api/user-ratings`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              run_item_id: item.id,
              user_name: userName.trim(),
              ratings: userRatings,
              comments: comments
            })
          });

          if (response.ok) {
            alert('Rating submitted successfully!');
            fetchExistingRatings(); // Refresh average ratings
            if (onRatingUpdate) {
              onRatingUpdate(); // Refresh parent component's data
            }
            onClose();
            // Reset form
            setUserRatings({});
            setComments({});
            setUserName('');
          } else {
            const errorData = await response.json();
            alert(`Error submitting rating: ${errorData.detail || 'Unknown error'}`);
          }
        } catch (error) {
          console.error('Error submitting rating:', error);
          alert('Error submitting rating. Please try again.');
        } finally {
          setLoading(false);
        }
      };

      const renderStarRating = (metricId, currentRating = 0) => {
        return (
          <div className="flex items-center space-x-1">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                onClick={() => handleRatingChange(metricId, star)}
                className={`text-lg ${
                  star <= currentRating 
                    ? 'text-yellow-400 hover:text-yellow-500' 
                    : 'text-gray-300 hover:text-yellow-300'
                } transition-colors`}
              >
                <Star className="h-5 w-5 fill-current" />
              </button>
            ))}
            <span className="text-sm text-gray-600 ml-2">
              {currentRating > 0 ? `${currentRating}/5` : 'Not rated'}
            </span>
          </div>
        );
      };

      if (!isOpen) return null;

      return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900">
                  Rate {actualServiceType.toUpperCase()} Quality
                </h2>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={onClose}
                  className="text-gray-500 hover:text-gray-700"
                >
                  ✕
                </Button>
              </div>

              <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                <div className="text-sm font-medium text-gray-700 mb-1">Item Details:</div>
                <div className="text-sm text-gray-600">
                  <strong>Vendor:</strong> {item.vendor} | <strong>Service:</strong> {serviceType.toUpperCase()}
                </div>
                <div className="text-sm text-gray-600 mt-1">
                  <strong>Text:</strong> {item.text_input}
                </div>
              </div>

              <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <div className="text-sm text-blue-800">
                  <strong>Note:</strong> All metrics below are required. Please rate every aspect before submitting.
                </div>
              </div>

              <div className="mb-4">
                <Label htmlFor="userName" className="text-sm font-medium">Your Name *</Label>
                <Input
                  id="userName"
                  type="text"
                  value={userName}
                  onChange={(e) => setUserName(e.target.value)}
                  placeholder="Enter your name for tracking"
                  className="mt-1"
                />
              </div>

              <div className="space-y-6">
                {subjectiveMetrics.map((metric) => (
                  <div key={metric.id} className={`border rounded-lg p-4 ${!userRatings[metric.id] ? 'border-red-200 bg-red-50/50' : 'border-gray-200'}`}>
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <h3 className="font-medium text-gray-900">
                          {metric.name}
                          <span className="text-red-500 ml-1">*</span>
                        </h3>
                        <p className="text-sm text-gray-600 mt-1">{metric.description}</p>
                        {averageRatings[metric.id] && (
                          <div className="text-xs text-blue-600 mt-2">
                            Average: {averageRatings[metric.id].avg.toFixed(1)}/5 
                            ({averageRatings[metric.id].count} rating{averageRatings[metric.id].count !== 1 ? 's' : ''})
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div className="mb-3">
                      {renderStarRating(metric.id, userRatings[metric.id] || 0)}
                    </div>

                    <div>
                      <Label htmlFor={`comment-${metric.id}`} className="text-xs text-gray-600">
                        Optional Comment
                      </Label>
                      <Textarea
                        id={`comment-${metric.id}`}
                        value={comments[metric.id] || ''}
                        onChange={(e) => handleCommentChange(metric.id, e.target.value)}
                        placeholder="Add any additional feedback..."
                        rows={2}
                        className="mt-1 text-sm"
                      />
                    </div>
                  </div>
                ))}
              </div>

              {subjectiveMetrics.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  No subjective metrics available for {actualServiceType.toUpperCase()} services.
                </div>
              )}

              <div className="flex justify-end space-x-3 mt-6 pt-4 border-t">
                <Button variant="outline" onClick={onClose} disabled={loading}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleSubmit} 
                  disabled={loading || !userName.trim() || subjectiveMetrics.some(metric => !userRatings[metric.id])}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {loading ? (
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Submitting...</span>
                    </div>
                  ) : (
                    'Submit Rating'
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      );
    };

    const ItemCard = ({ item }) => {
      const [subjectiveRatings, setSubjectiveRatings] = useState({});
      const [uniqueUserCount, setUniqueUserCount] = useState(0);
      
      const fetchSubjectiveRatings = async () => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/user-ratings/${item.id}`);
          if (response.ok) {
            const data = await response.json();
            const ratings = {};
            data.average_ratings.forEach(rating => {
              ratings[rating.subjective_metric_id] = {
                name: rating.name,
                avg: rating.avg_rating,
                count: rating.rating_count,
                service_type: rating.service_type
              };
            });
            setSubjectiveRatings(ratings);
            setUniqueUserCount(data.unique_user_count || 0);
          }
        } catch (error) {
          console.error('Error fetching subjective ratings:', error);
        }
      };
      
      useEffect(() => {
        fetchSubjectiveRatings();
      }, [item.id]);
      
      return (
        <div className="border rounded-lg p-4 bg-gray-50/50">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              {item.vendor === 'elevenlabs' && <Speaker className="h-4 w-4 text-purple-600" />}
              {item.vendor === 'deepgram' && <Mic className="h-4 w-4 text-green-600" />}
              {item.vendor === 'aws' && <Zap className="h-4 w-4 text-orange-600" />}
              {item.vendor === 'azure_openai' && <MessageSquare className="h-4 w-4 text-blue-600" />}
              <span className="font-medium capitalize">{item.vendor.replace('_', ' ')}</span>
              {renderServiceBadge(item)}
              <Badge variant="outline" className={getStatusColor(item.status)}>
                {item.status}
              </Badge>
            </div>
            <AudioControls item={item} uniqueUserCount={uniqueUserCount} onRatingUpdate={fetchSubjectiveRatings} />
          </div>
        
        <div className="text-sm mb-3">
          <div className="font-medium text-gray-700 mb-1">Input:</div>
          <div className="text-gray-600 bg-white p-2 rounded border">
            {item.text_input}
          </div>
        </div>
        
        {item.transcript && (
          <div className="text-sm mb-3">
            <div className="font-medium text-gray-700 mb-1">Transcript:</div>
            <div className="text-gray-600 bg-white p-2 rounded border">
              {item.transcript}
            </div>
          </div>
        )}
        
        {item.metrics_summary && (
          <div className="space-y-3">
            {(() => {
              const metrics = item.metrics_summary.split('|').map((metric) => {
                const [name, value] = metric.split(':');
                return { name, value };
              });
              
              // Group metrics by type
              const performanceMetrics = metrics.filter(m => 
                ['ttfb', 'rtf', 'latency', 'tts_latency', 'stt_latency', 'e2e_latency', 'audio_duration'].includes(m.name)
              );
              const qualityMetrics = metrics.filter(m => 
                ['wer', 'bleu', 'rouge'].includes(m.name)
              );
              const otherMetrics = metrics.filter(m => 
                !['ttfb', 'rtf', 'latency', 'tts_latency', 'stt_latency', 'e2e_latency', 'audio_duration', 'wer', 'confidence', 'bleu', 'rouge'].includes(m.name)
              );
              
              // Add subjective metrics
              const subjectiveMetricsArray = Object.values(subjectiveRatings);
              
              return (
                <>
                  {performanceMetrics.length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Performance Metrics
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {performanceMetrics.map((metric, midx) => (
                          <MetricBadge key={midx} name={metric.name} value={metric.value} />
                        ))}
                      </div>
                    </div>
                  )}
                  {qualityMetrics.length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                        <Target className="h-3 w-3" />
                        Quality Metrics
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {qualityMetrics.map((metric, midx) => (
                          <MetricBadge key={midx} name={metric.name} value={metric.value} />
                        ))}
                      </div>
                    </div>
                  )}
                  {otherMetrics.length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                        <BarChart3 className="h-3 w-3" />
                        Other Metrics
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {otherMetrics.map((metric, midx) => (
                          <MetricBadge key={midx} name={metric.name} value={metric.value} />
                        ))}
                      </div>
                    </div>
                  )}
                  {subjectiveMetricsArray.length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                        <User className="h-3 w-3" />
                        User Ratings ({subjectiveMetricsArray.reduce((total, m) => total + m.count, 0)} total)
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {subjectiveMetricsArray.map((metric, midx) => (
                          <Badge 
                            key={midx} 
                            variant="secondary" 
                            className="text-xs bg-amber-100 text-amber-800 border-amber-200"
                            title={`Average of ${metric.count} user rating${metric.count !== 1 ? 's' : ''}`}
                          >
                            {metric.name}: {metric.avg.toFixed(1)}/5 ⭐
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        )}
      </div>
    );
  };

    return (
      <Card className="mb-4">
        <CardHeader className="cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <Badge variant="outline" className={getStatusColor(run.status)}>
                  {run.status}
                </Badge>
                <Badge variant="secondary">{run.mode}</Badge>
              </div>
              <div className="text-sm text-gray-500">
                {new Date(run.started_at).toLocaleString()}
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-sm">
                <span className="font-medium">{run.vendors?.length || 0}</span> vendors
              </div>
              <div className="text-sm">
                <span className="font-medium">{run.items?.length || 0}</span> tests
              </div>
            </div>
          </div>
        </CardHeader>
        
        {expanded && (
          <CardContent className="pt-0">
            {(() => {
              const items = run.items || [];
              const ttsItems = items.filter((it) => classifyService(it) === 'tts');
              const sttItems = items.filter((it) => {
                const svc = classifyService(it);
                return svc === 'stt' || svc === 'e2e';
              });
              return (
                <div className="space-y-8">
                  {ttsItems.length > 0 && (
                    <div className="space-y-4">
                      <div className="flex items-center gap-3 pb-2 border-b border-purple-200">
                        <Badge variant="outline" className="bg-purple-500/10 text-purple-700 border-purple-200 font-semibold">
                          <Speaker className="h-3 w-3 mr-1" />
                          TTS Results
                        </Badge>
                        <span className="text-sm text-gray-600">{ttsItems.length} item{ttsItems.length > 1 ? 's' : ''}</span>
                      </div>
                      <div className="space-y-4 pl-2">
                        {ttsItems.map((item) => (
                          <ItemCard key={item.id} item={item} />
                        ))}
                      </div>
                    </div>
                  )}
                  {sttItems.length > 0 && (
                    <div className="space-y-4">
                      <div className="flex items-center gap-3 pb-2 border-b border-green-200">
                        <Badge variant="outline" className="bg-green-500/10 text-green-700 border-green-200 font-semibold">
                          <Mic className="h-3 w-3 mr-1" />
                          STT Results
                        </Badge>
                        <span className="text-sm text-gray-600">{sttItems.length} item{sttItems.length > 1 ? 's' : ''}</span>
                      </div>
                      <div className="space-y-4 pl-2">
                        {sttItems.map((item) => (
                          <ItemCard key={item.id} item={item} />
                        ))}
                      </div>
                    </div>
                  )}
                  {ttsItems.length === 0 && sttItems.length === 0 && (
                    <div className="text-sm text-gray-500">No items to display.</div>
                  )}
                </div>
              );
            })()}
          </CardContent>
        )}
      </Card>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/40">
      {/* Header */}
      <div className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                  <BarChart3 className="h-4 w-4 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-gray-900">TTS/STT Benchmark</h1>
                  <p className="text-sm text-gray-500">Speech Technology Performance Dashboard</p>
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">
                <Activity className="h-3 w-3 mr-1" />
                Live
              </Badge>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-4 bg-white/60 backdrop-blur-sm border border-gray-200">
            <TabsTrigger value="dashboard" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
              <BarChart3 className="h-4 w-4 mr-2" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="quick-test" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
              <Zap className="h-4 w-4 mr-2" />
              Quick Test
            </TabsTrigger>
            <TabsTrigger value="batch-test" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
              <Target className="h-4 w-4 mr-2" />
              Batch Test
            </TabsTrigger>
            <TabsTrigger value="results" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
              <Activity className="h-4 w-4 mr-2" />
              Results
            </TabsTrigger>
          </TabsList>

          {/* Dashboard Tab */}
          <TabsContent value="dashboard" className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <StatCard
                icon={Target}
                title="Total Runs"
                value={dashboardStats.total_runs || 0}
                subtitle="Test executions"
              />
              <StatCard
                icon={Activity}
                title="Success Rate"
                value={`${dashboardStats.success_rate || 0}%`}
                subtitle="Completed successfully"
              />

              <StatCard
                icon={Clock}
                title="Avg Latency"
                value={`${(dashboardStats.avg_latency * 1000 || 0).toFixed(0)}ms`}
                subtitle="Processing time"
              />
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Service Mix (last 7 days)</CardTitle>
                <CardDescription>Distribution of TTS / STT / E2E tests</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                  {Object.entries(insights.service_mix || {}).map(([k, v]) => (
                    <div key={k} className="p-3 rounded-lg border bg-white flex items-center justify-between">
                      <span className="text-sm font-medium">{k}</span>
                      <Badge variant="secondary">{v}</Badge>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <div className="font-medium mb-2">Top Vendor Pairings</div>
                    <div className="space-y-2">
                      {(insights.top_vendor_pairings || []).map((p, i) => (
                        <div key={i} className="p-3 rounded-lg border bg-white flex items-center justify-between">
                          <div className="text-sm">
                            <div className="font-medium">TTS: {p.tts_vendor} • STT: {p.stt_vendor}</div>
                            <div className="text-xs text-gray-500">{p.tests} tests</div>
                          </div>
                          <Badge variant="outline">avg WER: {(p.avg_wer * 100).toFixed(1)}%</Badge>
                        </div>
                      ))}
                      {(insights.top_vendor_pairings || []).length === 0 && (
                        <div className="text-sm text-gray-500">No pairings yet</div>
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="font-medium mb-2">Vendor Usage</div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 rounded-lg border bg-white">
                        <div className="text-xs text-gray-500 mb-1">TTS</div>
                        <div className="space-y-1">
                          {Object.entries(insights.vendor_usage?.tts || {}).map(([k, v]) => (
                            <div key={k} className="flex items-center justify-between text-sm"><span className="capitalize">{k}</span><span className="text-gray-600">{v}</span></div>
                          ))}
                          {Object.keys(insights.vendor_usage?.tts || {}).length === 0 && (
                            <div className="text-sm text-gray-500">No data</div>
                          )}
                        </div>
                      </div>
                      <div className="p-3 rounded-lg border bg-white">
                        <div className="text-xs text-gray-500 mb-1">STT</div>
                        <div className="space-y-1">
                          {Object.entries(insights.vendor_usage?.stt || {}).map(([k, v]) => (
                            <div key={k} className="flex items-center justify-between text-sm"><span className="capitalize">{k}</span><span className="text-gray-600">{v}</span></div>
                          ))}
                          {Object.keys(insights.vendor_usage?.stt || {}).length === 0 && (
                            <div className="text-sm text-gray-500">No data</div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Recent Activity</CardTitle>
                <CardDescription>Latest test runs and their performance</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center gap-3 mb-4">
                  <div className="flex items-center space-x-2">
                    <Label>Vendor</Label>
                    <Select value={filters.vendor} onValueChange={(v) => setFilters({ ...filters, vendor: v })}>
                      <SelectTrigger className="w-40"><SelectValue placeholder="Vendor" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="elevenlabs">ElevenLabs</SelectItem>
                        <SelectItem value="deepgram">Deepgram</SelectItem>
                        <SelectItem value="aws">AWS</SelectItem>
                        <SelectItem value="azure_openai">Azure OpenAI</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Label>Service</Label>
                    <Select value={filters.service} onValueChange={(v) => setFilters({ ...filters, service: v })}>
                      <SelectTrigger className="w-40"><SelectValue placeholder="Service" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="tts">TTS</SelectItem>
                        <SelectItem value="stt">STT</SelectItem>
                        <SelectItem value="e2e">E2E</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {runs.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No test runs yet. Start with a quick test!
                  </div>
                ) : (
                  <div className="space-y-3">
                    {runs
                      .map((run) => ({
                        ...run,
                        items: (run.items || []).filter((it) => {
                          const vendorOk = filters.vendor === 'all' || it.vendor === filters.vendor;
                          if (filters.service === 'all') return vendorOk;
                          const isTTS = it.audio_path && !it.transcript;
                          const isSTT = it.transcript && !it.audio_path; // rare in our pipeline
                          const isE2E = it.audio_path && it.transcript;
                          const serviceOk = (filters.service === 'tts' && isTTS) || (filters.service === 'stt' && isSTT) || (filters.service === 'e2e' && isE2E);
                          return vendorOk && serviceOk;
                        })
                      }))
                      .filter((run) => run.items?.length > 0)
                      .slice(0, 5)
                      .map((run) => (
                      <div key={run.id} className="flex items-center justify-between p-3 bg-gray-50/50 rounded-lg">
                        <div className="flex items-center space-x-3">
                          <Badge variant="outline" className={getStatusColor(run.status)}>
                            {run.status}
                          </Badge>
                          <div>
                            <div className="font-medium text-sm">{run.mode} mode</div>
                            <div className="text-xs text-gray-500">
                              {new Date(run.started_at).toLocaleString()}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center space-x-4 text-sm">
                          <span>{run.vendors?.length || 0} vendors</span>
                          <span>{run.items?.length || 0} tests</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Quick Test Tab */}
          <TabsContent value="quick-test" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Zap className="h-5 w-5 text-blue-600" />
                  <span>Quick Test</span>
                </CardTitle>
                <CardDescription>
                  Test a single phrase across multiple vendors and modes
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="test-text">Test Text</Label>
                    <Textarea
                      id="test-text"
                      placeholder="Enter text to test..."
                      value={quickTestForm.text}
                      onChange={(e) => setQuickTestForm({...quickTestForm, text: e.target.value})}
                      rows={3}
                      className="mt-1"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Test Mode</Label>
                      <Select value={quickTestForm.mode} onValueChange={(value) => setQuickTestForm({...quickTestForm, mode: value})}>
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="isolated">Isolated Mode</SelectItem>
                          <SelectItem value="chained">Chained Mode</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {quickTestForm.mode === 'isolated' && (
                      <div>
                        <Label>Test Service (Isolated Mode)</Label>
                        <Select value={quickTestForm.service} onValueChange={(v) => setQuickTestForm({...quickTestForm, service: v})}>
                          <SelectTrigger className="mt-1">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="tts">TTS</SelectItem>
                            <SelectItem value="stt">STT</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </div>

                  {/* Vendor-level config UI - Isolated only, show relevant sections */}
                  {quickTestForm.mode === 'isolated' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {quickTestForm.vendors.includes('elevenlabs') && (
                        <div className="space-y-2">
                          {quickTestForm.service === 'tts' && (
                            <>
                              <Label>ElevenLabs TTS Model</Label>
                              <Select value={quickTestForm.models.elevenlabs.tts_model} onValueChange={(v)=>setQuickTestForm({...quickTestForm, models:{...quickTestForm.models, elevenlabs: {...quickTestForm.models.elevenlabs, tts_model: v}}})}>
                                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="eleven_flash_v2_5">eleven_flash_v2_5</SelectItem>
                                  <SelectItem value="eleven_multilingual_v2">eleven_multilingual_v2</SelectItem>
                                </SelectContent>
                              </Select>
                            </>
                          )}
                          {quickTestForm.service === 'stt' && (
                            <>
                              <Label className="mt-2">ElevenLabs STT Model</Label>
                              <Select value={quickTestForm.models.elevenlabs.stt_model} onValueChange={(v)=>setQuickTestForm({...quickTestForm, models:{...quickTestForm.models, elevenlabs: {...quickTestForm.models.elevenlabs, stt_model: v}}})}>
                                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="scribe_v1">scribe_v1</SelectItem>
                                </SelectContent>
                              </Select>
                            </>
                          )}
                        </div>
                      )}
                      {quickTestForm.vendors.includes('deepgram') && (
                        <div className="space-y-2">
                          {quickTestForm.service === 'tts' && (
                            <>
                              <Label>Deepgram TTS Model</Label>
                              <Select value={quickTestForm.models.deepgram.tts_model} onValueChange={(v)=>setQuickTestForm({...quickTestForm, models:{...quickTestForm.models, deepgram: {...quickTestForm.models.deepgram, tts_model: v}}})}>
                                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="aura-2-thalia-en">aura-2-thalia-en</SelectItem>
                                </SelectContent>
                              </Select>
                            </>
                          )}
                          {quickTestForm.service === 'stt' && (
                            <>
                              <Label className="mt-2">Deepgram STT Model</Label>
                              <Select value={quickTestForm.models.deepgram.stt_model} onValueChange={(v)=>setQuickTestForm({...quickTestForm, models:{...quickTestForm.models, deepgram: {...quickTestForm.models.deepgram, stt_model: v}}})}>
                                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="nova-3">nova-3</SelectItem>
                                </SelectContent>
                              </Select>
                            </>
                          )}
                        </div>
                      )}
                      {quickTestForm.vendors.includes('azure_openai') && (
                        <div className="space-y-2">
                          {quickTestForm.service === 'tts' && (
                            <>
                              <Label>Azure OpenAI TTS Model</Label>
                              <Select value={quickTestForm.models.azure_openai.tts_model} onValueChange={(v)=>setQuickTestForm({...quickTestForm, models:{...quickTestForm.models, azure_openai: {...quickTestForm.models.azure_openai, tts_model: v}}})}>
                                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="tts-1">tts-1</SelectItem>
                                  <SelectItem value="tts-1-hd">tts-1-hd</SelectItem>
                                </SelectContent>
                              </Select>
                              <Label className="mt-2">Voice</Label>
                              <Select value={quickTestForm.models.azure_openai.voice} onValueChange={(v)=>setQuickTestForm({...quickTestForm, models:{...quickTestForm.models, azure_openai: {...quickTestForm.models.azure_openai, voice: v}}})}>
                                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="alloy">alloy</SelectItem>
                                  <SelectItem value="echo">echo</SelectItem>
                                  <SelectItem value="fable">fable</SelectItem>
                                  <SelectItem value="onyx">onyx</SelectItem>
                                  <SelectItem value="nova">nova</SelectItem>
                                  <SelectItem value="shimmer">shimmer</SelectItem>
                                </SelectContent>
                              </Select>
                            </>
                          )}
                          {quickTestForm.service === 'stt' && (
                            <>
                              <Label className="mt-2">Azure OpenAI STT Model</Label>
                              <Select value={quickTestForm.models.azure_openai.stt_model} onValueChange={(v)=>setQuickTestForm({...quickTestForm, models:{...quickTestForm.models, azure_openai: {...quickTestForm.models.azure_openai, stt_model: v}}})}>
                                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="whisper-1">whisper-1</SelectItem>
                                </SelectContent>
                              </Select>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Chained pairing config - only show in chained mode */}
                  {quickTestForm.mode === 'chained' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <Label>Chained: TTS Vendor</Label>
                        <Select value={quickTestForm.chain.tts_vendor} onValueChange={(v)=>setQuickTestForm({...quickTestForm, chain:{...quickTestForm.chain, tts_vendor: v}})}>
                          <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="elevenlabs">ElevenLabs (TTS)</SelectItem>
                            <SelectItem value="deepgram">Deepgram (TTS)</SelectItem>
                            <SelectItem value="azure_openai">Azure OpenAI (TTS)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>Chained: STT Vendor</Label>
                        <Select value={quickTestForm.chain.stt_vendor} onValueChange={(v)=>setQuickTestForm({...quickTestForm, chain:{...quickTestForm.chain, stt_vendor: v}})}>
                          <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="deepgram">Deepgram (STT)</SelectItem>
                            <SelectItem value="elevenlabs">ElevenLabs (STT)</SelectItem>
                            <SelectItem value="azure_openai">Azure OpenAI (STT)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  )}

                  {/* Vendors selection - hide in chained mode */}
                  {quickTestForm.mode === 'isolated' && (
                    <div>
                      <Label>Vendors</Label>
                      <div className="mt-1 space-y-2">
                        {['elevenlabs', 'deepgram', 'aws', 'azure_openai'].map((vendor) => (
                          <label key={vendor} className="flex items-center space-x-2">
                            <input
                              type="checkbox"
                              checked={quickTestForm.vendors.includes(vendor)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setQuickTestForm({
                                    ...quickTestForm,
                                    vendors: [...quickTestForm.vendors, vendor]
                                  });
                                } else {
                                  setQuickTestForm({
                                    ...quickTestForm,
                                    vendors: quickTestForm.vendors.filter(v => v !== vendor)
                                  });
                                }
                              }}
                              className="rounded border-gray-300"
                            />
                            <span className="text-sm capitalize">{vendor.replace('_', ' ')}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {error && (
                  <Alert className="border-red-200 bg-red-50">
                    <AlertDescription className="text-red-700">{error}</AlertDescription>
                  </Alert>
                )}

                <Button 
                  onClick={handleQuickTest} 
                  disabled={loading || (quickTestForm.mode === 'isolated' && quickTestForm.vendors.length === 0)}
                  className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                >
                  {loading ? (
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Running Test...</span>
                    </div>
                  ) : (
                    <div className="flex items-center space-x-2">
                      <Zap className="h-4 w-4" />
                      <span>Run Test</span>
                    </div>
                  )}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Batch Test Tab */}
          <TabsContent value="batch-test" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Target className="h-5 w-5 text-green-600" />
                  <span>Batch Test</span>
                </CardTitle>
                <CardDescription>
                  Run tests using predefined script collections
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      {/* Vendor-level config UI - Isolated only */}
                      {batchTestForm.mode === 'isolated' && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {batchTestForm.vendors.includes('elevenlabs') && (
                            <div className="space-y-2">
                              {batchTestForm.service === 'tts' && (
                                <>
                                  <Label>ElevenLabs TTS Model</Label>
                                  <Select value={batchTestForm.models.elevenlabs.tts_model} onValueChange={(v)=>setBatchTestForm({...batchTestForm, models:{...batchTestForm.models, elevenlabs: {...batchTestForm.models.elevenlabs, tts_model: v}}})}>
                                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="eleven_flash_v2_5">eleven_flash_v2_5</SelectItem>
                                      <SelectItem value="eleven_multilingual_v2">eleven_multilingual_v2</SelectItem>
                                    </SelectContent>
                                  </Select>
                                </>
                              )}
                              {batchTestForm.service === 'stt' && (
                                <>
                                  <Label className="mt-2">ElevenLabs STT Model</Label>
                                  <Select value={batchTestForm.models.elevenlabs.stt_model} onValueChange={(v)=>setBatchTestForm({...batchTestForm, models:{...batchTestForm.models, elevenlabs: {...batchTestForm.models.elevenlabs, stt_model: v}}})}>
                                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="scribe_v1">scribe_v1</SelectItem>
                                    </SelectContent>
                                  </Select>
                                </>
                              )}
                            </div>
                          )}
                          {batchTestForm.vendors.includes('deepgram') && (
                            <div className="space-y-2">
                              {batchTestForm.service === 'tts' && (
                                <>
                                  <Label>Deepgram TTS Model</Label>
                                  <Select value={batchTestForm.models.deepgram.tts_model} onValueChange={(v)=>setBatchTestForm({...batchTestForm, models:{...batchTestForm.models, deepgram: {...batchTestForm.models.deepgram, tts_model: v}}})}>
                                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="aura-2-thalia-en">aura-2-thalia-en</SelectItem>
                                    </SelectContent>
                                  </Select>
                                </>
                              )}
                              {batchTestForm.service === 'stt' && (
                                <>
                                  <Label className="mt-2">Deepgram STT Model</Label>
                                  <Select value={batchTestForm.models.deepgram.stt_model} onValueChange={(v)=>setBatchTestForm({...batchTestForm, models:{...batchTestForm.models, deepgram: {...batchTestForm.models.deepgram, stt_model: v}}})}>
                                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="nova-3">nova-3</SelectItem>
                                    </SelectContent>
                                  </Select>
                                </>
                              )}
                            </div>
                          )}
                          {batchTestForm.vendors.includes('azure_openai') && (
                            <div className="space-y-2">
                              {batchTestForm.service === 'tts' && (
                                <>
                                  <Label>Azure OpenAI TTS Model</Label>
                                  <Select value={batchTestForm.models.azure_openai.tts_model} onValueChange={(v)=>setBatchTestForm({...batchTestForm, models:{...batchTestForm.models, azure_openai: {...batchTestForm.models.azure_openai, tts_model: v}}})}>
                                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="tts-1">tts-1</SelectItem>
                                      <SelectItem value="tts-1-hd">tts-1-hd</SelectItem>
                                    </SelectContent>
                                  </Select>
                                  <Label className="mt-2">Voice</Label>
                                  <Select value={batchTestForm.models.azure_openai.voice} onValueChange={(v)=>setBatchTestForm({...batchTestForm, models:{...batchTestForm.models, azure_openai: {...batchTestForm.models.azure_openai, voice: v}}})}>
                                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="alloy">alloy</SelectItem>
                                      <SelectItem value="echo">echo</SelectItem>
                                      <SelectItem value="fable">fable</SelectItem>
                                      <SelectItem value="onyx">onyx</SelectItem>
                                      <SelectItem value="nova">nova</SelectItem>
                                      <SelectItem value="shimmer">shimmer</SelectItem>
                                    </SelectContent>
                                  </Select>
                                </>
                              )}
                              {batchTestForm.service === 'stt' && (
                                <>
                                  <Label className="mt-2">Azure OpenAI STT Model</Label>
                                  <Select value={batchTestForm.models.azure_openai.stt_model} onValueChange={(v)=>setBatchTestForm({...batchTestForm, models:{...batchTestForm.models, azure_openai: {...batchTestForm.models.azure_openai, stt_model: v}}})}>
                                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="whisper-1">whisper-1</SelectItem>
                                    </SelectContent>
                                  </Select>
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      <Label>Test Mode</Label>
                      <Select value={batchTestForm.mode} onValueChange={(value) => setBatchTestForm({...batchTestForm, mode: value})}>
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="isolated">Isolated Mode</SelectItem>
                          <SelectItem value="chained">Chained Mode</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {batchTestForm.mode === 'isolated' && (
                      <div>
                        <Label>Test Service (Isolated Mode)</Label>
                        <Select value={batchTestForm.service} onValueChange={(v) => setBatchTestForm({...batchTestForm, service: v})}>
                          <SelectTrigger className="mt-1">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="tts">TTS</SelectItem>
                            <SelectItem value="stt">STT</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </div>

                  {/* Chained pairing config - only in chained mode */}
                  {batchTestForm.mode === 'chained' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <Label>Chained: TTS Vendor</Label>
                        <Select value={batchTestForm.chain.tts_vendor} onValueChange={(v)=>setBatchTestForm({...batchTestForm, chain:{...batchTestForm.chain, tts_vendor: v}})}>
                          <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="elevenlabs">ElevenLabs (TTS)</SelectItem>
                            <SelectItem value="deepgram">Deepgram (TTS)</SelectItem>
                            <SelectItem value="azure_openai">Azure OpenAI (TTS)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>Chained: STT Vendor</Label>
                        <Select value={batchTestForm.chain.stt_vendor} onValueChange={(v)=>setBatchTestForm({...batchTestForm, chain:{...batchTestForm.chain, stt_vendor: v}})}>
                          <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="deepgram">Deepgram (STT)</SelectItem>
                            <SelectItem value="elevenlabs">ElevenLabs (STT)</SelectItem>
                            <SelectItem value="azure_openai">Azure OpenAI (STT)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  )}

                  {/* Vendors - hide in chained mode */}
                  {batchTestForm.mode === 'isolated' && (
                    <div>
                      <Label>Vendors</Label>
                      <div className="mt-1 space-y-2">
                        {['elevenlabs', 'deepgram', 'aws', 'azure_openai'].map((vendor) => (
                          <label key={vendor} className="flex items-center space-x-2">
                            <input
                              type="checkbox"
                              checked={batchTestForm.vendors.includes(vendor)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setBatchTestForm({
                                    ...batchTestForm,
                                    vendors: [...batchTestForm.vendors, vendor]
                                  });
                                } else {
                                  setBatchTestForm({
                                    ...batchTestForm,
                                    vendors: batchTestForm.vendors.filter(v => v !== vendor)
                                  });
                                }
                              }}
                              className="rounded border-gray-300"
                            />
                            <span className="text-sm capitalize">{vendor.replace('_', ' ')}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  <div>
                    <Label>Test Scripts</Label>
                    <div className="mt-2 space-y-3">
                      {scripts.map((script) => (
                        <div key={script.id} className="border rounded-lg p-3">
                          <label className="flex items-start space-x-3">
                            <input
                              type="checkbox"
                              checked={batchTestForm.scriptIds.includes(script.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setBatchTestForm({
                                    ...batchTestForm,
                                    scriptIds: [...batchTestForm.scriptIds, script.id]
                                  });
                                } else {
                                  setBatchTestForm({
                                    ...batchTestForm,
                                    scriptIds: batchTestForm.scriptIds.filter(id => id !== script.id)
                                  });
                                }
                              }}
                              className="mt-1 rounded border-gray-300"
                            />
                            <div className="flex-1">
                              <div className="font-medium">{script.name}</div>
                              <div className="text-sm text-gray-500 mt-1">{script.description}</div>
                              <div className="flex items-center space-x-2 mt-2">
                                <Badge variant="secondary" className="text-xs">
                                  {script.item_count} items
                                </Badge>
                                {script.tags && (
                                  <Badge variant="outline" className="text-xs">
                                    {script.tags}
                                  </Badge>
                                )}
                              </div>
                            </div>
                          </label>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Paste Batch Script (optional)</Label>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-start">
                      <div className="md:col-span-3">
                        <Textarea
                          placeholder={
                            batchTestForm.batchScriptFormat === 'jsonl'
                              ? '{"text":"Hello there"}\n{"text":"How can I help?"}'
                              : batchTestForm.batchScriptFormat === 'csv'
                              ? 'text\nHello there\nHow can I help?\n'
                              : 'Hello there\nHow can I help?\n'
                          }
                          rows={4}
                          value={batchTestForm.batchScriptInput}
                          onChange={(e) => setBatchTestForm({ ...batchTestForm, batchScriptInput: e.target.value })}
                          className="mt-1"
                        />
                        <div className="text-xs text-gray-500 mt-1">
                          Supports JSONL, CSV, or TXT. Recognized keys for JSONL/CSV: <code>text</code>, <code>prompt</code>, or <code>sentence</code>.
                        </div>
                      </div>
                      <div>
                        <Label>Format</Label>
                        <Select value={batchTestForm.batchScriptFormat} onValueChange={(v) => setBatchTestForm({ ...batchTestForm, batchScriptFormat: v })}>
                          <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="txt">TXT (one line per item)</SelectItem>
                            <SelectItem value="jsonl">JSONL</SelectItem>
                            <SelectItem value="csv">CSV</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>

                  {error && (
                    <Alert className="border-red-200 bg-red-50">
                      <AlertDescription className="text-red-700">{error}</AlertDescription>
                    </Alert>
                  )}

                  <Button 
                    onClick={handleBatchTest} 
                    disabled={
                      loading ||
                      (
                        batchTestForm.scriptIds.length === 0 &&
                        !(batchTestForm.batchScriptInput && batchTestForm.batchScriptInput.trim())
                      ) ||
                      (batchTestForm.mode === 'isolated' && batchTestForm.vendors.length === 0)
                    }
                    className="w-full bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700"
                  >
                    {loading ? (
                      <div className="flex items-center space-x-2">
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        <span>Running Batch Test...</span>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2">
                        <Target className="h-4 w-4" />
                        <span>Run Batch Test</span>
                      </div>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Results Tab */}
          <TabsContent value="results" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Activity className="h-5 w-5 text-purple-600" />
                    <span>Test Results</span>
                  </div>
                  <Button variant="outline" size="sm" onClick={fetchRuns}>
                    <Activity className="h-3 w-3 mr-1" />
                    Refresh
                  </Button>
                </CardTitle>
                <CardDescription>
                  Detailed results from all test runs
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm text-gray-600">Latest test runs and their performance</div>
                  <ExportToolbar runs={runs} />
                </div>
                {runs.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <Activity className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                    <h3 className="text-lg font-medium mb-2">No results yet</h3>
                    <p>Run your first test to see results here</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {runs.map((run) => (
                      <RunResultCard key={run.id} run={run} />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default App;