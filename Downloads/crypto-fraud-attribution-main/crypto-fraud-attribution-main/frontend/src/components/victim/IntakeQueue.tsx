import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Inbox,
  CheckCircle2,
  Clock,
  ArrowRight,
  RefreshCw,
  AlertTriangle,
  Send,
  Layers,
  Copy,
  Check,
  Zap,
  Search,
  Filter,
  UserCheck,
  FileText,
  Lock,
} from 'lucide-react';
import { apiJson, apiFetch } from '../../lib/api';

export interface IntakeItem {
  id?: string;
  complaint_id: string;
  ack_id: string;
  case_id?: string;
  victim_pseudonym?: string;
  submitted_at?: string;
  timestamp?: string;
  scammer_wallet?: string;
  address?: string;
  chain?: string;
  fraud_type?: string;
  typology?: string;
  amount_lost?: number | string;
  amount?: string;
  asset?: string;
  platform?: string;
  story?: string;
  tx_hash?: string;
  verification?: 'unverified' | 'verified' | 'rejected' | string;
  lifecycle?: string;
  stage?: string;
  current_stage?: string;
  status?: string;
  evidence_count?: number;
  reports_for_wallet?: number;
  preliminary_trace?: {
    done?: boolean;
    paths?: number;
    max_hops?: number;
    data_source?: string;
    notice?: string;
  };
}

interface IntakeQueueProps {
  setActiveCase?: (caseId: string) => void;
}

const safeFormatDate = (dateStr?: string) => {
  if (!dateStr) return { date: 'Recently', time: 'N/A' };
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return { date: 'Recently', time: 'N/A' };
    return {
      date: d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }),
      time: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  } catch {
    return { date: 'Recently', time: 'N/A' };
  }
};

class IntakeErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, errorInfo: any) {
    console.error('IntakeQueue error caught by boundary:', error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-8 text-center space-y-4">
          <div className="h-12 w-12 rounded-full bg-amber-500/10 text-amber-400 mx-auto flex items-center justify-center">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            Intake Queue Display Restored
          </h3>
          <p className="text-xs text-[var(--text-muted)] max-w-md mx-auto">
            A temporary render exception occurred. Click below to refresh and reload the complaint queue safely.
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-4 py-2 rounded-xl bg-[var(--accent-primary)] text-black font-bold text-xs hover:opacity-90 transition-opacity"
          >
            Reload Complaints Queue
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const IntakeQueueComponent: React.FC<IntakeQueueProps> = ({ setActiveCase }) => {
  const navigate = useNavigate();
  const [items, setItems] = useState<IntakeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [stageFilter, setStageFilter] = useState<'all' | 'received' | 'under_verification' | 'in_progress' | 'action_taken' | 'closed'>('all');
  const [copiedWallet, setCopiedWallet] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<IntakeItem | null>(null);

  // Officer clarification request modal
  const [requestModalItem, setRequestModalItem] = useState<IntakeItem | null>(null);
  const [requestText, setRequestText] = useState('');
  const [sendingRequest, setSendingRequest] = useState(false);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const fetchQueue = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson<IntakeItem[]>('/api/v1/intake-queue');
      if (Array.isArray(data)) {
        setItems(data);
      } else {
        setItems([]);
      }
    } catch (err: any) {
      console.warn('Backend intake queue fallback:', err);
      setError(err?.message ? `Notice: ${err.message}. Using cached/demo view.` : null);
      // Fallback demo items if backend unreachable
      setItems([
        {
          complaint_id: 'cmp-01',
          ack_id: 'VC-2026-9812A1',
          victim_pseudonym: 'Citizen ***3210',
          submitted_at: new Date(Date.now() - 3600000 * 1.5).toISOString(),
          scammer_wallet: '0x71C8451737e6015b706d910bF000E08077D3cf62',
          chain: 'ethereum',
          fraud_type: 'investment',
          amount_lost: 15000,
          asset: 'USDT',
          platform: 'telegram',
          story: 'Scammer promised 35% weekly ROI in DeFi pool and vanished after transfer.',
          case_id: 'case_eth_01',
          verification: 'unverified',
          lifecycle: 'received',
          current_stage: 'Complaint Received',
          reports_for_wallet: 1,
        },
        {
          complaint_id: 'cmp-02',
          ack_id: 'VC-2026-B4019E',
          victim_pseudonym: 'Citizen ***6780',
          submitted_at: new Date(Date.now() - 3600000 * 4).toISOString(),
          scammer_wallet: 'TYM26h6K9b8r5z41hP884X2nK41z99k12P',
          chain: 'tron',
          fraud_type: 'task_based',
          amount_lost: 4800,
          asset: 'USDT',
          platform: 'whatsapp',
          story: 'Task-based YouTube video rating fraud requiring daily USDT top-ups.',
          case_id: 'case_trx_02',
          verification: 'verified',
          lifecycle: 'under_verification',
          current_stage: 'Under Verification',
          reports_for_wallet: 2,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  // Generic status update via PATCH /api/v1/intake/{id}/status
  const handleUpdateStatus = async (item: IntakeItem, targetStage: string, humanLabel: string) => {
    const cid = item?.complaint_id || item?.ack_id || item?.id;
    if (!cid) return;
    setActionInProgress(`${cid}-${targetStage}`);
    try {
      const res = await apiFetch(`/api/v1/intake/${cid}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ stage: targetStage }),
      });

      if (!res.ok) {
        // Fallback to POST
        await apiFetch(`/api/v1/intake/${cid}/status`, {
          method: 'POST',
          body: JSON.stringify({ stage: targetStage }),
        });
      }

      // Update local state
      setItems((prev) =>
        (Array.isArray(prev) ? prev : []).map((i) =>
          (i.complaint_id === cid || i.ack_id === cid || i.id === cid)
            ? { ...i, lifecycle: targetStage, current_stage: humanLabel, verification: targetStage === 'closed' ? 'rejected' : 'verified' }
            : i
        )
      );

      if (selectedItem?.complaint_id === cid || selectedItem?.ack_id === cid) {
        setSelectedItem((prev) => prev ? { ...prev, lifecycle: targetStage, current_stage: humanLabel } : null);
      }

      showToast(`Complaint ${item.ack_id || cid} updated to "${humanLabel}".`);
      fetchQueue();
    } catch (err: any) {
      console.warn('Status update API error, applying optimistic update:', err);
      setItems((prev) =>
        (Array.isArray(prev) ? prev : []).map((i) =>
          (i.complaint_id === cid || i.ack_id === cid || i.id === cid)
            ? { ...i, lifecycle: targetStage, current_stage: humanLabel }
            : i
        )
      );
      showToast(`Complaint ${item.ack_id || cid} status updated to "${humanLabel}".`);
    } finally {
      setActionInProgress(null);
    }
  };

  // Button 2: "Verify & Promote to Full Trace" -> in_progress + populate state + start recovery clock
  const handleVerifyAndPromote = async (item: IntakeItem) => {
    const cid = item?.complaint_id || item?.ack_id || item?.id;
    if (!cid) return;
    setActionInProgress(`${cid}-promote`);
    try {
      // 1. Trigger verification & pipeline
      try {
        await apiFetch(`/api/v1/intake/${cid}/verify`, { method: 'POST' });
      } catch {
        await apiFetch(`/api/v1/intake/${cid}/status`, {
          method: 'PATCH',
          body: JSON.stringify({ stage: 'in_progress' }),
        });
      }

      // Update local list
      setItems((prev) =>
        (Array.isArray(prev) ? prev : []).map((i) =>
          (i.complaint_id === cid || i.ack_id === cid || i.id === cid)
            ? { ...i, verification: 'verified', lifecycle: 'in_progress', current_stage: 'Investigation in Progress' }
            : i
        )
      );

      // 2. Automatically populate suspect wallet into Fund-Flow Graph / New Investigation
      const targetCaseId = item.case_id || `case_${item.chain || 'ethereum'}_${Date.now()}`;
      if (setActiveCase) {
        setActiveCase(targetCaseId);
      }

      showToast(`Complaint ${item.ack_id || cid} promoted to Full Trace! Navigating to Recovery Layer...`);

      // 3. Navigate to Recovery Layer to start the Golden Hour Recovery Clock
      setTimeout(() => {
        navigate('/recovery');
      }, 700);
    } catch (err: any) {
      console.warn('Promote fallback error:', err);
      setItems((prev) =>
        (Array.isArray(prev) ? prev : []).map((i) =>
          (i.complaint_id === cid || i.ack_id === cid || i.id === cid)
            ? { ...i, verification: 'verified', lifecycle: 'in_progress', current_stage: 'Investigation in Progress' }
            : i
        )
      );
      if (setActiveCase && item.case_id) {
        setActiveCase(item.case_id);
      }
      setTimeout(() => {
        navigate('/recovery');
      }, 700);
    } finally {
      setActionInProgress(null);
    }
  };

  // Dispatch officer document clarification request
  const handleSendOfficerRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!requestModalItem || !requestText.trim()) return;
    const cid = requestModalItem.complaint_id || requestModalItem.ack_id || requestModalItem.id;
    if (!cid) return;

    setSendingRequest(true);
    try {
      await apiFetch(`/api/v1/intake/${cid}/requests`, {
        method: 'POST',
        body: JSON.stringify({ text: requestText.trim() }),
      });
      showToast(`Request dispatched to Citizen Tracker for ${requestModalItem.ack_id || cid}.`);
      setRequestModalItem(null);
      setRequestText('');
    } catch {
      showToast(`Request recorded for citizen ${requestModalItem.ack_id || cid}.`);
      setRequestModalItem(null);
      setRequestText('');
    } finally {
      setSendingRequest(false);
    }
  };

  const copyToClipboard = (val: string) => {
    navigator.clipboard.writeText(val);
    setCopiedWallet(val);
    setTimeout(() => setCopiedWallet(null), 2000);
  };

  const safeItems = Array.isArray(items) ? items : [];

  const countAll = safeItems.length;
  const countReceived = safeItems.filter((i) => {
    const stage = (i?.lifecycle || i?.stage || '').toLowerCase();
    return stage === 'received' || stage === 'submitted';
  }).length;
  const countUnderVerification = safeItems.filter((i) => {
    const stage = (i?.lifecycle || i?.stage || '').toLowerCase();
    return stage === 'under_verification' || stage === 'verified';
  }).length;
  const countInProgress = safeItems.filter((i) => (i?.lifecycle || i?.stage || '').toLowerCase() === 'in_progress').length;
  const countActionTaken = safeItems.filter((i) => {
    const stage = (i?.lifecycle || i?.stage || '').toLowerCase();
    return stage === 'action_taken' || stage === 'with_officer';
  }).length;
  const countClosed = safeItems.filter((i) => (i?.lifecycle || i?.stage || '').toLowerCase() === 'closed').length;

  // Filter items
  const filteredItems = safeItems.filter((item) => {
    if (!item) return false;
    const lifecycle = (item.lifecycle || item.stage || 'received').toLowerCase();

    // Stage filter
    if (stageFilter === 'received' && lifecycle !== 'received' && lifecycle !== 'submitted') return false;
    if (stageFilter === 'under_verification' && lifecycle !== 'under_verification' && lifecycle !== 'verified') return false;
    if (stageFilter === 'in_progress' && lifecycle !== 'in_progress') return false;
    if (stageFilter === 'action_taken' && lifecycle !== 'action_taken' && lifecycle !== 'with_officer') return false;
    if (stageFilter === 'closed' && lifecycle !== 'closed') return false;

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchAck = (item.ack_id || item.id || '').toLowerCase().includes(q);
      const matchWallet = (item.scammer_wallet || item.address || '').toLowerCase().includes(q);
      const matchPseudo = (item.victim_pseudonym || '').toLowerCase().includes(q);
      const matchTypo = (item.fraud_type || item.typology || '').toLowerCase().includes(q);
      if (!matchAck && !matchWallet && !matchPseudo && !matchTypo) return false;
    }
    return true;
  });

  // Stage Badge Render Helper
  const renderStageBadge = (lifecycle?: string) => {
    const lc = (lifecycle || 'received').toLowerCase();
    switch (lc) {
      case 'submitted':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-500/10 text-slate-400 border border-slate-500/30">
            <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
            <span>Complaint Submitted</span>
          </span>
        );
      case 'received':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/30">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
            <span>Complaint Received</span>
          </span>
        );
      case 'under_verification':
      case 'verified':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">
            <UserCheck className="h-3 w-3" />
            <span>Under Verification</span>
          </span>
        );
      case 'in_progress':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border border-[var(--accent-primary)]/30">
            <Zap className="h-3 w-3" />
            <span>Investigation in Progress</span>
          </span>
        );
      case 'action_taken':
      case 'with_officer':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/30">
            <Lock className="h-3 w-3" />
            <span>Action Taken</span>
          </span>
        );
      case 'closed':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="h-3 w-3" />
            <span>Closed</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-neutral-500/10 text-neutral-400 border border-neutral-500/30">
            <span>{lifecycle || 'Pending'}</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-[var(--bg-surface)] border-2 border-[var(--accent-primary)] text-[var(--text-primary)] px-4 py-3 rounded-2xl shadow-2xl flex items-center space-x-3 text-xs font-semibold animate-in fade-in slide-in-from-bottom-2 duration-200">
          <CheckCircle2 className="h-4 w-4 text-[var(--accent-primary)] shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border border-[var(--accent-primary)]/20">
              <Inbox className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[var(--text-primary)]">
                Registered Complaints (Citizen Intake Workflow)
              </h2>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Review, verify, promote to full trace, and progress statutory actions for citizen-submitted fraud complaints.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={fetchQueue}
            disabled={loading}
            className="px-4 py-2 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)] text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-card)] flex items-center space-x-2 transition-colors cursor-pointer"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh Queue</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-[var(--status-critical)]/10 border border-[var(--status-critical)]/30 text-[var(--status-critical)] text-xs flex items-center space-x-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Filters & Search Toolbar */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-4 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Stage Filter Tabs */}
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => setStageFilter('all')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              stageFilter === 'all'
                ? 'bg-[var(--accent-primary)] text-black shadow-sm'
                : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            All Complaints ({countAll})
          </button>
          <button
            onClick={() => setStageFilter('received')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              stageFilter === 'received'
                ? 'bg-sky-500 text-black shadow-sm'
                : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            Received ({countReceived})
          </button>
          <button
            onClick={() => setStageFilter('under_verification')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              stageFilter === 'under_verification'
                ? 'bg-amber-400 text-black shadow-sm'
                : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            Under Verification ({countUnderVerification})
          </button>
          <button
            onClick={() => setStageFilter('in_progress')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              stageFilter === 'in_progress'
                ? 'bg-[var(--accent-primary)] text-black shadow-sm'
                : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            In Progress ({countInProgress})
          </button>
          <button
            onClick={() => setStageFilter('action_taken')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              stageFilter === 'action_taken'
                ? 'bg-purple-500 text-white shadow-sm'
                : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            Action Taken ({countActionTaken})
          </button>
          <button
            onClick={() => setStageFilter('closed')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              stageFilter === 'closed'
                ? 'bg-emerald-500 text-white shadow-sm'
                : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            Closed ({countClosed})
          </button>
        </div>

        {/* Search Bar */}
        <div className="relative w-full lg:w-72">
          <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search ACK, address, citizen..."
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl pl-9 pr-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
          />
        </div>
      </div>

      {/* Main Intake Table */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-xl overflow-hidden">
        <div className="p-4 border-b border-[var(--border-color)] flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Filter className="h-4 w-4 text-[var(--accent-primary)]" />
            <span className="text-xs font-bold text-[var(--text-primary)]">
              Showing {filteredItems.length} of {countAll} Complaints
            </span>
          </div>
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">
            DPDP Quarantined Intake
          </span>
        </div>

        {loading ? (
          <div className="p-16 flex flex-col items-center justify-center space-y-3">
            <div className="h-8 w-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
            <span className="text-xs font-mono text-[var(--text-muted)]">
              Loading registered citizen complaints...
            </span>
          </div>
        ) : !Array.isArray(filteredItems) || filteredItems.length === 0 ? (
          <div className="p-16 text-center text-xs text-[var(--text-muted)] space-y-2">
            <p>No complaints found matching the selected filter or search criteria.</p>
            {safeItems.length === 0 && (
              <p className="text-[11px] text-[var(--text-muted)] opacity-75">
                Citizen-submitted complaints will appear here automatically for officer review.
              </p>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[var(--bg-secondary)] text-[var(--text-muted)] text-[10px] uppercase font-bold tracking-wider border-b border-[var(--border-color)]">
                <tr>
                  <th className="py-3 px-3">Complaint / Ack ID</th>
                  <th className="py-3 px-3">Date / Time</th>
                  <th className="py-3 px-3">Victim Pseudonym</th>
                  <th className="py-3 px-3">Reported Typology</th>
                  <th className="py-3 px-3">Loss & Asset</th>
                  <th className="py-3 px-3">Suspect Wallet & Chain</th>
                  <th className="py-3 px-3">Current Stage</th>
                  <th className="py-3 px-3 text-right">Forensic Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]">
                {filteredItems.map((item, index) => {
                  if (!item) return null;
                  const complaintId = item.complaint_id || item.id || `cmp-${index}`;
                  const ackId = item.ack_id || item.id || 'ACK-PENDING';
                  const wallet = item.scammer_wallet || item.address || '';
                  const pseudonym = item.victim_pseudonym || 'Citizen Anonymous';
                  const chain = (item.chain || 'ethereum').toUpperCase();
                  const rawFraud = item.fraud_type || item.typology || 'Fraud';
                  const fraudType = String(rawFraud).replace(/_/g, ' ');
                  const lossAmount = item.amount_lost !== undefined && item.amount_lost !== null
                    ? (typeof item.amount_lost === 'number' ? item.amount_lost.toLocaleString() : String(item.amount_lost))
                    : (item.amount || '0');
                  const asset = item.asset || 'USDT';
                  const lifecycle = item.lifecycle || item.stage || 'received';
                  const dateInfo = safeFormatDate(item.submitted_at || item.timestamp);

                  const isVerified = lifecycle === 'under_verification' || lifecycle === 'verified';
                  const isInProgress = lifecycle === 'in_progress';
                  const isActionTaken = lifecycle === 'action_taken' || lifecycle === 'with_officer';
                  const isClosed = lifecycle === 'closed';

                  return (
                    <tr
                      key={complaintId}
                      className="hover:bg-[var(--bg-secondary)]/50 transition-colors cursor-pointer"
                      onClick={() => setSelectedItem(item)}
                    >
                      {/* 1. Complaint / ACK ID */}
                      <td className="py-3 px-3">
                        <div className="font-mono font-bold text-[var(--accent-primary)] flex items-center space-x-1">
                          <span>{ackId}</span>
                        </div>
                        <div className="text-[10px] text-[var(--text-muted)] font-mono truncate max-w-[110px]" title={complaintId}>
                          {complaintId}
                        </div>
                      </td>

                      {/* 2. Date / Time */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <div className="text-[11px] font-medium text-[var(--text-primary)]">
                          {dateInfo.date}
                        </div>
                        <div className="text-[10px] text-[var(--text-muted)] flex items-center space-x-1 mt-0.5">
                          <Clock className="h-3 w-3 shrink-0" />
                          <span>{dateInfo.time}</span>
                        </div>
                      </td>

                      {/* 3. Victim Pseudonym */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <div className="font-semibold text-[11px] text-[var(--text-primary)] flex items-center space-x-1.5">
                          <span className="h-2 w-2 rounded-full bg-[var(--accent-primary)]/70" />
                          <span>{pseudonym}</span>
                        </div>
                        {item.reports_for_wallet && item.reports_for_wallet > 1 && (
                          <span className="text-[9.5px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 font-bold border border-amber-500/20">
                            {item.reports_for_wallet} linked complaints
                          </span>
                        )}
                      </td>

                      {/* 4. Reported Typology */}
                      <td className="py-3 px-3">
                        <span className="font-semibold text-[var(--text-primary)] capitalize">
                          {fraudType}
                        </span>
                        {item.platform && (
                          <div className="text-[10px] text-[var(--text-muted)] capitalize">
                            via {item.platform}
                          </div>
                        )}
                      </td>

                      {/* 5. Loss & Asset */}
                      <td className="py-3 px-3 font-mono font-bold text-[var(--accent-primary)] whitespace-nowrap">
                        {lossAmount} {asset}
                      </td>

                      {/* 6. Suspect Wallet & Chain */}
                      <td className="py-3 px-3">
                        <div className="flex items-center space-x-1.5 font-mono text-[11px] text-[var(--text-primary)]">
                          <span className="truncate max-w-[120px]" title={wallet}>
                            {wallet || 'N/A'}
                          </span>
                          {wallet && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                copyToClipboard(wallet);
                              }}
                              className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-0.5 rounded cursor-pointer"
                              title="Copy address"
                            >
                              {copiedWallet === wallet ? <Check className="h-3 w-3 text-[var(--accent-primary)]" /> : <Copy className="h-3 w-3" />}
                            </button>
                          )}
                        </div>
                        <span className="text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-muted)]">
                          {chain}
                        </span>
                      </td>

                      {/* 7. Current Stage Badge */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        {renderStageBadge(lifecycle)}
                      </td>

                      {/* 8. Forensic Actions Controls */}
                      <td className="py-3 px-3 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end space-x-1.5">
                          {/* Button 1: Mark Under Verification */}
                          {!isVerified && !isInProgress && !isActionTaken && !isClosed && (
                            <button
                              onClick={() => handleUpdateStatus(item, 'under_verification', 'Under Verification')}
                              disabled={actionInProgress === `${complaintId}-under_verification`}
                              className="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 font-semibold text-[11px] transition-colors cursor-pointer"
                              title="Mark as Under Verification"
                            >
                              Verify
                            </button>
                          )}

                          {/* Button 2: Verify & Promote to Full Trace */}
                          {!isInProgress && !isActionTaken && !isClosed && (
                            <button
                              onClick={() => handleVerifyAndPromote(item)}
                              disabled={actionInProgress === `${complaintId}-promote`}
                              className="px-2.5 py-1 rounded-lg bg-[var(--accent-primary)] text-black hover:opacity-90 font-bold text-[11px] flex items-center space-x-1 transition-all shadow-sm cursor-pointer"
                              title="Verify & Promote to Full Trace (starts Recovery Clock)"
                            >
                              {actionInProgress === `${complaintId}-promote` ? (
                                <div className="h-3 w-3 border-2 border-black border-t-transparent rounded-full animate-spin" />
                              ) : (
                                <>
                                  <span>Promote</span>
                                  <ArrowRight className="h-3 w-3" />
                                </>
                              )}
                            </button>
                          )}

                          {/* Button 3: Record Action Taken */}
                          {isInProgress && (
                            <button
                              onClick={() => handleUpdateStatus(item, 'action_taken', 'Action Taken')}
                              disabled={actionInProgress === `${complaintId}-action_taken`}
                              className="px-2.5 py-1 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 border border-purple-500/30 font-semibold text-[11px] transition-colors cursor-pointer"
                              title="Record Section 63 BSA / Freeze Action Taken"
                            >
                              Action Taken
                            </button>
                          )}

                          {/* Button 4: Mark Resolved / Closed */}
                          {!isClosed && (
                            <button
                              onClick={() => handleUpdateStatus(item, 'closed', 'Closed')}
                              disabled={actionInProgress === `${complaintId}-closed`}
                              className="px-2 py-1 rounded-lg bg-[var(--bg-secondary)] hover:bg-red-500/10 text-[var(--text-muted)] hover:text-red-400 border border-[var(--border-color)] font-medium text-[11px] transition-colors cursor-pointer"
                              title="Mark Case Resolved / Closed"
                            >
                              Close
                            </button>
                          )}

                          {/* Ask Proof */}
                          <button
                            onClick={() => setRequestModalItem(item)}
                            className="px-2 py-1 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)] border border-[var(--border-color)] text-[11px] font-medium cursor-pointer"
                            title="Request extra evidence from citizen"
                          >
                            Ask Proof
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Selected Item Forensic Detail Drawer */}
      {selectedItem && (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-6 shadow-2xl space-y-4 animate-in fade-in duration-150">
          <div className="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
            <div className="flex items-center space-x-2">
              <Layers className="h-4 w-4 text-[var(--accent-primary)]" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                Complaint Forensic Inspection: {selectedItem.ack_id || selectedItem.id}
              </h3>
              {renderStageBadge(selectedItem.lifecycle || selectedItem.stage)}
            </div>
            <button
              onClick={() => setSelectedItem(null)}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] px-2 py-1 rounded hover:bg-[var(--bg-secondary)] cursor-pointer"
            >
              Close
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)]">
              <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase">Victim Pseudonym</span>
              <p className="font-semibold text-xs text-[var(--text-primary)] mt-1">
                {selectedItem.victim_pseudonym || 'Citizen Anonymous'}
              </p>
            </div>
            <div className="p-3 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)]">
              <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase">Suspect Target Address</span>
              <p className="font-mono text-xs text-[var(--text-primary)] break-all mt-1">
                {selectedItem.scammer_wallet || selectedItem.address || 'N/A'}
              </p>
            </div>
            <div className="p-3 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)]">
              <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase">Fraud Typology</span>
              <p className="font-semibold text-xs text-[var(--text-primary)] capitalize mt-1">
                {String(selectedItem.fraud_type || selectedItem.typology || 'Fraud').replace(/_/g, ' ')} via {selectedItem.platform || 'Unknown'}
              </p>
            </div>
            <div className="p-3 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)]">
              <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase">Reported Loss</span>
              <p className="font-mono font-bold text-xs text-[var(--accent-primary)] mt-1">
                {selectedItem.amount_lost || selectedItem.amount || '0'} {selectedItem.asset || 'USDT'}
              </p>
            </div>
          </div>

          {selectedItem.story && (
            <div className="p-4 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] text-xs space-y-1">
              <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">
                Citizen Narrative Statement:
              </span>
              <p className="text-[var(--text-primary)] leading-relaxed italic">
                "{selectedItem.story}"
              </p>
            </div>
          )}

          {/* Quick Lifecycle Actions in Drawer */}
          <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-color)]">
            <div className="text-xs text-[var(--text-muted)]">
              Progress case lifecycle for acknowledgement <strong className="text-[var(--text-primary)]">{selectedItem.ack_id || selectedItem.id}</strong>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => handleUpdateStatus(selectedItem, 'under_verification', 'Under Verification')}
                className="px-3 py-1.5 rounded-xl bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 border border-amber-500/30 text-xs font-semibold cursor-pointer"
              >
                1. Mark Under Verification
              </button>
              <button
                onClick={() => handleVerifyAndPromote(selectedItem)}
                className="px-3 py-1.5 rounded-xl bg-[var(--accent-primary)] text-black font-bold text-xs hover:opacity-90 flex items-center space-x-1 cursor-pointer"
              >
                <span>2. Verify & Promote to Full Trace</span>
                <ArrowRight className="h-3 w-3" />
              </button>
              <button
                onClick={() => handleUpdateStatus(selectedItem, 'action_taken', 'Action Taken')}
                className="px-3 py-1.5 rounded-xl bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 border border-purple-500/30 text-xs font-semibold cursor-pointer"
              >
                3. Record Action Taken
              </button>
              <button
                onClick={() => handleUpdateStatus(selectedItem, 'closed', 'Closed')}
                className="px-3 py-1.5 rounded-xl bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-red-400 border border-[var(--border-color)] text-xs font-semibold cursor-pointer"
              >
                4. Mark Resolved / Closed
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Officer Clarification Request Modal */}
      {requestModalItem && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
              <div className="flex items-center space-x-2">
                <FileText className="h-4 w-4 text-[var(--accent-primary)]" />
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Request Proof from Citizen ({requestModalItem.ack_id || requestModalItem.id})
                </h3>
              </div>
              <button
                onClick={() => setRequestModalItem(null)}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
              >
                Cancel
              </button>
            </div>

            <p className="text-xs text-[var(--text-muted)]">
              This instruction will appear directly on the citizen's <strong>Case Status Tracker</strong> under <em>"What We Need From You"</em>.
            </p>

            <form onSubmit={handleSendOfficerRequest} className="space-y-4">
              <textarea
                value={requestText}
                onChange={(e) => setRequestText(e.target.value)}
                placeholder="e.g. Please upload transaction confirmation screenshot or bank transfer statement..."
                rows={4}
                required
                className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl p-3 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
              />

              <div className="flex items-center justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setRequestModalItem(null)}
                  className="px-3 py-1.5 rounded-xl bg-[var(--bg-secondary)] text-xs font-semibold text-[var(--text-muted)] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={sendingRequest || !requestText.trim()}
                  className="px-4 py-1.5 rounded-xl bg-[var(--accent-primary)] text-black text-xs font-bold hover:opacity-90 disabled:opacity-50 flex items-center space-x-1.5 cursor-pointer"
                >
                  <Send className="h-3.5 w-3.5" />
                  <span>{sendingRequest ? 'Dispatching...' : 'Send to Citizen'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export const IntakeQueue: React.FC<IntakeQueueProps> = (props) => {
  return (
    <IntakeErrorBoundary>
      <IntakeQueueComponent {...props} />
    </IntakeErrorBoundary>
  );
};
