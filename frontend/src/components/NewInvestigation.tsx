import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface NewInvestigationProps {
  setActiveCase: (id: string) => void;
  activeCase: string | null;
}

const NewInvestigation: React.FC<NewInvestigationProps> = ({ setActiveCase, activeCase }) => {
  const [address, setAddress] = useState('');
  const [chain, setChain] = useState('ethereum');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/investigations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chain, reported_address: address }),
      });
      const data = await res.json();
      setActiveCase(data.id);
      
      // Start tracing right after creation
      await fetch(`http://localhost:8000/api/investigations/${data.id}/trace`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_hops: 5, min_taint_share: 0.05 }),
      });
      
      navigate('/graph');
    } catch (err) {
      console.error(err);
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
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Blockchain</label>
          <select
            className="w-full border border-gray-300 rounded-md p-2 focus:ring-indigo-500 focus:border-indigo-500"
            value={chain}
            onChange={(e) => setChain(e.target.value)}
          >
            <option value="ethereum">Ethereum (ETH)</option>
            <option value="bitcoin">Bitcoin (BTC)</option>
            <option value="tron">TRON (TRX)</option>
            <option value="bsc">BNB Smart Chain (BSC)</option>
          </select>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Time Window (days)</label>
            <input type="number" defaultValue={30} className="w-full border border-gray-300 rounded-md p-2" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Hop Limit</label>
            <input type="number" defaultValue={5} className="w-full border border-gray-300 rounded-md p-2" />
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
