import React, { useState, useEffect } from 'react';
import {
  Clock,
  ShieldCheck,
  AlertTriangle,
  Network,
  CheckCircle,
  ShieldAlert,
  Cpu,
  FileCheck,
  RefreshCw,
  Target,
} from 'lucide-react';
import { apiJson } from '../lib/api';

interface RecoveryLayerProps {
  activeCase: string | null;
}

const RecoveryLayer: React.FC<RecoveryLayerProps> = ({ activeCase }) => {
  const [ranking, setRanking] = useState<any[]>([]);
  const [clock, setClock] = useState<any[]>([]);
  const [typology, setTypology] = useState<any>(null);
  const [related, setRelated] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRecoveryData = async () => {
    if (!activeCase) return;
    setLoading(true);
    setError(null);
    try {
      const [rRank, rClock, rRel, rSum] = await Promise.all([
        apiJson(`/api/v1/cases/${activeCase}/ranking`).catch(() => ({ destinations_ranked: [] })),
        apiJson(`/api/v1/cases/${activeCase}/clock`).catch(() => ({ timeline_steps: [] })),
        apiJson(`/api/v1/cases/${activeCase}/related`).catch(() => null),
        apiJson(`/api/v1/cases/${activeCase}/summary`).catch(() => null),
      ]);

      setRanking(rRank.destinations_ranked || []);
      setClock(rClock.timeline_steps || []);
      setRelated(rRel);
      setSummary(rSum);

      const c = await apiJson(`/api/investigations/${activeCase}`).catch(() => null);
      if (c?.analysis?.recovery_path) {
        setTypology(c.analysis.recovery_path);
      } else if (c?.recovery_path) {
        setTypology(c.recovery_path);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecoveryData();
  }, [activeCase]);

  const toggleStep = async (stepId: string, currentStatus: string) => {
    if (!activeCase) return;
    const nextStatus = currentStatus === 'done' ? 'pending' : 'done';
    try {
      await apiJson(`/api/v1/cases/${activeCase}/clock/${stepId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      });
      loadRecoveryData();
    } catch (e) {
      console.error(e);
    }
  };

  if (!activeCase) {
    return (
      <div className="p-12 text-center text-[var(--text-muted)] bg-[var(--bg-card)] rounded-2xl border border-[var(--border-color)] max-w-xl mx-auto my-12">
        <Clock className="h-10 w-10 text-[#79E282] mx-auto mb-3" />
        <h3 className="text-base font-bold text-[var(--text-primary)]">No Active Case Selected</h3>
        <p className="text-xs mt-1">Please select an investigation from the header console to track the Recovery Layer.</p>
      </div>
    );
  }

  const overdueCount = clock.filter((s) => s.status === 'overdue').length;
  const completedSteps = clock.filter((s) => s.status === 'done').length;
  const totalSteps = clock.length || 1;
  const progressPercent = Math.round((completedSteps / totalSteps) * 100);

  // Top destination for the highlighted "Last Observed Destination" card
  const primaryDestination = ranking[0] || null;

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Official Safe-Handling Advisory Banner */}
      <div className="p-4 bg-[#E6A94A]/10 border border-[#E6A94A]/30 rounded-2xl flex items-start space-x-3 text-[#E6A94A] shadow-sm">
        <ShieldAlert className="h-5 w-5 text-[#E6A94A] flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-bold text-xs tracking-wider uppercase">Official Safe-Handling Advisory</h4>
          <p className="text-[11px] mt-0.5 text-[#E6A94A]/90 leading-relaxed">
            Law enforcement officials, regulatory bodies, and genuine recovery processes never ask victims for private keys,
            seed phrases, OTPs, or upfront recovery fees. Anyone requesting credentials or fees claiming to be a "recovery agent" is committing fraud.
          </p>
        </div>
      </div>

      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center p-6 bg-[var(--bg-card)] rounded-2xl border border-[var(--border-color)] shadow-xl gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-[#79E282]/10 rounded-lg text-[#79E282]">
              <Clock className="h-5 w-5" />
            </div>
            <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
              Golden Hour Recovery Layer
            </h2>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Time-critical SLA freeze notices, recoverability ranking, standardized typology checklists, and cross-case network coordination.
          </p>
        </div>
        <button
          onClick={loadRecoveryData}
          disabled={loading}
          className="inline-flex items-center px-4 py-2 bg-[var(--bg-surface)] text-[#79E282] hover:text-[#0B0B0D] hover:bg-[#79E282] border border-[var(--border-color)] hover:border-[#79E282] font-bold rounded-xl transition-colors text-xs shadow-sm"
        >
          <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Refreshing...' : 'Refresh Timeline'}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-[#D95F63]/10 text-[#D95F63] border border-[#D95F63]/30 rounded-xl text-xs">{error}</div>
      )}

      {overdueCount > 0 && (
        <div className="p-4 bg-[#D95F63]/15 border border-[#D95F63]/40 rounded-2xl flex items-center space-x-3 text-[#D95F63]">
          <AlertTriangle className="h-5 w-5 text-[#D95F63] flex-shrink-0 animate-pulse" />
          <div className="text-xs">
            <strong className="uppercase tracking-wider">Urgent Action Alert:</strong> {overdueCount} critical recovery milestone(s) have passed their due window! Immediate VASP outreach is recommended before asset flight.
          </div>
        </div>
      )}

      {/* Top Highlight: Last Observed Destination Card (if ranking exists) */}
      {primaryDestination && (
        <div className="bg-[var(--bg-card)] p-6 rounded-2xl border border-[var(--border-color)] shadow-xl relative overflow-hidden">
          <div className="flex items-center justify-between mb-3 pb-3 border-b border-[var(--border-color)]">
            <div className="flex items-center space-x-2">
              <Target className="h-4 w-4 text-[#79E282]" />
              <h3 className="font-bold text-sm text-[var(--text-primary)]">Primary Actionable Endpoint</h3>
            </div>
            <span
              className={`text-xs px-2.5 py-0.5 rounded-full font-bold border ${
                primaryDestination.tier === 'Act now'
                  ? 'bg-[#D95F63]/15 text-[#D95F63] border-[#D95F63]/40'
                  : primaryDestination.tier === 'Act soon'
                  ? 'bg-[#E6A94A]/15 text-[#E6A94A] border-[#E6A94A]/40'
                  : 'bg-[#368980]/15 text-[#79E282] border-[#368980]/40'
              }`}
            >
              {primaryDestination.tier}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="p-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-color)]">
              <span className="text-[10px] uppercase font-bold text-[var(--text-muted)] block">Target Entity</span>
              <span className="text-sm font-bold text-[var(--text-primary)]">{primaryDestination.entity_name}</span>
              <span className="text-[11px] font-mono text-[var(--text-muted)] block truncate mt-0.5">
                {primaryDestination.destination_address}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-color)]">
              <span className="text-[10px] uppercase font-bold text-[var(--text-muted)] block">Traced Balance</span>
              <span className="text-sm font-bold text-[#79E282] font-mono">
                {primaryDestination.traced_amount} {primaryDestination.asset}
              </span>
              <span className="text-[11px] text-[var(--text-muted)] block mt-0.5">
                Received ~{primaryDestination.time_since_receipt_hours}h ago
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-color)] flex flex-col justify-between">
              <div className="flex justify-between items-center text-[10px] uppercase font-bold text-[var(--text-muted)]">
                <span>Attribution Confidence</span>
                <span className="text-[#79E282] font-mono">
                  {Math.round(primaryDestination.attribution_confidence * 100)}%
                </span>
              </div>
              <div className="w-full bg-[#1C272A] rounded-full h-2 my-1 overflow-hidden">
                <div
                  className="bg-[#79E282] h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.round(primaryDestination.attribution_confidence * 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-[var(--text-muted)]">Verified exchange/VASP deposit cluster</span>
            </div>
          </div>

          <div className="p-3 bg-[#79E282]/5 border border-[#79E282]/20 rounded-xl text-xs text-[var(--text-primary)] flex items-center justify-between">
            <span>
              <strong>Action Directive:</strong> {primaryDestination.recommended_action}
            </span>
            <span className="text-[10px] text-[#79E282] font-mono uppercase font-bold">Priority One</span>
          </div>
        </div>
      )}

      {/* Typology & Evidence Checklist */}
      {typology && (
        <div className="bg-[var(--bg-card)] p-6 rounded-2xl border border-[var(--border-color)] shadow-xl">
          <div className="flex items-center justify-between mb-3 pb-3 border-b border-[var(--border-color)]">
            <h3 className="font-bold text-sm text-[var(--text-primary)] flex items-center">
              <FileCheck className="mr-2 h-4 w-4 text-[#79E282]" />
              Recovery Path Engine: {typology.name || typology.typology}
            </h3>
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-[#368980]/20 text-[#79E282] border border-[#368980]/40">
              {typology.recommended_request_type}
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mb-4 leading-relaxed">{typology.description}</p>
          <div className="bg-[var(--bg-surface)] p-4 rounded-xl border border-[var(--border-color)]">
            <h5 className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2.5">
              Standardized Evidence Package Checklist:
            </h5>
            <ul className="text-xs text-[var(--text-primary)] space-y-1.5">
              {typology.evidence_checklist?.map((item: string, i: number) => (
                <li key={i} className="flex items-center">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#79E282] mr-2" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="text-[11px] text-[var(--text-muted)] mt-3">
            Primary Recipient Authority: <strong className="text-[var(--text-primary)]">{typology.responsible_party}</strong>
          </div>
        </div>
      )}

      {/* Grid: Recovery Clock + Recoverability Ranking */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recovery Clock Timeline with SVG Progress Ring */}
        <div className="bg-[var(--bg-card)] p-6 rounded-2xl border border-[var(--border-color)] shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-[var(--border-color)]">
              <div className="flex items-center space-x-2">
                <Clock className="h-4 w-4 text-[#79E282]" />
                <h3 className="font-bold text-sm text-[var(--text-primary)]">Recovery Clock Milestones</h3>
              </div>
              <div className="flex items-center space-x-2">
                {/* Mini Circular SVG Progress Ring */}
                <div className="relative w-8 h-8 flex items-center justify-center">
                  <svg className="w-8 h-8 transform -rotate-90" viewBox="0 0 36 36">
                    <path
                      className="text-[#1C272A]"
                      strokeWidth="3.5"
                      stroke="currentColor"
                      fill="none"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                    <path
                      className="text-[#79E282] transition-all duration-500"
                      strokeDasharray={`${progressPercent}, 100`}
                      strokeWidth="3.5"
                      strokeLinecap="round"
                      stroke="currentColor"
                      fill="none"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <span className="absolute text-[9px] font-bold font-mono text-[#79E282]">{progressPercent}%</span>
                </div>
                <span className="text-[10px] font-mono bg-[var(--bg-surface)] text-[var(--text-muted)] px-2 py-0.5 rounded border border-[var(--border-color)]">
                  {completedSteps}/{totalSteps}
                </span>
              </div>
            </div>

            <div className="space-y-3">
              {clock.map((step) => {
                const isOverdue = step.status === 'overdue';
                const isDone = step.status === 'done';
                return (
                  <div
                    key={step.step_id}
                    className={`p-3.5 rounded-xl border transition-all flex items-start justify-between ${
                      isDone
                        ? 'bg-[#79E282]/5 border-[#79E282]/30'
                        : isOverdue
                        ? 'bg-[#D95F63]/10 border-[#D95F63]/30'
                        : 'bg-[var(--bg-surface)] border-[var(--border-color)]'
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded text-[var(--text-muted)]">
                          {step.step_id}
                        </span>
                        <h4 className="text-xs font-bold text-[var(--text-primary)]">{step.title}</h4>
                      </div>
                      <div className="text-[11px] text-[var(--text-muted)] flex items-center space-x-3 mt-1">
                        <span>Lead: <strong className="text-[var(--text-primary)]">{step.owner}</strong></span>
                        <span>SLA: <strong>{step.due_rule_hours}h</strong></span>
                        <span>Elapsed: <strong>{step.elapsed_hours}h</strong></span>
                      </div>
                    </div>

                    <button
                      onClick={() => toggleStep(step.step_id, step.status)}
                      className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition-colors flex items-center ${
                        isDone
                          ? 'bg-[#79E282] text-[#0B0B0D] hover:bg-white'
                          : isOverdue
                          ? 'bg-[#D95F63] text-white hover:bg-red-700 animate-pulse'
                          : 'bg-[#182124] text-[#79E282] hover:bg-[#79E282] hover:text-[#0B0B0D] border border-[#243338]'
                      }`}
                    >
                      {isDone ? (
                        <>
                          <CheckCircle className="mr-1 h-3 w-3" /> Done
                        </>
                      ) : isOverdue ? (
                        'Overdue!'
                      ) : (
                        'Mark Done'
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Recoverability Ranking List */}
        <div className="bg-[var(--bg-card)] p-6 rounded-2xl border border-[var(--border-color)] shadow-xl">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-[var(--border-color)]">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="h-4 w-4 text-[#79E282]" />
              <h3 className="font-bold text-sm text-[var(--text-primary)]">Recoverability Ranking (Advisory)</h3>
            </div>
            <span className="text-[10px] text-[var(--text-muted)] font-mono">Terminal Destinations</span>
          </div>

          {ranking.length === 0 ? (
            <p className="text-xs text-[var(--text-muted)] p-4 text-center">No terminal destinations traced yet.</p>
          ) : (
            <div className="space-y-3">
              {ranking.map((dest, i) => {
                const tierColor =
                  dest.tier === 'Act now'
                    ? 'bg-[#D95F63]/15 text-[#D95F63] border-[#D95F63]/40'
                    : dest.tier === 'Act soon'
                    ? 'bg-[#E6A94A]/15 text-[#E6A94A] border-[#E6A94A]/40'
                    : 'bg-[#368980]/15 text-[#79E282] border-[#368980]/40';

                return (
                  <div
                    key={i}
                    className="p-3.5 border border-[var(--border-color)] bg-[var(--bg-surface)] rounded-xl hover:border-[#79E282] transition-colors"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-mono font-bold text-[var(--text-primary)]">{dest.entity_name}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${tierColor}`}>
                        {dest.tier}
                      </span>
                    </div>
                    <div className="text-[11px] font-mono text-[var(--text-muted)] truncate mb-2">
                      {dest.destination_address}
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-[11px] text-[var(--text-muted)] bg-[var(--bg-card)] p-2 rounded-lg border border-[var(--border-color)]">
                      <div>
                        Traced: <strong className="text-[var(--text-primary)] font-mono">{dest.traced_amount} {dest.asset}</strong>
                      </div>
                      <div>
                        Confidence: <strong className="text-[#79E282] font-mono">{Math.round(dest.attribution_confidence * 100)}%</strong>
                      </div>
                      <div>
                        Elapsed: <strong className="text-[var(--text-primary)] font-mono">{dest.time_since_receipt_hours}h</strong>
                      </div>
                    </div>
                    <p className="text-[11px] text-[#79E282] mt-2 font-medium">
                      Action: {dest.recommended_action}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Cross-Case Convergence & Network View */}
      {related && (
        <div className="bg-[var(--bg-card)] p-6 rounded-2xl border border-[var(--border-color)] shadow-xl">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-[var(--border-color)]">
            <div className="flex items-center space-x-2">
              <Network className="h-4 w-4 text-[#38BDF8]" />
              <h3 className="font-bold text-sm text-[var(--text-primary)]">
                Complaint-to-Network Intelligence (Convergence)
              </h3>
            </div>
            <span className="text-xs bg-[#38BDF8]/15 text-[#38BDF8] px-2.5 py-0.5 rounded-full font-bold border border-[#38BDF8]/30">
              {related.converged_cases_count} Linked Cases Detected
            </span>
          </div>

          <div className="text-xs text-[var(--text-primary)] mb-4 p-3 bg-[#38BDF8]/10 border border-[#38BDF8]/30 rounded-xl leading-relaxed">
            <strong className="text-[#38BDF8]">Forensic Correlation:</strong> {related.investigative_guidance}
          </div>

          {related.links && related.links.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {related.links.map((link: any, idx: number) => (
                <div key={idx} className="p-3 border border-[var(--border-color)] rounded-xl bg-[var(--bg-surface)] text-xs">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-[#38BDF8] uppercase tracking-wide text-[10px]">
                      {link.link_type.replace('_', ' ')}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)] font-mono">
                      Confidence: {Math.round(link.confidence * 100)}%
                    </span>
                  </div>
                  <p className="text-[var(--text-primary)] text-[11px] leading-relaxed">{link.description}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Grounded AI Case Summary */}
      {summary && (
        <div className="bg-[var(--bg-card)] p-6 rounded-2xl border border-[var(--border-color)] shadow-xl">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-[var(--border-color)]">
            <div className="flex items-center space-x-2">
              <Cpu className="h-4 w-4 text-[#79E282]" />
              <h3 className="font-bold text-sm text-[var(--text-primary)]">
                Grounded Case Narrative (Zero Hallucination)
              </h3>
            </div>
            <span className="text-xs bg-[#79E282]/10 text-[#79E282] px-2.5 py-0.5 rounded-full font-bold border border-[#79E282]/30">
              100% Trace-Backed
            </span>
          </div>

          <div className="space-y-3">
            {summary.sentences?.map((st: any, i: number) => (
              <div
                key={i}
                className="flex items-start space-x-3 p-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-color)] text-xs"
              >
                <span
                  className={`text-[9.5px] px-2 py-0.5 rounded font-bold uppercase tracking-wider shrink-0 ${
                    st.fact_or_finding === 'FACT'
                      ? 'bg-[#38BDF8]/20 text-[#38BDF8] border border-[#38BDF8]/40'
                      : 'bg-[#79E282]/20 text-[#79E282] border border-[#79E282]/40'
                  }`}
                >
                  {st.fact_or_finding}
                </span>
                <div className="flex-1">
                  <p className="text-[var(--text-primary)] leading-relaxed">{st.text}</p>
                  <div className="text-[10px] text-[var(--text-muted)] mt-1 font-mono">
                    Sources: {st.source_record_ids?.slice(0, 3).join(', ')}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default RecoveryLayer;
