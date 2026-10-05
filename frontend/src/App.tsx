import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Activity, ShieldAlert, FileText, Share2, Search, LogOut, Clock, FolderOpen } from 'lucide-react';
import { supabase } from './lib/supabase';
import { apiJson } from './lib/api';
import type { Session } from '@supabase/supabase-js';

import Login from './components/Login';
import NewInvestigation from './components/NewInvestigation';
import FundFlowGraph from './components/FundFlowGraph';
import RiskAttribution from './components/RiskAttribution';
import RecoveryLayer from './components/RecoveryLayer';
import MonitoringAlerts from './components/MonitoringAlerts';
import EvidenceReport from './components/EvidenceReport';

export interface CaseSummary {
  id: string;
  case_id?: string;
  complaint_ref?: string;
  chain: string;
  reported_address: string;
  reported_amount?: number;
  asset?: string;
  status: string;
  created_at?: string;
  risk?: { score: number; category: string };
}

const STORAGE_KEY = 'crypto_fraud_active_case';

function Dashboard({ session }: { session: Session }) {
  const [activeCase, setActiveCase] = useState<string | null>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || null;
    } catch {
      return null;
    }
  });
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loadingCases, setLoadingCases] = useState(false);
  const [dataSource, setDataSource] = useState<string | null>(null);

  // Fetch recent cases and auto-restore the active case if needed
  const refreshCases = async () => {
    setLoadingCases(true);
    try {
      const list = await apiJson<CaseSummary[]>('/api/v1/cases?limit=30');
      if (Array.isArray(list) && list.length > 0) {
        setCases(list);
        const stored = localStorage.getItem(STORAGE_KEY);
        const hasStored = stored && list.some((c) => c.id === stored);
        if (hasStored && stored) {
          setActiveCase(stored);
        } else {
          // If no valid stored case exists, select the most recent completed case or the newest case
          const mostRecent = list.find((c) => c.status === 'completed') || list[0];
          if (mostRecent) {
            setActiveCase(mostRecent.id);
            try {
              localStorage.setItem(STORAGE_KEY, mostRecent.id);
            } catch {}
          }
        }
      }
    } catch (err) {
      console.warn('Could not load case list:', err);
    } finally {
      setLoadingCases(false);
    }
  };

  useEffect(() => {
    refreshCases();
  }, []);

  // Synchronize localStorage whenever activeCase changes
  useEffect(() => {
    if (activeCase) {
      try {
        localStorage.setItem(STORAGE_KEY, activeCase);
      } catch {}
    }
  }, [activeCase]);

  // Look up where the active case's data came from so mock data is always labelled
  useEffect(() => {
    setDataSource(null);
    if (!activeCase) return;
    const load = () =>
      apiJson(`/api/investigations/${activeCase}`)
        .then((c) => setDataSource(c.data_source ?? null))
        .catch(() => setDataSource(null));
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [activeCase]);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h1 className="text-xl font-bold text-gray-800 flex items-center">
            <ShieldAlert className="mr-2 text-indigo-600" />
            CryptoFraud
          </h1>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <Link to="/" className="flex items-center p-2 text-gray-700 hover:bg-indigo-50 hover:text-indigo-700 rounded-md">
            <Search className="mr-3 h-5 w-5" />
            New Investigation
          </Link>
          <Link to="/graph" className="flex items-center p-2 text-gray-700 hover:bg-indigo-50 hover:text-indigo-700 rounded-md">
            <Share2 className="mr-3 h-5 w-5" />
            Fund-Flow Graph
          </Link>
          <Link to="/risk" className="flex items-center p-2 text-gray-700 hover:bg-indigo-50 hover:text-indigo-700 rounded-md">
            <ShieldAlert className="mr-3 h-5 w-5" />
            Risk & Attribution
          </Link>
          <Link to="/recovery" className="flex items-center p-2 text-gray-700 hover:bg-indigo-50 hover:text-indigo-700 rounded-md">
            <Clock className="mr-3 h-5 w-5" />
            Recovery Layer
          </Link>
          <Link to="/alerts" className="flex items-center p-2 text-gray-700 hover:bg-indigo-50 hover:text-indigo-700 rounded-md">
            <Activity className="mr-3 h-5 w-5" />
            Monitoring
          </Link>
          <Link to="/report" className="flex items-center p-2 text-gray-700 hover:bg-indigo-50 hover:text-indigo-700 rounded-md">
            <FileText className="mr-3 h-5 w-5" />
            Evidence Report
          </Link>
        </nav>
        
        <div className="p-4 border-t border-gray-200">
          <button 
            onClick={() => supabase.auth.signOut()}
            className="flex items-center w-full p-2 text-gray-600 hover:bg-red-50 hover:text-red-600 rounded-md transition-colors"
          >
            <LogOut className="mr-3 h-5 w-5" />
            Sign Out
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b border-gray-200 p-4 flex justify-between items-center">
          <h2 className="text-lg font-medium text-gray-800">Investigator Dashboard</h2>
          <div className="flex items-center space-x-4">
            {/* Case Selector Dropdown */}
            <div className="flex items-center space-x-2">
              <label htmlFor="case-select" className="text-xs font-medium text-gray-500 flex items-center">
                <FolderOpen className="h-3.5 w-3.5 mr-1 text-indigo-600" />
                Active Case:
              </label>
              {cases.length > 0 ? (
                <select
                  id="case-select"
                  value={activeCase || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val) setActiveCase(val);
                  }}
                  className="bg-white border border-gray-300 text-gray-800 text-xs rounded-md px-2.5 py-1.5 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 shadow-sm max-w-[280px] truncate font-mono"
                  title="Switch active investigation"
                >
                  {!activeCase && <option value="">Select an investigation...</option>}
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      [{c.chain.slice(0, 3).toUpperCase()}] {c.reported_address ? `${c.reported_address.slice(0, 6)}...${c.reported_address.slice(-4)}` : c.id.slice(0, 8)} ({c.status})
                    </option>
                  ))}
                </select>
              ) : (
                <div className="text-xs text-gray-500 italic">
                  {loadingCases ? 'Loading cases...' : activeCase ? `${activeCase.slice(0, 8)}...` : 'No active case'}
                </div>
              )}
            </div>
            <div className="text-sm font-medium text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full">
              {session.user.email}
            </div>
          </div>
        </header>

        {/* Standing Safe-Handling Advisory Banner */}
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 flex items-center justify-between text-xs text-amber-900">
          <div className="flex items-center space-x-2">
            <span className="font-semibold px-1.5 py-0.5 bg-amber-500 text-white rounded text-[10px] tracking-wide uppercase">Advisory</span>
            <span>
              Official recovery processes <strong>never</strong> ask for private keys, seed phrases, OTPs, or upfront fees. Unsolicited "recovery agents" are scammers.
            </span>
          </div>
          <span className="text-amber-700 font-medium hidden md:inline">Golden Hour SOP</span>
        </div>

        {dataSource === 'mock' && (
          <div className="bg-yellow-100 border-b border-yellow-300 text-yellow-900 text-sm px-4 py-2">
            <strong>DEMO DATA:</strong> this case uses built-in mock transactions, not live blockchain data.
            Addresses, exchange labels and amounts are fake.
          </div>
        )}
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route
              path="/"
              element={
                <NewInvestigation
                  setActiveCase={setActiveCase}
                  activeCase={activeCase}
                  cases={cases}
                  onCaseCreated={refreshCases}
                />
              }
            />
            <Route path="/graph" element={<FundFlowGraph activeCase={activeCase} />} />
            <Route path="/risk" element={<RiskAttribution activeCase={activeCase} />} />
            <Route path="/recovery" element={<RecoveryLayer activeCase={activeCase} />} />
            <Route path="/alerts" element={<MonitoringAlerts activeCase={activeCase} />} />
            <Route path="/report" element={<EvidenceReport activeCase={activeCase} />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  if (loading) {
    return <div className="h-screen flex items-center justify-center bg-gray-50">Loading application...</div>;
  }

  if (!session) {
    return <Login />;
  }

  return (
    <Router>
      <Dashboard session={session} />
    </Router>
  );
}

export default App;
