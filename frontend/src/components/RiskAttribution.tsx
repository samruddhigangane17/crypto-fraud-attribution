import { useEffect, useState } from 'react';
import { apiJson } from '../lib/api';
import { ShieldAlert } from 'lucide-react';

interface RiskAttributionProps {
  activeCase: string | null;
}

const levelColors: Record<string, string> = {
  LOW: 'bg-[#79E282]/10 border-[#79E282]/30 text-[#79E282]',
  MEDIUM: 'bg-[#E6A94A]/10 border-[#E6A94A]/30 text-[#E6A94A]',
  HIGH: 'bg-[#F97316]/10 border-[#F97316]/30 text-[#F97316]',
  CRITICAL: 'bg-[#D95F63]/15 border-[#D95F63]/40 text-[#D95F63]',
};

const RiskAttribution: React.FC<RiskAttributionProps> = ({ activeCase }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeCase) return;
    setLoading(true);
    setError(null);
    apiJson(`/api/investigations/${activeCase}/risk`)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [activeCase]);

  if (!activeCase) {
    return (
      <div className="p-12 text-center text-[var(--text-muted)] bg-[var(--bg-card)] rounded-2xl border border-[var(--border-color)] max-w-xl mx-auto my-12">
        <ShieldAlert className="h-10 w-10 text-[#79E282] mx-auto mb-3" />
        <h3 className="text-base font-bold text-[var(--text-primary)]">No Active Case Selected</h3>
        <p className="text-xs mt-1">Please select an investigation from the header console to view Risk Assessment.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-12 text-center text-xs font-mono text-[#79E282] bg-[var(--bg-card)] rounded-2xl border border-[var(--border-color)] max-w-xl mx-auto my-12">
        ANALYZING RISK & HEURISTIC ATTRIBUTION TELEMETRY...
      </div>
    );
  }

  if (error) {
    return <div className="p-4 bg-[#D95F63]/10 text-[#D95F63] border border-[#D95F63]/30 rounded-xl text-xs">{error}</div>;
  }

  if (!data) return null;

  const risk = data.risk_assessment;
  const conf = data.attribution_confidence;
  const riskStyle = levelColors[risk.risk_level] ?? levelColors.LOW;
  const confStyle = levelColors[conf.confidence_level === 'HIGH' ? 'LOW' : conf.confidence_level === 'MEDIUM' ? 'MEDIUM' : 'CRITICAL'];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-[var(--bg-card)] p-8 rounded-2xl shadow-xl border border-[var(--border-color)] transition-colors">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-[var(--border-color)]">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center">
              <ShieldAlert className="mr-3 h-6 w-6 text-[#79E282]" />
              Explainable Risk & Forensic Attribution
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Deterministic 0–100 risk scoring and evidentiary confidence quantification.
            </p>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--bg-surface)] text-[#79E282] border border-[var(--border-color)]">
            Deterministic Engine
          </span>
        </div>

        {/* Big Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8">
          <div className={`p-6 rounded-2xl border text-center ${riskStyle}`}>
            <div className="text-xs font-bold uppercase tracking-wider mb-1">Composite Risk Score</div>
            <div className="text-5xl font-black font-mono my-2">{Math.round(risk.overall_score)}</div>
            <div className="text-xs font-bold uppercase tracking-wider">{risk.risk_level} Risk (0–100 Scale)</div>
          </div>

          <div className={`p-6 rounded-2xl border text-center ${confStyle}`}>
            <div className="text-xs font-bold uppercase tracking-wider mb-1">Attribution Confidence</div>
            <div className="text-5xl font-black font-mono my-2">{Math.round(conf.overall_confidence * 100)}%</div>
            <div className="text-xs font-bold uppercase tracking-wider">
              {conf.confidence_level}
              {conf.primary_entity ? ` · ${conf.primary_entity}` : ' · No Named Endpoint'}
            </div>
          </div>
        </div>

        <div className="p-3 bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-muted)] mb-6 leading-relaxed">
          <strong>Evidentiary Standard:</strong> Risk scores and attribution confidence are evaluated independently.
          A high-risk pathway may terminate at an unlabelled address, while verified exchange deposit labels indicate observed endpoints rather than definitive identity proof.
        </div>

        {risk.summary_rationale && (
          <div className="mb-6 p-4 rounded-xl bg-[#79E282]/5 border border-[#79E282]/20 text-xs text-[var(--text-primary)] leading-relaxed">
            <strong className="text-[#79E282]">Analytical Narrative:</strong> {risk.summary_rationale}
          </div>
        )}

        {/* Risk Factors */}
        <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-muted)] mb-3">
          Risk Contribution Factors
        </h3>
        <div className="space-y-3 mb-8">
          {risk.factors?.map((f: any) => (
            <div key={f.factor_name} className="p-4 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-color)]">
              <div className="flex justify-between items-center mb-1">
                <h4 className="text-xs font-bold text-[var(--text-primary)]">
                  {f.factor_name} {f.triggered ? <span className="text-[#D95F63] ml-1">· Triggered</span> : ''}
                </h4>
                <span className="text-xs font-mono text-[#79E282]">
                  +{Number(f.score_contribution).toFixed(1)} pts (w: {f.weight})
                </span>
              </div>
              <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">{f.rationale}</p>
            </div>
          ))}
        </div>

        {/* Attribution Confidence Factors */}
        <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-muted)] mb-3">
          Confidence Attenuation Factors
        </h3>
        <div className="space-y-3 mb-6">
          {conf.factors?.map((f: any) => (
            <div key={f.factor_name} className="p-4 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-color)]">
              <div className="flex justify-between items-center mb-1">
                <h4 className="text-xs font-bold text-[var(--text-primary)]">{f.factor_name}</h4>
                <span className="text-xs font-mono text-[#38BDF8]">
                  {Number(f.score_contribution).toFixed(2)} (w: {f.weight})
                </span>
              </div>
              <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">{f.rationale}</p>
            </div>
          ))}
        </div>

        {conf.limitations?.length > 0 && (
          <div className="p-4 bg-[#38BDF8]/10 border border-[#38BDF8]/30 rounded-xl text-xs text-[#38BDF8]">
            <div className="font-bold mb-1 uppercase tracking-wider text-[10px]">Forensic Limitations & Scope</div>
            <ul className="list-disc ml-5 space-y-0.5 text-[11px]">
              {conf.limitations.map((l: string) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default RiskAttribution;
