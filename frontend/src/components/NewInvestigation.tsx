import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiJson } from '../lib/api';
import { History, Check, ArrowRight, RefreshCw } from 'lucide-react';
import type { CaseSummary } from '../App';

interface NewInvestigationProps {
  setActiveCase: (id: string) => void;
  activeCase: string | null;
  cases?: CaseSummary[];
  onCaseCreated?: () => void;
}

const NewInvestigation: React.FC<NewInvestigationProps> = ({
  setActiveCase,
  activeCase,
  cases = [],
  onCaseCreated,
}) => {
  const [address, setAddress] = useState('');
  const [chain, setChain] = useState('ethereum');
  const [windowDays, setWindowDays] = useState(30);
  const [hopLimit, setHopLimit] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [recentCases, setRecentCases] = useState<CaseSummary[]>(cases);
  const [loadingRecent, setLoadingRecent] = useState(false);
  const navigate = useNavigate();

  // Keep recent cases in sync with prop, or fetch if prop is empty
  useEffect(() => {
    if (cases && cases.length > 0) {
      setRecentCases(cases);
    } else {
      fetchRecentCases();
    }
  }, [cases]);

  const fetchRecentCases = async () => {
    setLoadingRecent(true);
    try {
      const list = await apiJson<CaseSummary[]>('/api/v1/cases?limit=15');
      if (Array.isArray(list)) {
        setRecentCases(list);
      }
    } catch {
      // Fallback silently if offline or unconfigured
    } finally {
      setLoadingRecent(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setNotice(null);
    setWarnings([]);
    try {
      const created = await apiJson('/api/investigations', {
        method: 'POST',
        body: JSON.stringify({ chain, reported_address: address.trim() }),
      });
      const startTime = new Date(Date.now() - windowDays * 24 * 60 * 60 * 1000).toISOString();
      const traced = await apiJson(`/api/investigations/${created.id}/trace`, {
        method: 'POST',
        body: JSON.stringify({
          max_hops: hopLimit,
          min_taint_share: 0.05,
          start_time: startTime,
        }),
      });
      // Only make this the active case once tracing succeeded, so the other pages never open a
      // case that has no results (which used to surface as confusing 404s).
      setActiveCase(created.id);
      onCaseCreated?.();
      fetchRecentCases();
      setWarnings(traced.warnings ?? []);
      if (traced.notice) {
        setNotice(traced.notice);
        return; // stay here: nothing to show on the graph
      }
      if ((traced.warnings ?? []).length === 0) navigate('/graph');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCase = (caseId: string) => {
    setActiveCase(caseId);
    navigate('/graph');
  };

  const getChainBadgeStyle = (chainName: string) => {
    const c = (chainName || '').toLowerCase();
    if (c === 'ethereum' || c === 'eth') return 'bg-blue-100 text-blue-800 border-blue-200';
    if (c === 'bitcoin' || c === 'btc') return 'bg-amber-100 text-amber-800 border-amber-200';
    if (c === 'tron' || c === 'trx') return 'bg-red-100 text-red-800 border-red-200';
    if (c === 'bsc') return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    return 'bg-gray-100 text-gray-800 border-gray-200';
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* New Investigation Form */}
      <div className="bg-white p-8 rounded-lg shadow-sm border border-gray-200">
        <h2 className="text-2xl font-bold mb-6 text-gray-800">New Investigation</h2>
        {activeCase && (
          <div className="mb-6 p-4 bg-green-50 text-green-700 border border-green-200 rounded-md flex items-center justify-between">
            <span className="font-mono text-sm">Active Case: {activeCase}</span>
            <button
              onClick={() => navigate('/graph')}
              className="text-xs bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700 flex items-center"
            >
              View Fund-Flow Graph <ArrowRight className="h-3 w-3 ml-1" />
            </button>
          </div>
        )}
        {notice && (
          <div className="mb-6 p-4 bg-amber-50 text-amber-800 border border-amber-200 rounded-md">{notice}</div>
        )}
        {warnings.length > 0 && (
          <div className="mb-6 p-4 bg-amber-50 text-amber-800 border border-amber-200 rounded-md space-y-1">
            {warnings.map((w) => (
              <div key={w}>{w}</div>
            ))}
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
              className="w-full border border-gray-300 rounded-md p-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono text-sm"
              placeholder="0x..."
              value={address}
              onChange={(e) => setAddress(e.target.value)}
            />
            <p className="mt-1 text-xs text-gray-500">
              Demo address for offline mock data: <code className="text-indigo-600 font-mono">0xmock_wallet_a</code>
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
            className="w-full bg-indigo-600 text-white p-3 rounded-md font-medium hover:bg-indigo-700 disabled:bg-indigo-300 transition-colors shadow-sm"
          >
            {loading ? 'Starting Investigation...' : 'Start Investigation'}
          </button>
        </form>
      </div>

      {/* Recent Investigations Section */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div className="flex justify-between items-center mb-4 pb-2 border-b border-gray-100">
          <div className="flex items-center space-x-2">
            <History className="h-5 w-5 text-indigo-600" />
            <h3 className="text-lg font-bold text-gray-800">Recent Investigations</h3>
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium">
              {recentCases.length}
            </span>
          </div>
          <button
            onClick={() => {
              onCaseCreated?.();
              fetchRecentCases();
            }}
            disabled={loadingRecent}
            className="text-xs text-gray-500 hover:text-indigo-600 flex items-center p-1 rounded hover:bg-gray-50"
            title="Refresh list"
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loadingRecent ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {recentCases.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            {loadingRecent ? 'Loading investigations...' : 'No previous investigations found. Start your first trace above.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3">Case ID</th>
                  <th className="px-4 py-3">Chain</th>
                  <th className="px-4 py-3">Reported Wallet</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentCases.slice(0, 10).map((c) => {
                  const isCurrent = c.id === activeCase;
                  const dateStr = c.created_at ? new Date(c.created_at).toLocaleString() : 'Recently';
                  return (
                    <tr key={c.id} className={`hover:bg-gray-50/80 transition-colors ${isCurrent ? 'bg-indigo-50/40' : ''}`}>
                      <td className="px-4 py-3 font-mono text-xs text-gray-600" title={c.id}>
                        {c.id.slice(0, 8)}...
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${getChainBadgeStyle(c.chain)}`}>
                          {c.chain.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-800" title={c.reported_address}>
                        {c.reported_address
                          ? c.reported_address.length > 20
                            ? `${c.reported_address.slice(0, 10)}...${c.reported_address.slice(-6)}`
                            : c.reported_address
                          : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                            c.status === 'completed'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">{dateStr}</td>
                      <td className="px-4 py-3 text-right">
                        {isCurrent ? (
                          <span className="inline-flex items-center text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded border border-emerald-200">
                            <Check className="h-3 w-3 mr-1" /> Active
                          </span>
                        ) : (
                          <button
                            onClick={() => handleOpenCase(c.id)}
                            className="inline-flex items-center text-xs font-medium text-indigo-600 hover:text-white bg-indigo-50 hover:bg-indigo-600 px-2.5 py-1 rounded border border-indigo-200 hover:border-indigo-600 transition-colors"
                          >
                            Open Investigation
                            <ArrowRight className="h-3 w-3 ml-1" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default NewInvestigation;
