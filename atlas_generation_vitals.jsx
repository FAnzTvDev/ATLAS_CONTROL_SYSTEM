/**
 * ATLAS GENERATION VITALS MONITOR
 * ================================
 * Real-time UI for monitoring AI film scene generation
 * Shows per-shot status, wave execution, doctrine gates, and health indicators
 *
 * Features:
 * - Live scene & shot status with thumbnail hydration
 * - Wave execution visualization (parallel + sequential)
 * - Pipeline phase tracking (Intent → Film Engine → FAL → Scoring)
 * - EKG-style generation throughput graph
 * - Color-coded health: green=pass, yellow=warning, red=fail
 * - Expandable shot detail panels
 *
 * Usage:
 *   <GenerationVitalsMonitor project="my_project" sceneId="001" />
 *
 * API Contract:
 *   GET /api/v26/render-status/{project}/{scene_id} → {
 *     scene_id, total_shots, shots_completed, current_phase,
 *     active_shots: [{shot_id, status, phase, duration_ms, thumbnail, ...}],
 *     waves: [{wave_id, status, shots: [...]}],
 *     doctrine_results: [{phase, status, reason}],
 *     throughput_history: [{timestamp, shots_completed}]
 *   }
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  AlertCircle,
  CheckCircle,
  Clock,
  Zap,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Loader,
  AlertTriangle,
  Film,
  Eye,
  Cpu,
  BarChart3,
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

/**
 * Main component: GenerationVitalsMonitor
 * Polls render-status endpoint and displays real-time generation metrics
 */
