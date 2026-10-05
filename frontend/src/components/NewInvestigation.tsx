import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiJson, API_BASE } from '../lib/api';
import { supabase } from '../lib/supabase';
import { History, Check, ArrowRight, RefreshCw, Upload, FileSpreadsheet, CheckCircle2, AlertCircle } from 'lucide-react';
import type { CaseSummary } from '../App';

interface BulkRowError {
  row_index: number;
  wallet_address: string;
  error: string;
}

interface BulkUploadResponse {
  total_rows_read: number;
  successfully_ingested: number;
  failed_count: number;
  cases: Array<{
    case_id: string;
    complaint_ref: string;
    chain: string;
    wallet_address: string;
    status: string;
  }>;
  errors: BulkRowError[];
}

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

  // Bulk CSV upload states
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkResponse, setBulkResponse] = useState<BulkUploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const handleBulkUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setBulkError('Please select a .csv file to upload.');
      return;
    }
    setBulkLoading(true);
    setBulkError(null);
    setBulkResponse(null);

    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const formData = new FormData();
      formData.append('file', selectedFile);

      // Do NOT manually set Content-Type header; let the browser set multipart boundary
      const res = await fetch(`${API_BASE}/api/v1/cases/bulk`, {
        method: 'POST',
        headers,
        body: formData,
      });

      if (!res.ok) {
        let errorDetail = res.statusText;
        try {
          const body = await res.json();
          errorDetail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
        } catch {
          /* fallback to statusText */
        }
        throw new Error(`${res.status}: ${errorDetail}`);
      }

      const result: BulkUploadResponse = await res.json();
      setBulkResponse(result);

      // If at least one case was successfully ingested, refresh cases and notify parent
      if (result.successfully_ingested > 0) {
        onCaseCreated?.();
        fetchRecentCases();
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        setSelectedFile(null);
      }
    } catch (err) {
      setBulkError(err instanceof Error ? err.message : String(err));
    } finally {
      setBulkLoading(false);
    }
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

      {/* Bulk CSV Upload Section */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div className="flex items-center space-x-2 mb-4 pb-2 border-b border-gray-100">
          <FileSpreadsheet className="h-5 w-5 text-indigo-600" />
          <h3 className="text-lg font-bold text-gray-800">Bulk CSV Upload</h3>
          <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
            NCRP / SAHYOG
          </span>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          Batch ingest multiple suspect wallet addresses for multi-hop tracing. Expected CSV columns:
          <code className="text-indigo-600 ml-1 font-mono">complaint_ref, wallet_address, chain, amount, asset</code>
        </p>

        {bulkError && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm flex items-start space-x-2">
            <AlertCircle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
            <span>{bulkError}</span>
          </div>
        )}

        {bulkResponse && (
          <div className="mb-4 space-y-3">
            <div
              className={`p-3 rounded-md text-sm border flex items-center justify-between ${
                bulkResponse.failed_count === 0
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : 'bg-amber-50 text-amber-800 border-amber-200'
              }`}
            >
              <div className="flex items-center space-x-2">
                <CheckCircle2
                  className={`h-5 w-5 ${bulkResponse.failed_count === 0 ? 'text-emerald-600' : 'text-amber-600'}`}
                />
                <span className="font-medium">
                  Upload completed: {bulkResponse.successfully_ingested} of {bulkResponse.total_rows_read} rows ingested.
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 bg-gray-50 border border-gray-200 rounded-md">
                <div className="text-xs text-gray-500 font-medium">Total Rows</div>
                <div className="text-lg font-bold text-gray-800">{bulkResponse.total_rows_read}</div>
              </div>
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-md">
                <div className="text-xs text-emerald-600 font-medium">Successfully Ingested</div>
                <div className="text-lg font-bold text-emerald-700">{bulkResponse.successfully_ingested}</div>
              </div>
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
                <div className="text-xs text-amber-600 font-medium">Failed Rows</div>
                <div className="text-lg font-bold text-amber-700">{bulkResponse.failed_count}</div>
              </div>
            </div>

            {bulkResponse.errors && bulkResponse.errors.length > 0 && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-md text-xs text-red-800 space-y-1">
                <div className="font-semibold flex items-center mb-1 text-red-900">
                  <AlertCircle className="h-4 w-4 mr-1 text-red-600 inline" />
                  Row Validation Errors ({bulkResponse.errors.length}):
                </div>
                <ul className="list-disc list-inside space-y-0.5 max-h-32 overflow-y-auto">
                  {bulkResponse.errors.map((err, idx) => (
                    <li key={idx} className="font-mono text-[11px]">
                      Row {err.row_index} ({err.wallet_address || 'empty'}): {err.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleBulkUpload} className="space-y-4">
          <div className="flex items-center space-x-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              disabled={bulkLoading}
              onChange={(e) => {
                const file = e.target.files?.[0] || null;
                setSelectedFile(file);
                setBulkError(null);
                setBulkResponse(null);
              }}
              className="block w-full text-xs text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 border border-gray-300 rounded-md p-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={bulkLoading || !selectedFile}
              className="inline-flex items-center px-4 py-2 border border-transparent text-xs font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-indigo-300 disabled:cursor-not-allowed transition-colors shrink-0"
            >
              <Upload className="h-4 w-4 mr-1.5" />
              {bulkLoading ? 'Uploading CSV...' : 'Upload CSV'}
            </button>
          </div>
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
