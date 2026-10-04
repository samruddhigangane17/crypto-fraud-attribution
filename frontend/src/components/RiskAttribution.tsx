import { useEffect, useState } from 'react';
import { apiJson } from '../lib/api';

interface RiskAttributionProps {
  activeCase: string | null;
}

const levelColors: Record<string, string> = {
  LOW: 'bg-green-50 border-green-100 text-green-700',
  MEDIUM: 'bg-yellow-50 border-yellow-100 text-yellow-700',
  HIGH: 'bg-orange-50 border-orange-100 text-orange-700',
  CRITICAL: 'bg-red-50 border-red-100 text-red-700',
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

  if (!activeCase) return <div className="p-8 text-center text-gray-500">No active case selected.</div>;
  if (loading) return <div>Loading risk assessment...</div>;
  if (error) return <div className="p-4 bg-red-50 text-red-700 border border-red-200 rounded-md">{error}</div>;
  if (!data) return null;

  const risk = data.risk_assessment;
  const conf = data.attribution_confidence;
  const riskStyle = levelColors[risk.risk_level] ?? levelColors.LOW;
  const confStyle = levelColors[conf.confidence_level === 'HIGH' ? 'LOW' : conf.confidence_level === 'MEDIUM' ? 'MEDIUM' : 'HIGH'];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h2 className="text-2xl font-bold mb-6 text-gray-800 border-b pb-4">Risk and Attribution</h2>

        <div className="grid grid-cols-2 gap-8 mb-8">
          <div className={`p-6 rounded-lg border text-center ${riskStyle}`}>
            <div className="text-sm font-medium mb-1 uppercase tracking-wider">Risk Score</div>
            <div className="text-5xl font-black">{Math.round(risk.overall_score)}</div>
            <div className="mt-2 font-medium">{risk.risk_level} risk (0-100)</div>
          </div>

          <div className={`p-6 rounded-lg border text-center ${confStyle}`}>
            <div className="text-sm font-medium mb-1 uppercase tracking-wider">Attribution Confidence</div>
            <div className="text-5xl font-black">{Math.round(conf.overall_confidence * 100)}%</div>
            <div className="mt-2 font-medium">
              {conf.confidence_level}
              {conf.primary_entity ? ` · ${conf.primary_entity}` : ' · no endpoint identified'}
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-500 mb-6">
          Risk and attribution confidence are separate. A high-risk path can end at an uncertain label, and a
          strong label does not prove who controlled the funds.
        </p>

        {risk.summary_rationale && (
          <p className="mb-6 text-gray-700 text-sm">{risk.summary_rationale}</p>
        )}

        <h3 className="text-lg font-semibold text-gray-800 mb-4">Risk Factors</h3>
        <div className="space-y-3 mb-8">
          {risk.factors?.map((f: any) => (
            <div key={f.factor_name} className="p-4 bg-gray-50 rounded border border-gray-200">
              <div className="flex justify-between">
                <h4 className="font-medium text-gray-900">
                  {f.factor_name} {f.triggered ? '· triggered' : ''}
                </h4>
                <span className="text-sm text-gray-500">
                  +{Number(f.score_contribution).toFixed(1)} (weight {f.weight})
                </span>
              </div>
              <p className="text-gray-600 text-sm mt-1">{f.rationale}</p>
            </div>
          ))}
        </div>

        <h3 className="text-lg font-semibold text-gray-800 mb-4">Attribution Confidence Factors</h3>
        <div className="space-y-3 mb-6">
          {conf.factors?.map((f: any) => (
            <div key={f.factor_name} className="p-4 bg-gray-50 rounded border border-gray-200">
              <div className="flex justify-between">
                <h4 className="font-medium text-gray-900">{f.factor_name}</h4>
                <span className="text-sm text-gray-500">
                  {Number(f.score_contribution).toFixed(2)} (weight {f.weight})
                </span>
              </div>
              <p className="text-gray-600 text-sm mt-1">{f.rationale}</p>
            </div>
          ))}
        </div>

        {conf.limitations?.length > 0 && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded text-sm text-blue-900">
            <div className="font-semibold mb-1">Limitations</div>
            <ul className="list-disc ml-5">
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
