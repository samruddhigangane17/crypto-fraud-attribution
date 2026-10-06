import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  Activity,
  ShieldAlert,
  FileText,
  Share2,
  Search,
  LogOut,
  Clock,
  FolderOpen,
  Sun,
  Moon,
  Sparkles,
} from 'lucide-react';
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
import CryptoTracerLogo from './components/CryptoTracerLogo';
import Floating3DCoins from './components/Floating3DCoins';

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
const THEME_KEY = 'cryptotracer_theme';

function Dashboard({ session }: { session: Session }) {
  const location = useLocation();

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

  // Active chain selection shared with 3D coins hero
  const [selectedChain, setSelectedChain] = useState<'ethereum' | 'tron' | 'bitcoin' | 'bsc'>('ethereum');
  const [showHeroCoins, setShowHeroCoins] = useState(true);

  // Light / Dark Theme State
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try {
      return (localStorage.getItem(THEME_KEY) as 'dark' | 'light') || 'dark';
    } catch {
      return 'dark';
    }
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {}
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  // Fetch recent cases and auto-restore active case
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

  useEffect(() => {
    if (activeCase) {
      try {
        localStorage.setItem(STORAGE_KEY, activeCase);
      } catch {}
    }
  }, [activeCase]);

  // Look up data source to label demo/mock data
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

  const navLinks = [
    { path: '/', label: 'New Investigation', icon: Search },
    { path: '/graph', label: 'Fund-Flow Graph', icon: Share2 },
    { path: '/risk', label: 'Risk & Attribution', icon: ShieldAlert },
    { path: '/recovery', label: 'Recovery Layer', icon: Clock },
    { path: '/alerts', label: 'Monitoring Alerts', icon: Activity },
    { path: '/report', label: 'Evidence Report', icon: FileText },
  ];

  const handleSelectChainFromCoins = (chain: 'ethereum' | 'tron' | 'bitcoin' | 'bsc') => {
    setSelectedChain(chain);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg-main)] text-[var(--text-primary)]">
      {/* Sidebar */}
      <aside className="w-64 bg-[var(--bg-card)] border-r border-[var(--border-color)] flex flex-col transition-colors duration-200">
        <div className="p-4 border-b border-[var(--border-color)]">
          <CryptoTracerLogo />
        </div>

        <nav className="flex-1 p-3 space-y-1.5 overflow-y-auto">
          {navLinks.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;

            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-[#182124] text-[#79E282] border-l-4 border-[#79E282] shadow-sm font-semibold'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)]'
                }`}
              >
                <Icon className={`mr-3 h-4 w-4 ${isActive ? 'text-[#79E282]' : 'text-[var(--text-muted)]'}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Sidebar Footer with Sign Out */}
        <div className="p-3 border-t border-[var(--border-color)] space-y-2">
          <button
            onClick={() => supabase.auth.signOut()}
            className="flex items-center w-full px-3 py-2 text-xs font-medium text-[var(--text-muted)] hover:text-[#D95F63] hover:bg-[#D95F63]/10 rounded-lg transition-colors"
          >
            <LogOut className="mr-2.5 h-4 w-4" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Navbar */}
        <header className="bg-[var(--bg-card)] border-b border-[var(--border-color)] px-6 py-3.5 flex justify-between items-center transition-colors duration-200">
          <div className="flex items-center space-x-3">
            <h2 className="text-base font-bold tracking-tight text-[var(--text-primary)]">
              Investigator Intelligence Console
            </h2>
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-[#79E282]/10 text-[#79E282] border border-[#79E282]/30">
              v2.1 Real-Time
            </span>
          </div>

          <div className="flex items-center space-x-4">
            {/* Active Case Selector */}
            <div className="flex items-center space-x-2">
              <label htmlFor="case-select" className="text-xs font-medium text-[var(--text-muted)] flex items-center">
                <FolderOpen className="h-3.5 w-3.5 mr-1.5 text-[#79E282]" />
                Active Dossier:
              </label>
              {cases.length > 0 ? (
                <select
                  id="case-select"
                  value={activeCase || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val) setActiveCase(val);
                  }}
                  className="bg-[var(--bg-surface)] border border-[var(--border-color)] text-[var(--text-primary)] text-xs rounded-lg px-2.5 py-1.5 focus:ring-2 focus:ring-[#79E282] focus:border-[#79E282] shadow-sm max-w-[270px] truncate font-mono"
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
                <div className="text-xs text-[var(--text-muted)] italic">
                  {loadingCases ? 'Loading...' : activeCase ? `${activeCase.slice(0, 8)}...` : 'None'}
                </div>
              )}
            </div>

            {/* 3D Hero Toggle Button */}
            <button
              onClick={() => setShowHeroCoins(!showHeroCoins)}
              className="p-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[#79E282] transition-colors"
              title="Toggle 3D Coins Hero Banner"
            >
              <Sparkles className="h-4 w-4" />
            </button>

            {/* Light / Dark Mode Toggle */}
            <button
              onClick={toggleTheme}
              className="p-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
            >
              {theme === 'dark' ? <Sun className="h-4 w-4 text-[#E6A94A]" /> : <Moon className="h-4 w-4 text-[#368980]" />}
            </button>

            {/* User identity pill */}
            <div className="text-xs font-mono font-medium text-[#79E282] bg-[#79E282]/10 border border-[#79E282]/20 px-2.5 py-1 rounded-full truncate max-w-[180px]">
              {session.user.email}
            </div>
          </div>
        </header>

        {/* Standing Safe-Handling Advisory Banner */}
        <div className="bg-[#E6A94A]/10 border-b border-[#E6A94A]/30 px-6 py-2 flex items-center justify-between text-xs text-[#E6A94A]">
          <div className="flex items-center space-x-2.5">
            <span className="font-bold px-1.5 py-0.5 bg-[#E6A94A] text-[#0B0B0D] rounded text-[9.5px] tracking-wider uppercase">
              Law Enforcement Advisory
            </span>
            <span>
              Official recovery processes <strong>never</strong> ask victims for private keys, seed phrases, OTPs, or upfront fees. Unsolicited "recovery agents" are fraudulent.
            </span>
          </div>
          <span className="text-[#E6A94A]/80 font-bold hidden md:inline tracking-wider uppercase text-[10px]">
            SOP Chain of Custody
          </span>
        </div>

        {/* Mock/Demo Notification Banner */}
        {dataSource === 'mock' && (
          <div className="bg-[#E6A94A]/15 border-b border-[#E6A94A]/40 text-[#E6A94A] text-xs px-6 py-1.5 flex items-center space-x-2">
            <span className="font-bold uppercase tracking-wider text-[10px] bg-[#E6A94A]/30 px-1 py-0.5 rounded">Demo Data</span>
            <span>This dossier is powered by deterministic mock blockchain transactions for hermetic demonstration.</span>
          </div>
        )}

        {/* Main Content Router */}
        <main className="flex-1 overflow-auto p-6 bg-[var(--bg-main)] transition-colors duration-200">
          {/* Optional Collapsible 3D Crypto Coins Hero Section */}
          {showHeroCoins && location.pathname === '/' && (
            <Floating3DCoins
              onSelectChain={handleSelectChainFromCoins}
              activeChain={selectedChain}
            />
          )}

          <Routes>
            <Route
              path="/"
              element={
                <NewInvestigation
                  setActiveCase={setActiveCase}
                  activeCase={activeCase}
                  cases={cases}
                  onCaseCreated={refreshCases}
                  selectedChain={selectedChain}
                  onSelectChain={setSelectedChain}
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
    return (
      <div className="h-screen flex items-center justify-center bg-[#0B0B0D] text-[#79E282] font-mono text-sm">
        <div className="flex flex-col items-center space-y-3">
          <div className="h-8 w-8 border-2 border-[#79E282] border-t-transparent rounded-full animate-spin" />
          <span>INITIALIZING CRYPTOTRACER FORENSIC SUITE...</span>
        </div>
      </div>
    );
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