const GenerationVitalsMonitor = ({ project, sceneId, pollIntervalMs = 1000 }) => {
  const [vitals, setVitals] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedShots, setExpandedShots] = useState(new Set());
  const pollIntervalRef = useRef(null);

  // Fetch render status
  const fetchVitals = async () => {
    try {
      const response = await fetch(
        `/api/v26/render-status/${encodeURIComponent(project)}/${encodeURIComponent(sceneId)}`
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setVitals(data);
      setError(null);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      // Don't disable polling on error — keep trying
    }
  };

  // Set up polling
  useEffect(() => {
    fetchVitals(); // Initial fetch
    pollIntervalRef.current = setInterval(fetchVitals, pollIntervalMs);
    return () => clearInterval(pollIntervalRef.current);
  }, [project, sceneId, pollIntervalMs]);

  if (loading && !vitals) {
    return (
      <div className="w-full h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="text-center">
          <Loader className="w-12 h-12 animate-spin mx-auto mb-4 text-cyan-400" />
          <p>Initializing ATLAS Vitals...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full min-h-screen bg-slate-950 text-white overflow-auto">
      {/* Header */}
      <VitalsHeader vitals={vitals} error={error} />

      {/* Main content grid */}
      <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Scene overview + waves */}
        <div className="lg:col-span-2 space-y-6">
          {/* Scene progress card */}
          <SceneProgressCard vitals={vitals} />

          {/* Wave execution visualization */}
          {vitals?.waves && <WaveVisualization waves={vitals.waves} />}

          {/* Pipeline phase tracker */}
          {vitals?.doctrine_results && (
            <PipelinePhaseTracker phases={vitals.doctrine_results} />
          )}

          {/* Throughput EKG */}
          {vitals?.throughput_history && (
            <ThroughputEKG history={vitals.throughput_history} />
          )}
        </div>

        {/* Right column: Health indicators + shot grid */}
        <div className="space-y-6">
          {/* Vital signs (health indicators) */}
          <VitalSigns vitals={vitals} />

          {/* Recent shots status */}
          {vitals?.active_shots && (
            <RecentShotsStatus
              shots={vitals.active_shots}
              expandedShots={expandedShots}
              setExpandedShots={setExpandedShots}
            />
          )}
        </div>
      </div>

      {/* Shot detail grid */}
      {vitals?.active_shots && (
        <div className="p-6 border-t border-slate-800">
          <h2 className="text-lg font-bold text-cyan-400 mb-4 flex items-center gap-2">
            <Film className="w-5 h-5" /> All Shots
          </h2>
          <ShotGrid shots={vitals.active_shots} expandedShots={expandedShots} />
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="fixed bottom-4 right-4 bg-red-900 border border-red-400 text-white px-4 py-3 rounded flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};

/**
 * Header with title and overall status
 */
const VitalsHeader = ({ vitals, error }) => {
  const isHealthy = vitals && !error && vitals.current_phase !== 'failed';
  const statusColor = isHealthy ? 'text-green-400' : 'text-red-400';

  return (
    <div className="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
      <div className="p-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className={`w-4 h-4 rounded-full ${isHealthy ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
          <div>
            <h1 className="text-3xl font-bold text-white">ATLAS GENERATION VITALS</h1>
            <p className={`text-sm ${statusColor}`}>
              {vitals?.scene_id ? `Scene ${vitals.scene_id}` : 'Initializing...'}
              {vitals?.current_phase && ` • Phase: ${vitals.current_phase}`}
            </p>
          </div>
        </div>

        {vitals && (
          <div className="text-right">
            <div className="text-2xl font-bold text-cyan-400">
              {vitals.shots_completed}/{vitals.total_shots}
            </div>
            <p className="text-sm text-slate-400">Shots completed</p>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Scene progress card with progress bar and ETA
 */
const SceneProgressCard = ({ vitals }) => {
  if (!vitals) return null;

  const progress = (vitals.shots_completed / vitals.total_shots) * 100;
  const avgTimePerShot = vitals.total_duration_ms ? vitals.total_duration_ms / vitals.shots_completed : 0;
  const remainingShots = vitals.total_shots - vitals.shots_completed;
  const estimatedRemainingMs = remainingShots * avgTimePerShot;
  const etaMinutes = Math.ceil(estimatedRemainingMs / 1000 / 60);

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-bold text-cyan-400 mb-4 flex items-center gap-2">
        <Activity className="w-5 h-5" /> Scene Progress
      </h2>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex justify-between text-sm mb-2">
          <span>Overall Progress</span>
          <span className="text-cyan-400 font-mono">{progress.toFixed(1)}%</span>
        </div>
        <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-slate-400">Avg time/shot</p>
          <p className="text-cyan-400 font-mono font-bold">{(avgTimePerShot / 1000).toFixed(1)}s</p>
        </div>
        <div>
          <p className="text-slate-400">Est. remaining</p>
          <p className="text-cyan-400 font-mono font-bold">{etaMinutes}m</p>
        </div>
        <div>
          <p className="text-slate-400">Total time</p>
          <p className="text-cyan-400 font-mono font-bold">{(vitals.total_duration_ms / 1000 / 60).toFixed(1)}m</p>
        </div>
        <div>
          <p className="text-slate-400">Status</p>
          <p className="text-green-400 font-bold capitalize">{vitals.current_phase}</p>
        </div>
      </div>
    </div>
  );
};

/**
 * Wave execution visualization
 * Shows parallel (Wave 0) vs sequential (Wave 1+) execution
 */
const WaveVisualization = ({ waves }) => {
  if (!waves || waves.length === 0) return null;

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-bold text-cyan-400 mb-4 flex items-center gap-2">
        <Zap className="w-5 h-5" /> Wave Execution
      </h2>

      <div className="space-y-3">
        {waves.map((wave, idx) => (
          <div key={wave.wave_id || idx}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-mono text-slate-300">
                Wave {idx} {idx === 0 ? '(Parallel Anchors)' : '(Sequential Chain)'}
              </span>
              <span className={`text-xs px-2 py-1 rounded font-bold ${getWaveStatusColor(wave.status)}`}>
                {wave.status.toUpperCase()}
              </span>
            </div>

            {/* Shot boxes in wave */}
            <div className="flex flex-wrap gap-1">
              {(wave.shots || []).map((shot, shotIdx) => (
                <div
                  key={shot.shot_id || shotIdx}
                  className={`px-2 py-1 text-xs rounded font-mono ${getShotStatusBgColor(
                    shot.status
                  )} ${getShotStatusTextColor(shot.status)} border ${getShotStatusBorderColor(
                    shot.status
                  )}`}
                >
                  {shot.shot_id}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/**
 * Pipeline phase tracker (doctrine gates)
 */
const PipelinePhaseTracker = ({ phases }) => {
  if (!phases || phases.length === 0) return null;

  // Define phase sequence
  const phaseSequence = [
    { id: 'intent_verify', name: 'Intent Verify', icon: Eye },
    { id: 'film_engine', name: 'Film Engine', icon: Cpu },
    { id: 'shot_authority', name: 'Shot Authority', icon: BarChart3 },
    { id: 'fal_generation', name: 'FAL Generation', icon: Zap },
    { id: 'post_gen_score', name: 'Post-Gen Score', icon: CheckCircle },
  ];

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-bold text-cyan-400 mb-4 flex items-center gap-2">
        <Film className="w-5 h-5" /> Pipeline Phases
      </h2>

      <div className="space-y-2">
        {phaseSequence.map((phase, idx) => {
          const result = phases.find((p) => p.phase === phase.id);
          const isActive = result && result.status === 'in_progress';
          const isPassed = result && result.status === 'passed';
          const isFailed = result && result.status === 'failed';
          const Icon = phase.icon;

          return (
            <div key={phase.id} className="flex items-center gap-3">
              {/* Phase indicator */}
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  isPassed
                    ? 'bg-green-900/30 border border-green-400'
                    : isFailed
                    ? 'bg-red-900/30 border border-red-400'
                    : isActive
                    ? 'bg-cyan-900/30 border border-cyan-400 animate-pulse'
                    : 'bg-slate-800 border border-slate-600'
                }`}
              >
                <Icon className="w-4 h-4" />
              </div>

              {/* Phase name + status */}
              <div className="flex-1">
                <p className="text-sm font-bold text-white">{phase.name}</p>
                {result?.reason && (
                  <p className="text-xs text-slate-400 truncate">{result.reason}</p>
                )}
              </div>

              {/* Status badge */}
              <div className="flex-shrink-0">
                {isPassed && <CheckCircle className="w-4 h-4 text-green-400" />}
                {isFailed && <AlertTriangle className="w-4 h-4 text-red-400" />}
                {isActive && <Loader className="w-4 h-4 text-cyan-400 animate-spin" />}
                {!result && <Clock className="w-4 h-4 text-slate-500" />}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

/**
 * Throughput EKG: shots completed over time
 */
const ThroughputEKG = ({ history }) => {
  if (!history || history.length < 2) return null;

  // Transform history for recharts
  const data = history.map((entry) => ({
    time: new Date(entry.timestamp).toLocaleTimeString(),
    shots: entry.shots_completed,
  }));

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-bold text-cyan-400 mb-4 flex items-center gap-2">
        <TrendingUp className="w-5 h-5" /> Generation Throughput
      </h2>

      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <XAxis
            dataKey="time"
            stroke="#94a3b8"
            style={{ fontSize: '12px' }}
            tick={{ fill: '#94a3b8' }}
          />
          <YAxis stroke="#94a3b8" style={{ fontSize: '12px' }} tick={{ fill: '#94a3b8' }} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #475569',
              borderRadius: '8px',
            }}
            labelStyle={{ color: '#22d3ee' }}
          />
          <Line
            type="monotone"
            dataKey="shots"
            stroke="#06b6d4"
            dot={{ fill: '#06b6d4', r: 3 }}
            isAnimationActive={true}
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

/**
 * Vital signs card (health indicators)
 */
const VitalSigns = ({ vitals }) => {
  if (!vitals) return null;

  const getHealthLevel = () => {
    if (vitals.shots_completed === vitals.total_shots) return 'excellent';
    if (vitals.failed_shots === 0) return 'good';
    if (vitals.failed_shots / vitals.total_shots < 0.1) return 'warning';
    return 'critical';
  };

  const health = getHealthLevel();
  const healthColor = {
    excellent: 'bg-green-900/30 border-green-400 text-green-400',
    good: 'bg-cyan-900/30 border-cyan-400 text-cyan-400',
    warning: 'bg-yellow-900/30 border-yellow-400 text-yellow-400',
    critical: 'bg-red-900/30 border-red-400 text-red-400',
  }[health];

  return (
    <div className={`border rounded-lg p-6 ${healthColor}`}>
      <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
        <Activity className="w-5 h-5" /> Vital Signs
      </h2>

      <div className="space-y-3 text-sm">
        <div className="flex justify-between">
          <span>Health Status</span>
          <span className="font-bold capitalize">{health}</span>
        </div>

        <div className="flex justify-between">
          <span>Pass Rate</span>
          <span className="font-bold">
            {(((vitals.total_shots - vitals.failed_shots) / vitals.total_shots) * 100).toFixed(1)}%
          </span>
        </div>

        <div className="flex justify-between">
          <span>Failed Shots</span>
          <span className="font-bold">{vitals.failed_shots || 0}</span>
        </div>

        <div className="flex justify-between">
          <span>Warnings</span>
          <span className="font-bold">{vitals.warning_shots || 0}</span>
        </div>

        <div className="flex justify-between">
          <span>Memory (MB)</span>
          <span className="font-mono">{vitals.memory_mb?.toFixed(0) || 'N/A'}</span>
        </div>
      </div>
    </div>
  );
};

/**
 * Recent shots status (small cards)
 */
const RecentShotsStatus = ({ shots, expandedShots, setExpandedShots }) => {
  const recentShots = shots.slice(0, 5);

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-bold text-cyan-400 mb-4">Recent Shots</h2>
      <div className="space-y-2">
        {recentShots.map((shot) => (
          <div key={shot.shot_id} className="flex items-center gap-3">
            <div
              className={`w-3 h-3 rounded-full ${getShotStatusDotColor(shot.status)}`}
            />
            <span className="text-sm font-mono flex-1">{shot.shot_id}</span>
            <span className="text-xs text-slate-400">
              {shot.duration_ms ? `${(shot.duration_ms / 1000).toFixed(1)}s` : 'pending'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

/**
 * Shot grid: all shots with expandable detail
 */
const ShotGrid = ({ shots, expandedShots }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {shots.map((shot) => (
        <ShotCard key={shot.shot_id} shot={shot} isExpanded={expandedShots.has(shot.shot_id)} />
      ))}
    </div>
  );
};

/**
 * Individual shot card with thumbnail and details
 */
const ShotCard = ({ shot, isExpanded }) => {
  const statusColor = getShotStatusBgColor(shot.status);
  const statusText = getShotStatusTextColor(shot.status);
  const hasThumbnail = shot.thumbnail_url;

  return (
    <div
      className={`rounded-lg overflow-hidden border transition-all ${
        isExpanded ? 'col-span-2 row-span-2' : ''
      } ${statusColor}`}
    >
      {/* Thumbnail or placeholder */}
      {hasThumbnail ? (
        <img
          src={shot.thumbnail_url}
          alt={shot.shot_id}
          className="w-full h-40 object-cover"
        />
      ) : (
        <div className="w-full h-40 bg-slate-700 flex items-center justify-center">
          {shot.status === 'completed' || shot.status === 'done' ? (
            <CheckCircle className="w-8 h-8 text-green-400" />
          ) : shot.status === 'running' || shot.status === 'pending' ? (
            <Loader className="w-8 h-8 text-cyan-400 animate-spin" />
          ) : shot.status === 'failed' ? (
            <AlertCircle className="w-8 h-8 text-red-400" />
          ) : (
            <Film className="w-8 h-8 text-slate-500" />
          )}
        </div>
      )}

      {/* Card body */}
      <div className="p-4 bg-slate-900/50">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-mono font-bold">{shot.shot_id}</span>
          <span className={`text-xs px-2 py-1 rounded font-bold ${statusText} ${statusColor}`}>
            {shot.status}
          </span>
        </div>

        {shot.duration_ms && (
          <p className="text-xs text-slate-400 mb-2">
            {(shot.duration_ms / 1000).toFixed(2)}s
          </p>
        )}

        {shot.phase && (
          <p className="text-xs text-slate-400 mb-2">Phase: {shot.phase}</p>
        )}

        {/* Expandable details */}
        {isExpanded && shot.details && (
          <div className="mt-3 pt-3 border-t border-slate-700 text-xs space-y-1 text-slate-300">
            {shot.details.prompt && (
              <div>
                <p className="font-bold text-cyan-400">Prompt:</p>
                <p className="text-slate-400 line-clamp-3">{shot.details.prompt}</p>
              </div>
            )}
            {shot.details.doctrine_result && (
              <div>
                <p className="font-bold text-cyan-400">Doctrine:</p>
                <p className="text-slate-400">{shot.details.doctrine_result}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Utility functions for color coding
 */
const getShotStatusBgColor = (status) => {
  switch (status) {
    case 'completed':
    case 'done':
    case 'success':
      return 'bg-green-900/20 border-green-400';
    case 'running':
    case 'pending':
    case 'queued':
      return 'bg-cyan-900/20 border-cyan-400';
    case 'warning':
      return 'bg-yellow-900/20 border-yellow-400';
    case 'failed':
    case 'error':
      return 'bg-red-900/20 border-red-400';
    default:
      return 'bg-slate-800/50 border-slate-600';
  }
};

const getShotStatusTextColor = (status) => {
  switch (status) {
    case 'completed':
    case 'done':
    case 'success':
      return 'text-green-400';
    case 'running':
    case 'pending':
    case 'queued':
      return 'text-cyan-400';
    case 'warning':
      return 'text-yellow-400';
    case 'failed':
    case 'error':
      return 'text-red-400';
    default:
      return 'text-slate-400';
  }
};

const getShotStatusBorderColor = (status) => {
  switch (status) {
    case 'completed':
    case 'done':
    case 'success':
      return 'border-green-400';
    case 'running':
    case 'pending':
    case 'queued':
      return 'border-cyan-400';
    case 'warning':
      return 'border-yellow-400';
    case 'failed':
    case 'error':
      return 'border-red-400';
    default:
      return 'border-slate-600';
  }
};

const getShotStatusDotColor = (status) => {
  switch (status) {
    case 'completed':
    case 'done':
    case 'success':
      return 'bg-green-400';
    case 'running':
    case 'pending':
    case 'queued':
      return 'bg-cyan-400 animate-pulse';
    case 'warning':
      return 'bg-yellow-400';
    case 'failed':
    case 'error':
      return 'bg-red-400';
    default:
      return 'bg-slate-500';
  }
};

const getWaveStatusColor = (status) => {
  switch (status) {
    case 'completed':
      return 'bg-green-900/30 border-green-400 text-green-400';
    case 'in_progress':
      return 'bg-cyan-900/30 border-cyan-400 text-cyan-400';
    case 'warning':
      return 'bg-yellow-900/30 border-yellow-400 text-yellow-400';
    case 'failed':
      return 'bg-red-900/30 border-red-400 text-red-400';
    default:
      return 'bg-slate-800 border-slate-600 text-slate-400';
  }
};

export default GenerationVitalsMonitor;
