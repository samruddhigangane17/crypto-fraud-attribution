import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiJson, API_BASE } from '../lib/api';
import { supabase } from '../lib/supabase';
import {
  History,
  Check,
  ArrowRight,
  RefreshCw,
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Shield,
  Layers,
  Sparkles,
} from 'lucide-react';
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
  selectedChain?: 'ethereum' | 'tron' | 'bitcoin' | 'bsc';
  onSelectChain?: (chain: 'ethereum' | 'tron' | 'bitcoin' | 'bsc') => void;
}

const CHAIN_OPTIONS = [
  { id: 'ethereum', name: 'Ethereum', ticker: 'ETH', color: 'from-[#6366F1] to-[#312E81]', border: '#6366F1', text: '#818CF8' },
  { id: 'tron', name: 'TRON', ticker: 'TRX', color: 'from-[#EF4444] to-[#7F1D1D]', border: '#EF4444', text: '#F87171' },
  { id: 'bitcoin', name: 'Bitcoin', ticker: 'BTC', color: 'from-[#F59E0B] to-[#78350F]', border: '#F59E0B', text: '#FBBF24' },
  { id: 'bsc', name: 'BNB Chain', ticker: 'BSC', color: 'from-[#EAB308] to-[#713F12]', border: '#EAB308', text: '#FACC15' },
];

const SAMPLE_WALLETS = [
  { label: 'ETH Demo: 0xmock_wallet_a (Verified 5-Hop VASP Path)', addr: '0xmock_wallet_a', chain: 'ethereum' as const },
  { label: 'BTC Live: bc1qm986... (Live Mainnet 15-Node Graph)', addr: 'bc1qm986eljmd9749cmrqsu3yudp7gg7e2ws9k09hg', chain: 'bitcoin' as const },
  { label: 'ETH Demo: 0xmock_wallet_b (Intermediate Mule Peel)', addr: '0xmock_wallet_b', chain: 'ethereum' as const },
  { label: 'ETH Demo: 0xmock_wallet_c (Pre-VASP Deposit)', addr: '0xmock_wallet_c', chain: 'ethereum' as const },
  { label: 'TRON Live: High-Velocity Hub', addr: 'T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb', chain: 'tron' as const },
];

