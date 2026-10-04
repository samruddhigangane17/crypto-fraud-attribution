import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiJson } from '../lib/api';

interface NewInvestigationProps {
  setActiveCase: (id: string) => void;
  activeCase: string | null;
}

const NewInvestigation: React.FC<NewInvestigationProps> = ({ setActiveCase, activeCase }) => {
  const [address, setAddress] = useState('');
  const [chain, setChain] = useState('ethereum');
  const [windowDays, setWindowDays] = useState(30);
  const [hopLimit, setHopLimit] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const created = await apiJson('/api/investigations', {
        method: 'POST',
        body: JSON.stringify({ chain, reported_address: address.trim() }),
      });
      setActiveCase(created.id);

      const startTime = new Date(Date.now() - windowDays * 24 * 60 * 60 * 1000).toISOString();
      await apiJson(`/api/investigations/${created.id}/trace`, {
        method: 'POST',
        body: JSON.stringify({
          max_hops: hopLimit,
          min_taint_share: 0.05,
          start_time: startTime,
        }),
      });
      navigate('/graph');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto bg-white p-8 rounded-lg shadow-sm border border-gray-200">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">New Investigation</h2>
      {activeCase && (
        <div className="mb-6 p-4 bg-green-50 text-green-700 border border-green-200 rounded-md">
          Current active case: {activeCase}
        </div>
      )}
      {error && (
        <div className="mb-6 p-4 bg-red-50 text-red-700 border border-red-200 rounded-md">{error}</div>
      )}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Suspicious Wallet Address</label>
          <input
            type="text"
            required
            className="w-full border border-gray-300 rounded-md p-2 focus:ring-indigo-500 focus:border-indigo-500"
            placeholder="0x..."
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
          <p className="mt-1 text-xs text-gray-500">
            Demo address for offline mock data: 0xmock_wallet_a
          </p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Blockchain</label>
          <select
            className="w-full border border-gray-300 rounded-md p-2 focus:ring-indigo-500 focus:border-indigo-500"
            value={chain}
            onChange={(e) => setChain(e.target.value)}
          >
            <option value="auto">Auto-detect</option>
            <option value="ethereum">Ethereum (ETH)</option>
            <option value="bitcoin">Bitcoin (BTC)</option>
            <option value="tron">TRON (TRX)</option>
            <option value="bsc">BNB Smart Chain (BSC)</option>
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Time Window (days)</label>
            <input
              type="number"
              min={1}
              value={windowDays}
              onChange={(e) => setWindowDays(Number(e.target.value) || 1)}
              className="w-full border border-gray-300 rounded-md p-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Hop Limit</label>
            <input
              type="number"
              min={1}
              max={10}
              value={hopLimit}
              onChange={(e) => setHopLimit(Number(e.target.value) || 1)}
              className="w-full border border-gray-300 rounded-md p-2"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-indigo-600 text-white p-3 rounded-md font-medium hover:bg-indigo-700 disabled:bg-indigo-300 transition-colors"
        >
          {loading ? 'Starting Investigation...' : 'Start Investigation'}
        </button>
      </form>
    </div>
  );
};

export default NewInvestigation;
