import { useEffect, useState } from 'react';

interface RiskAttributionProps {
  activeCase: string | null;
}

const RiskAttribution: React.FC<RiskAttributionProps> = ({ activeCase }) => {
  const [riskData, setRiskData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeCase) return;
    setLoading(true);
    fetch(`http://localhost:8000/api/investigations/${activeCase}/risk`)
      .then(res => res.json())
      .then(data => setRiskData(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeCase]);

  if (!activeCase) return <div className="p-8 text-center text-gray-500">No active case selected.</div>;
  if (loading) return <div>Loading risk assessment...</div>;
  if (!riskData) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h2 className="text-2xl font-bold mb-6 text-gray-800 border-b pb-4">Risk and Attribution</h2>
        
        <div className="grid grid-cols-2 gap-8 mb-8">
          <div className="p-6 bg-red-50 rounded-lg border border-red-100 text-center">
            <div className="text-sm font-medium text-red-600 mb-1 uppercase tracking-wider">Risk Score</div>
            <div className="text-5xl font-black text-red-700">{riskData.score}</div>
            <div className="mt-2 text-red-800 font-medium">{riskData.category} Risk</div>
          </div>
          
          <div className="p-6 bg-green-50 rounded-lg border border-green-100 text-center">
            <div className="text-sm font-medium text-green-600 mb-1 uppercase tracking-wider">Attribution Confidence</div>
            <div className="text-5xl font-black text-green-700">{riskData.confidence}</div>
            <div className="mt-2 text-green-800 font-medium">Exchange Endpoint Found</div>
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Contributing Factors</h3>
          <div className="space-y-3">
            {riskData.factors?.map((factor: any, i: number) => (
              <div key={i} className="flex items-start p-4 bg-gray-50 rounded border border-gray-200">
                <div className="flex-1">
                  <h4 className="font-medium text-gray-900">{factor.signal}</h4>
                  <p className="text-gray-600 text-sm mt-1">{factor.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RiskAttribution;
