import React, { useState, useEffect } from 'react';
import { Clock, ShieldCheck, AlertTriangle, Network, CheckCircle, ShieldAlert, Cpu, FileCheck } from 'lucide-react';
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

      // Check case for typology
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
    return <div className="p-8 text-center text-gray-500">No active case selected. Select or create an investigation first.</div>;
  }

  const overdueCount = clock.filter((s) => s.status === 'overdue').length;

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Safe-Handling Advisory Banner */}
      <div className="p-4 bg-amber-50 border-l-4 border-amber-500 rounded-r-md flex items-start space-x-3 text-amber-900 shadow-sm">
        <ShieldAlert className="h-6 w-6 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-semibold text-sm tracking-wide uppercase">Official Safe-Handling Advisory</h4>
          <p className="text-xs mt-1 text-amber-800">
            Law enforcement officials, regulatory bodies, and genuine recovery processes never ask a victim for private keys,
            seed phrases, OTPs, or upfront recovery fees. Anyone asking for fees or private credentials claiming to be a
            "recovery agent" is engaging in criminal fraud.
          </p>
        </div>
      </div>

      {/* Header */}
      <div className="flex justify-between items-center bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center">
            <Clock className="mr-3 text-indigo-600 h-7 w-7" />
            Golden Hour Recovery Layer
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Orchestrates time-critical freeze notices, VASP ranking, fraud typology checklists, and cross-case network coordination.
          </p>
        </div>
        <button
          onClick={loadRecoveryData}
          disabled={loading}
          className="px-4 py-2 bg-indigo-50 text-indigo-700 font-medium rounded hover:bg-indigo-100 transition-colors text-sm"
        >
          {loading ? 'Refreshing...' : 'Refresh Timeline'}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm">{error}</div>
      )}

      {overdueCount > 0 && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-3 text-red-800">
          <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0" />
          <div className="text-sm">
            <strong>Urgent Alert:</strong> {overdueCount} critical step(s) have passed their due window! Immediate action required to prevent asset flight.
          </div>
        </div>
      )}

      {/* Typology & Evidence Checklist */}
      {typology && (
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-100">
            <h3 className="font-bold text-gray-800 flex items-center">
              <FileCheck className="mr-2 h-5 w-5 text-indigo-500" />
              Recovery Path Engine: {typology.name || typology.typology}
            </h3>
            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
              {typology.recommended_request_type}
            </span>
          </div>
          <p className="text-xs text-gray-600 mb-3">{typology.description}</p>
          <div className="bg-gray-50 p-3 rounded border border-gray-200">
            <h5 className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">Pre-Packaged Evidence Checklist:</h5>
            <ul className="text-xs text-gray-600 space-y-1">
              {typology.evidence_checklist?.map((item: string, i: number) => (
                <li key={i} className="flex items-center">
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 mr-2" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="text-xs text-gray-500 mt-2">
            Responsible Entity: <strong className="text-gray-700">{typology.responsible_party}</strong>
          </div>
        </div>
      )}

      {/* Grid: Clock + Ranking */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recovery Clock Timeline */}
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-gray-100">
            <h3 className="font-bold text-gray-800 flex items-center">
              <Clock className="mr-2 h-5 w-5 text-indigo-500" />
              Recovery Clock Timeline
            </h3>
            <span className="text-xs bg-indigo-50 text-indigo-700 px-2.5 py-0.5 rounded-full font-medium">
              Configurable Rules
            </span>
          </div>

          <div className="space-y-4">
            {clock.map((step) => {
              const isOverdue = step.status === 'overdue';
              const isDone = step.status === 'done';
              return (
                <div
                  key={step.step_id}
                  className={`p-3.5 rounded-lg border transition-all flex items-start justify-between ${
                    isDone
                      ? 'bg-green-50/50 border-green-200'
                      : isOverdue
                      ? 'bg-red-50/50 border-red-300'
                      : 'bg-gray-50 border-gray-200'
                  }`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-semibold px-2 py-0.5 bg-white border border-gray-200 rounded text-gray-600">
                        {step.step_id}
                      </span>
                      <h4 className="text-sm font-medium text-gray-900">{step.title}</h4>
                    </div>
                    <div className="text-xs text-gray-500 flex items-center space-x-3 mt-1">
                      <span>Owner: <strong className="text-gray-700">{step.owner}</strong></span>
                      <span>Due: <strong>{step.due_rule_hours}h</strong></span>
                      <span>Elapsed: <strong>{step.elapsed_hours}h</strong></span>
                    </div>
                  </div>

                  <button
                    onClick={() => toggleStep(step.step_id, step.status)}
                    className={`px-3 py-1 text-xs font-medium rounded transition-colors flex items-center ${
                      isDone
                        ? 'bg-green-600 text-white hover:bg-green-700'
                        : isOverdue
                        ? 'bg-red-600 text-white hover:bg-red-700'
                        : 'bg-indigo-600 text-white hover:bg-indigo-700'
                    }`}
                  >
                    {isDone ? (
                      <>
                        <CheckCircle className="mr-1 h-3.5 w-3.5" /> Done
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

        {/* Recoverability Ranking */}
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-gray-100">
            <h3 className="font-bold text-gray-800 flex items-center">
              <ShieldCheck className="mr-2 h-5 w-5 text-indigo-500" />
              Recoverability Ranking (Advisory)
            </h3>
            <span className="text-xs text-gray-500 font-mono">last observed destination</span>
          </div>

          {ranking.length === 0 ? (
            <p className="text-sm text-gray-500 p-4 text-center">No terminal destinations traced yet.</p>
          ) : (
            <div className="space-y-3">
              {ranking.map((dest, i) => {
                const tierColor =
                  dest.tier === 'Act now'
                    ? 'bg-red-100 text-red-800 border-red-300'
                    : dest.tier === 'Act soon'
                    ? 'bg-amber-100 text-amber-800 border-amber-300'
                    : 'bg-blue-50 text-blue-800 border-blue-200';

                return (
                  <div key={i} className="p-3.5 border border-gray-200 rounded-lg hover:border-indigo-300 transition-colors">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-mono font-bold text-gray-800">{dest.entity_name}</span>
                      <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold border ${tierColor}`}>
                        {dest.tier}
                      </span>
                    </div>
                    <div className="text-xs font-mono text-gray-500 truncate mb-2">
                      {dest.destination_address}
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs text-gray-600 bg-gray-50 p-2 rounded">
                      <div>
                        Traced: <strong className="text-gray-900">{dest.traced_amount} {dest.asset}</strong>
                      </div>
                      <div>
                        Confidence: <strong className="text-gray-900">{Math.round(dest.attribution_confidence * 100)}%</strong>
                      </div>
                      <div>
                        Elapsed: <strong className="text-gray-900">{dest.time_since_receipt_hours}h</strong>
                      </div>
                    </div>
                    <p className="text-xs text-indigo-700 mt-2 font-medium">
                      Action: {dest.recommended_action}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Cross-Case Convergence & Syndicate View */}
      {related && (
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-gray-100">
            <h3 className="font-bold text-gray-800 flex items-center">
              <Network className="mr-2 h-5 w-5 text-indigo-500" />
              Cross-Case Convergence & Network View
            </h3>
            <span className="text-xs bg-purple-50 text-purple-700 px-2.5 py-0.5 rounded-full font-medium">
              {related.converged_cases_count} Linked Cases Detected
            </span>
          </div>

          <div className="text-sm text-gray-600 mb-4 p-3 bg-purple-50 border border-purple-200 rounded-md">
            <strong>Forensic Assessment:</strong> {related.investigative_guidance}
          </div>

          {related.links && related.links.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {related.links.map((link: any, idx: number) => (
                <div key={idx} className="p-3 border border-gray-200 rounded bg-gray-50 text-xs">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-semibold text-purple-900 uppercase tracking-wide">
                      {link.link_type.replace('_', ' ')}
                    </span>
                    <span className="text-gray-500">Confidence: {Math.round(link.confidence * 100)}%</span>
                  </div>
                  <p className="text-gray-700">{link.description}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Grounded AI Case Summary */}
      {summary && (
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-gray-100">
            <h3 className="font-bold text-gray-800 flex items-center">
              <Cpu className="mr-2 h-5 w-5 text-indigo-500" />
              Grounded Case Narrative (Zero Hallucination)
            </h3>
            <span className="text-xs bg-green-50 text-green-700 px-2.5 py-0.5 rounded-full font-medium">
              100% Trace-Backed
            </span>
          </div>

          <div className="space-y-3">
            {summary.sentences?.map((st: any, i: number) => (
              <div key={i} className="flex items-start space-x-3 p-2.5 rounded bg-gray-50 border border-gray-100 text-sm">
                <span
                  className={`text-xs px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
                    st.fact_or_finding === 'FACT'
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-purple-100 text-purple-800'
                  }`}
                >
                  {st.fact_or_finding}
                </span>
                <div className="flex-1">
                  <p className="text-gray-800">{st.text}</p>
                  <div className="text-xs text-gray-400 mt-1 font-mono">
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