const NewInvestigation: React.FC<NewInvestigationProps> = ({
  setActiveCase,
  activeCase,
  cases = [],
  onCaseCreated,
  selectedChain,
  onSelectChain,
}) => {
  const [address, setAddress] = useState('');
  const [chain, setChain] = useState<'ethereum' | 'tron' | 'bitcoin' | 'bsc' | 'auto'>('ethereum');
  const [windowDays, setWindowDays] = useState(90);
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

  // Sync chain if selectedChain passed from 3D coins hero
  useEffect(() => {
    if (selectedChain) {
      setChain(selectedChain);
    }
  }, [selectedChain]);

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

  const handleSelectChain = (c: 'ethereum' | 'tron' | 'bitcoin' | 'bsc') => {
    setChain(c);
    onSelectChain?.(c);
  };

  const handleQuickFill = (sample: typeof SAMPLE_WALLETS[number]) => {
    setAddress(sample.addr);
    setChain(sample.chain);
    onSelectChain?.(sample.chain);
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

      setActiveCase(created.id);
      onCaseCreated?.();
      fetchRecentCases();
      setWarnings(traced.warnings ?? []);
      if (traced.notice) {
        setNotice(traced.notice);
      }
      // Always transition directly into the Fund-Flow Graph workspace
      navigate('/graph');
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes('502') || errMsg.includes('provider') || errMsg.includes('API key')) {
        setError(`${errMsg} — External blockchain API rate-limit reached or key unconfigured. For instant guaranteed traversal, try '0xmock_wallet_a' above!`);
      } else {
        setError(errMsg);
      }
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
        } catch {}
        throw new Error(`${res.status}: ${errorDetail}`);
      }

      const result: BulkUploadResponse = await res.json();
      setBulkResponse(result);

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
    if (c === 'ethereum' || c === 'eth') return 'bg-[#6366F1]/10 text-[#818CF8] border-[#6366F1]/30';
    if (c === 'bitcoin' || c === 'btc') return 'bg-[#F59E0B]/10 text-[#FBBF24] border-[#F59E0B]/30';
    if (c === 'tron' || c === 'trx') return 'bg-[#EF4444]/10 text-[#F87171] border-[#EF4444]/30';
    if (c === 'bsc') return 'bg-[#EAB308]/10 text-[#FACC15] border-[#EAB308]/30';
    return 'bg-[var(--bg-secondary)] text-[var(--text-muted)] border-[var(--border-color)]';
  };

  return (
    <div id="investigation-form" className="max-w-4xl mx-auto space-y-8">
      {/* Primary Investigation Setup Card */}
      <div className="bg-[var(--bg-card)] p-8 rounded-2xl shadow-xl border border-[var(--border-color)] transition-colors duration-200">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-[var(--border-color)]">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center">
              <Shield className="mr-3 h-6 w-6 text-[var(--accent-primary)]" />
              Initiate Fraud Investigation
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Submit reported fraudulent wallets to reconstruct forward fund dispersion, taint flow, and VASP off-ramps.
            </p>
          </div>
          <span className="text-[11px] font-mono px-2.5 py-1 rounded-full bg-[var(--bg-secondary)] text-[var(--accent-primary)] border border-[var(--border-color)]">
            Automated Traversal
          </span>
        </div>

        {activeCase && (
          <div className="mb-6 p-4 bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border border-[var(--accent-primary)]/30 rounded-xl flex items-center justify-between">
            <span className="font-mono text-xs">
              Active Investigation Loaded: <strong className="underline">{activeCase}</strong>
            </span>
            <button
              onClick={() => navigate('/graph')}
              className="text-xs bg-[var(--accent-primary)] text-[var(--bg-card)] font-bold px-3 py-1.5 rounded-lg hover:opacity-90 flex items-center transition-colors shadow-sm"
            >
              Inspect Graph <ArrowRight className="h-3 w-3 ml-1.5" />
            </button>
          </div>
        )}

        {notice && (
          <div className="mb-6 p-4 bg-[#E6A94A]/10 text-[#E6A94A] border border-[#E6A94A]/30 rounded-xl text-xs">
            {notice}
          </div>
        )}

        {warnings.length > 0 && (
          <div className="mb-6 p-4 bg-[#E6A94A]/10 text-[#E6A94A] border border-[#E6A94A]/30 rounded-xl space-y-1 text-xs">
            {warnings.map((w) => (
              <div key={w}>{w}</div>
            ))}
          </div>
        )}

        {error && (
          <div className="mb-6 p-4 bg-[#D95F63]/10 text-[#D95F63] border border-[#D95F63]/30 rounded-xl text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Target Chain Selector Cards */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2.5">
              Target Blockchain Network
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-2">
              {CHAIN_OPTIONS.map((opt) => {
                const isSelected = chain === opt.id;
                return (
                  <button
                    type="button"
                    key={opt.id}
                    onClick={() => handleSelectChain(opt.id as any)}
                    className={`p-3 rounded-xl border text-left transition-all duration-200 flex flex-col justify-between ${
                      isSelected
                        ? 'border-[var(--accent-primary)] bg-[var(--bg-secondary)] shadow-md ring-1 ring-[var(--accent-primary)]'
                        : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--accent-secondary)]'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold text-[var(--text-primary)]">{opt.name}</span>
                      <span
                        className="text-[10px] font-mono px-1.5 py-0.5 rounded font-bold"
                        style={{ color: opt.text, backgroundColor: `${opt.border}20` }}
                      >
                        {opt.ticker}
                      </span>
                    </div>
                    <div className="text-[10px] text-[var(--text-muted)]">
                      {isSelected ? 'Active Target' : 'Click to select'}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Wallet Address Input */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label htmlFor="wallet-address-input" className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                Reported Incident Wallet Address
              </label>
              <span className="text-[10px] text-[var(--accent-primary)]">Supports BTC, ETH, TRX, BSC</span>
            </div>
            <input
              id="wallet-address-input"
              type="text"
              required
              className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl p-3 focus:ring-2 focus:ring-[var(--accent-primary)] focus:border-[var(--accent-primary)] font-mono text-sm text-[var(--text-primary)] transition-all shadow-inner"
              placeholder="e.g. 0xmock_wallet_a or T9yD14Nj... or bc1q..."
              value={address}
              onChange={(e) => setAddress(e.target.value)}
            />

            {/* Quick Fill Sample Wallets */}
            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-[var(--text-muted)] mr-1 flex items-center">
                <Sparkles className="h-3 w-3 mr-1 text-[var(--accent-primary)]" /> Quick Test:
              </span>
              {SAMPLE_WALLETS.map((s, idx) => (
                <button
                  type="button"
                  key={idx}
                  onClick={() => handleQuickFill(s)}
                  className="text-[10px] font-mono px-2 py-1 rounded-md bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--accent-primary)] hover:bg-[var(--border-color)] border border-[var(--border-color)] transition-colors"
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Trace Parameters: Time Window & Hop Limit */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-[var(--bg-surface)] p-3.5 rounded-xl border border-[var(--border-color)]">
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1">
                Analysis Lookback Window (Days)
              </label>
              <input
                type="number"
                min={1}
                max={365}
                value={windowDays}
                onChange={(e) => setWindowDays(Number(e.target.value) || 1)}
                className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg p-2 text-sm font-mono text-[var(--text-primary)] focus:ring-2 focus:ring-[#79E282]"
              />
              <span className="text-[10px] text-[var(--text-muted)] mt-1 block">Examines transactions within this timeframe.</span>
            </div>

            <div className="bg-[var(--bg-surface)] p-3.5 rounded-xl border border-[var(--border-color)]">
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1">
                Forward Traversal Hop Depth (1–10)
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={hopLimit}
                onChange={(e) => setHopLimit(Number(e.target.value) || 1)}
                className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg p-2 text-sm font-mono text-[var(--text-primary)] focus:ring-2 focus:ring-[#79E282]"
              />
              <span className="text-[10px] text-[var(--text-muted)] mt-1 block">Maximum sequential transfers traced from source.</span>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#79E282] text-[#0B0B0D] py-3.5 rounded-xl font-bold hover:bg-white disabled:bg-[#368980]/40 disabled:text-[#899695] transition-all duration-200 shadow-lg shadow-[#79E282]/10 flex items-center justify-center space-x-2"
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin text-[#0B0B0D]" />
                <span>Traversing Transaction Pathways...</span>
              </>
            ) : (
              <>
                <Layers className="h-4 w-4" />
                <span>Execute Multi-Hop Forward Trace</span>
                <ArrowRight className="h-4 w-4 ml-1" />
              </>
            )}
          </button>
        </form>
      </div>

      {/* Bulk CSV Batch Ingestion Section */}
      <div className="bg-[var(--bg-card)] p-6 rounded-2xl shadow-xl border border-[var(--border-color)] transition-colors duration-200">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-[var(--border-color)]">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-lg bg-[#368980]/15 text-[#79E282]">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[var(--text-primary)]">Bulk CSV Intake Protocol</h3>
              <p className="text-xs text-[var(--text-muted)]">NCRP / SAHYOG Automated Multi-Case Batch Ingestion</p>
            </div>
          </div>
          <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-[#38BDF8]/10 text-[#38BDF8] border border-[#38BDF8]/30">
            Batch API
          </span>
        </div>

        <p className="text-xs text-[var(--text-muted)] mb-4 leading-relaxed">
          Batch ingest suspect wallet addresses directly into the forensic pipeline. Expected CSV format:
          <code className="text-[#79E282] ml-1 font-mono text-[11px] bg-[var(--bg-surface)] px-1.5 py-0.5 rounded">
            complaint_ref, wallet_address, chain, amount, asset
          </code>
        </p>

        {bulkError && (
          <div className="mb-4 p-3 bg-[#D95F63]/10 text-[#D95F63] border border-[#D95F63]/30 rounded-xl text-xs flex items-start space-x-2">
            <AlertCircle className="h-4 w-4 text-[#D95F63] shrink-0 mt-0.5" />
            <span>{bulkError}</span>
          </div>
        )}

        {bulkResponse && (
          <div className="mb-4 space-y-3">
            <div
              className={`p-3 rounded-xl text-xs border flex items-center justify-between ${
                bulkResponse.failed_count === 0
                  ? 'bg-[#79E282]/10 text-[#79E282] border-[#79E282]/30'
                  : 'bg-[#E6A94A]/10 text-[#E6A94A] border-[#E6A94A]/30'
              }`}
            >
              <div className="flex items-center space-x-2">
                <CheckCircle2
                  className={`h-4 w-4 ${bulkResponse.failed_count === 0 ? 'text-[#79E282]' : 'text-[#E6A94A]'}`}
                />
                <span className="font-semibold">
                  Batch Ingest Completed: {bulkResponse.successfully_ingested} of {bulkResponse.total_rows_read} rows processed.
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-xl">
                <div className="text-[11px] text-[var(--text-muted)] font-medium">Total Rows</div>
                <div className="text-lg font-bold text-[var(--text-primary)] font-mono">{bulkResponse.total_rows_read}</div>
              </div>
              <div className="p-3 bg-[#79E282]/10 border border-[#79E282]/20 rounded-xl">
                <div className="text-[11px] text-[#79E282] font-medium">Ingested</div>
                <div className="text-lg font-bold text-[#79E282] font-mono">{bulkResponse.successfully_ingested}</div>
              </div>
              <div className="p-3 bg-[#E6A94A]/10 border border-[#E6A94A]/20 rounded-xl">
                <div className="text-[11px] text-[#E6A94A] font-medium">Exceptions</div>
                <div className="text-lg font-bold text-[#E6A94A] font-mono">{bulkResponse.failed_count}</div>
              </div>
            </div>

            {bulkResponse.errors && bulkResponse.errors.length > 0 && (
              <div className="p-3 bg-[#D95F63]/10 border border-[#D95F63]/30 rounded-xl text-xs text-[#D95F63] space-y-1">
                <div className="font-bold flex items-center mb-1">
                  <AlertCircle className="h-4 w-4 mr-1 inline" />
                  Validation Exceptions ({bulkResponse.errors.length}):
                </div>
                <ul className="list-disc list-inside space-y-0.5 max-h-32 overflow-y-auto font-mono text-[11px]">
                  {bulkResponse.errors.map((err, idx) => (
                    <li key={idx}>
                      Row {err.row_index} ({err.wallet_address || 'empty'}): {err.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleBulkUpload} className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center gap-3">
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
              className="block w-full text-xs text-[var(--text-muted)] file:mr-3 file:py-2 file:px-3.5 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-[var(--bg-secondary)] file:text-[var(--accent-primary)] hover:file:bg-[var(--border-color)] border border-[var(--border-color)] bg-[var(--bg-secondary)] rounded-xl p-2 focus:outline-none cursor-pointer disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={bulkLoading || !selectedFile}
              className="w-full sm:w-auto inline-flex items-center justify-center px-5 py-2.5 rounded-xl text-xs font-bold text-[var(--bg-card)] bg-[var(--accent-primary)] hover:opacity-90 disabled:opacity-50 transition-colors shrink-0 shadow-sm"
            >
              <Upload className="h-3.5 w-3.5 mr-1.5" />
              {bulkLoading ? 'Processing Batch...' : 'Upload & Parse CSV'}
            </button>
          </div>
        </form>
      </div>

      {/* Recent Investigations Dossier List */}
      <div className="bg-[var(--bg-card)] p-6 rounded-2xl shadow-xl border border-[var(--border-color)] transition-colors duration-200">
        <div className="flex justify-between items-center mb-4 pb-3 border-b border-[var(--border-color)]">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-lg bg-[var(--bg-secondary)] text-[var(--accent-primary)]">
              <History className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[var(--text-primary)]">Investigation Case Files</h3>
              <p className="text-xs text-[var(--text-muted)]">{recentCases.length} Registered Incidents</p>
            </div>
          </div>
          <button
            onClick={() => {
              onCaseCreated?.();
              fetchRecentCases();
            }}
            disabled={loadingRecent}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--accent-primary)] flex items-center px-2.5 py-1 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--border-color)] border border-[var(--border-color)] transition-colors"
            title="Refresh list"
          >
            <RefreshCw className={`h-3 w-3 mr-1.5 ${loadingRecent ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {recentCases.length === 0 ? (
          <div className="text-center py-8 text-[var(--text-muted)] text-xs">
            {loadingRecent ? 'Fetching case repository...' : 'No previous investigations found. Initiate your first trace above.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[var(--bg-surface)] text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider border-b border-[var(--border-color)]">
                <tr>
                  <th className="px-4 py-3">Case Reference</th>
                  <th className="px-4 py-3">Chain</th>
                  <th className="px-4 py-3">Reported Wallet</th>
                  <th className="px-4 py-3">State</th>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]">
                {recentCases.slice(0, 10).map((c) => {
                  const isCurrent = c.id === activeCase;
                  const dateStr = c.created_at ? new Date(c.created_at).toLocaleDateString() : 'Recently';
                  return (
                    <tr
                      key={c.id}
                      className={`hover:bg-[var(--bg-surface)] transition-colors ${isCurrent ? 'bg-[#79E282]/5' : ''}`}
                    >
                      <td className="px-4 py-3 font-mono text-[11px] text-[var(--text-muted)]" title={c.id}>
                        {c.id.slice(0, 8)}...
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getChainBadgeStyle(c.chain)}`}>
                          {c.chain.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-[var(--text-primary)]" title={c.reported_address}>
                        {c.reported_address
                          ? c.reported_address.length > 20
                            ? `${c.reported_address.slice(0, 10)}...${c.reported_address.slice(-6)}`
                            : c.reported_address
                          : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            c.status === 'completed'
                              ? 'bg-[#79E282]/10 text-[#79E282] border border-[#79E282]/30'
                              : 'bg-[#E6A94A]/10 text-[#E6A94A] border border-[#E6A94A]/30'
                          }`}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[11px] text-[var(--text-muted)]">{dateStr}</td>
                      <td className="px-4 py-3 text-right">
                        {isCurrent ? (
                          <span className="inline-flex items-center text-[11px] font-bold text-[#79E282] bg-[#79E282]/10 px-2 py-0.5 rounded-md border border-[#79E282]/30">
                            <Check className="h-3 w-3 mr-1" /> Active
                          </span>
                        ) : (
                          <button
                            onClick={() => handleOpenCase(c.id)}
                            className="inline-flex items-center text-[11px] font-medium text-[#79E282] hover:text-[#0B0B0D] bg-[var(--bg-surface)] hover:bg-[#79E282] px-2.5 py-1 rounded-md border border-[var(--border-color)] hover:border-[#79E282] transition-colors"
                          >
                            Open
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
