import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Link, useLocation, useNavigate } from 'react-router-dom';
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
  Inbox,
  Shield,
  ExternalLink,
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
import { IntakeQueue } from './components/victim/IntakeQueue';
import { VictimPortal } from './components/victim/VictimPortal';

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

function Dashboard({
  session,
  onSwitchToVictim,
  onSignOut,
}: {
  session: Session;
  onSwitchToVictim?: () => void;
  onSignOut?: () => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();

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

  // Core Workflow Tabs (strictly 1 active view at a time)
  const coreTabs = [
    { path: '/', label: 'New Investigation', icon: Search },
    { path: '/intake', label: 'Registered Complaints', icon: Inbox },
    { path: '/graph', label: 'Fund-Flow Graph', icon: Share2 },
    { path: '/recovery', label: 'Recovery Layer', icon: Clock },
    { path: '/report', label: 'Evidence Report', icon: FileText },
  ];

  // Secondary analysis modules
  const secondaryLinks = [
    { path: '/risk', label: 'Risk & Attribution', icon: ShieldAlert },
    { path: '/alerts', label: 'Monitoring Alerts', icon: Activity },
  ];

  const getPageInfo = () => {
    const path = location.pathname;
    if (path === '/' || path === '') {
      return {
        title: 'New Investigation',
        category: 'TARGET INGESTION',
        subtitle: 'Multi-chain target ingestion, address resolution, and transaction dispatch',
      };
    }
    if (path.startsWith('/intake')) {
      return {
        title: 'Registered Complaints',
        category: 'CITIZEN COMPLAINTS INTAKE',
        subtitle: 'Manage registered victim complaints, advance lifecycle verification, and promote to active investigation',
      };
    }
    if (path.startsWith('/graph')) {
      return {
        title: 'Fund-Flow Graph',
        category: 'MULTI-HOP GRAPH',
        subtitle: 'Interactive multi-hop taint tracking, flow topology, and cluster expansion',
      };
    }
    if (path.startsWith('/recovery')) {
      return {
        title: 'Recovery Layer',
        category: 'ASSET RECOVERY',
        subtitle: 'Golden Hour countdown clock, typology classifier, and legal freeze pack generation',
      };
    }
    if (path.startsWith('/report')) {
      return {
        title: 'Evidence Report',
        category: 'FORENSIC DOSSIER',
        subtitle: 'Court-admissible tamper-evident report with SHA-256 digital signature verification',
      };
    }
    if (path.startsWith('/risk')) {
      return {
        title: 'Risk & Attribution',
        category: 'SCORING ENGINE',
        subtitle: 'Deterministic forensic risk classification, entity profiling, and typology analysis',
      };
    }
    if (path.startsWith('/alerts')) {
      return {
        title: 'Monitoring Alerts',
        category: 'SURVEILLANCE',
        subtitle: 'Real-time on-chain wallet monitoring, velocity alerts, and convergence detection',
      };
    }
    if (path.startsWith('/victim')) {
      return {
        title: 'Citizen Victim Portal',
        category: 'CITIZEN INGESTION',
        subtitle: 'Citizen complaint wizard, evidence vault, and case status tracker',
      };
    }
    return {
      title: 'Forensic Workspace',
      category: 'DASHBOARD',
      subtitle: 'CryptoTracer Anti-Fraud Attribution Suite',
    };
  };

  const handleSelectChainFromCoins = (chain: 'ethereum' | 'tron' | 'bitcoin' | 'bsc') => {
    setSelectedChain(chain);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg-main)] text-[var(--text-primary)]">
      {/* Left Sidebar */}
      <aside className="w-64 bg-[var(--bg-card)] border-r border-[var(--border-color)] flex flex-col transition-colors duration-200">
        <div className="p-4 border-b border-[var(--border-color)]">
          <CryptoTracerLogo />
        </div>

        <nav className="flex-1 p-3 space-y-4 overflow-y-auto">
          {/* Primary 4 Core Tabs */}
          <div>
            <div className="text-[10px] uppercase font-bold tracking-wider text-[var(--text-muted)] px-3 mb-1.5">
              Core Forensic Workflow
            </div>
            <div className="space-y-1">
              {coreTabs.map((item) => {
                const Icon = item.icon;
                const isActive = item.path === '/'
                  ? (location.pathname === '/' || location.pathname === '')
                  : location.pathname.startsWith(item.path);

                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center px-3 py-2.5 rounded-xl text-xs transition-all duration-150 ${
                      isActive
                        ? 'bg-[var(--bg-surface)] text-[var(--accent-primary)] border-l-4 border-[var(--accent-primary)] shadow-sm font-bold'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)] font-medium'
                    }`}
                  >
                    <Icon className={`mr-2.5 h-4 w-4 ${isActive ? 'text-[var(--accent-primary)]' : 'text-[var(--text-muted)]'}`} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Secondary Specialized Modules */}
          <div className="pt-2 border-t border-[var(--border-subtle)]">
            <div className="text-[10px] uppercase font-bold tracking-wider text-[var(--text-muted)] px-3 mb-1.5">
              Telemetry & Alerts
            </div>
            <div className="space-y-1">
              {secondaryLinks.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname.startsWith(item.path);

                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center px-3 py-2 rounded-xl text-xs transition-all duration-150 ${
                      isActive
                        ? 'bg-[var(--bg-surface)] text-[var(--accent-primary)] border-l-4 border-[var(--accent-primary)] font-bold'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)] font-medium'
                    }`}
                  >
                    <Icon className={`mr-2.5 h-3.5 w-3.5 ${isActive ? 'text-[var(--accent-primary)]' : 'text-[var(--text-muted)]'}`} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </nav>

        {/* Sidebar Footer with Sign Out */}
        <div className="p-3 border-t border-[var(--border-color)]">
          <button
            onClick={() => {
              if (onSignOut) {
                onSignOut();
              } else {
                supabase.auth.signOut();
              }
            }}
            className="flex items-center w-full px-3 py-2 text-xs font-medium text-[var(--text-muted)] hover:text-[#D95F63] hover:bg-[#D95F63]/10 rounded-xl transition-colors cursor-pointer"
          >
            <LogOut className="mr-2.5 h-4 w-4" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Execution Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Navbar */}
        <header className="bg-[var(--bg-card)] border-b border-[var(--border-color)] px-6 py-2.5 flex flex-wrap justify-between items-center gap-3 transition-colors duration-200">
          {/* Active Breadcrumb / Page Title */}
          <div className="flex items-center space-x-3">
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-sm font-bold text-[var(--text-primary)] tracking-tight">
                  {getPageInfo().title}
                </h1>
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-md bg-[var(--bg-surface)] text-[var(--accent-primary)] border border-[var(--border-color)]">
                  {getPageInfo().category}
                </span>
              </div>
              <p className="text-[11px] text-[var(--text-muted)]">
                {getPageInfo().subtitle}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {/* Active Case Selector */}
            <div className="flex items-center space-x-1.5">
              <label htmlFor="case-select" className="text-xs font-medium text-[var(--text-muted)] flex items-center">
                <FolderOpen className="h-3.5 w-3.5 mr-1 text-[var(--accent-primary)]" />
                Case:
              </label>
              {cases.length > 0 ? (
                <select
                  id="case-select"
                  value={activeCase || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val) setActiveCase(val);
                  }}
                  className="bg-[var(--bg-surface)] border border-[var(--border-color)] text-[var(--text-primary)] text-xs rounded-lg px-2 py-1 focus:ring-2 focus:ring-[var(--accent-primary)] focus:border-[var(--accent-primary)] shadow-sm max-w-[240px] truncate font-mono"
                  title="Switch active investigation"
                >
                  {!activeCase && <option value="">Select investigation...</option>}
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

            {/* Citizen Victim Portal Switcher */}
            <button
              onClick={() => (onSwitchToVictim ? onSwitchToVictim() : navigate('/victim'))}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-surface)] hover:bg-[var(--accent-primary)]/10 text-xs font-semibold text-[var(--accent-primary)] hover:border-[var(--accent-primary)] transition-all shadow-sm"
              title="Open Citizen Victim Portal"
            >
              <Shield className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Citizen Portal</span>
              <ExternalLink className="h-3 w-3 opacity-70" />
            </button>

            {/* Light / Dark Mode Toggle */}
            <button
              onClick={toggleTheme}
              className="p-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
            >
              {theme === 'dark' ? <Sun className="h-4 w-4 text-[#E6A94A]" /> : <Moon className="h-4 w-4 text-[#368980]" />}
            </button>

            {/* Officer Email Pill */}
            <div className="text-xs font-mono font-medium text-[var(--accent-primary)] bg-[var(--accent-primary)]/10 border border-[var(--accent-primary)]/20 px-2.5 py-1 rounded-full truncate max-w-[170px]">
              {session.user.email}
            </div>
          </div>
        </header>

        {/* Standing Safe-Handling Advisory Banner */}
        <div className="bg-[var(--status-warning-bg)] border-b border-[var(--status-warning-border)] px-6 py-2 flex items-center justify-between text-xs text-[var(--status-warning)]">
          <div className="flex items-center space-x-2">
            <span className="font-bold px-1.5 py-0.5 bg-[var(--status-warning)] text-[var(--bg-card)] rounded text-[9.5px] tracking-wider uppercase">
              Law Enforcement Advisory
            </span>
            <span>
              Official recovery processes <strong>never</strong> ask victims for private keys, seed phrases, OTPs, or upfront fees. Unsolicited "recovery agents" are fraudulent.
            </span>
          </div>
          <span className="opacity-80 font-bold hidden md:inline tracking-wider uppercase text-[10px]">
            SOP Chain of Custody
          </span>
        </div>

        {dataSource === 'mock' && (
          <div className="bg-[var(--status-warning-bg)] border-b border-[var(--status-warning-border)] text-[var(--status-warning)] text-xs px-6 py-1.5 flex items-center space-x-2">
            <span className="font-bold uppercase tracking-wider text-[10px] bg-[var(--status-warning)] text-[var(--bg-card)] px-1 py-0.5 rounded">Demo Data</span>
            <span>This dossier is powered by deterministic mock blockchain transactions for hermetic demonstration.</span>
          </div>
        )}

        {/* Main Content Router — STRICT TAB ISOLATION */}
        <main className="flex-1 overflow-auto p-6 bg-[var(--bg-primary)] transition-colors duration-200 flex flex-col">
          {/* TAB 1: Only renders 3D Floating Coins Hero + NewInvestigation */}
          {(location.pathname === '/' || location.pathname === '') && (
            <div className="space-y-6">
              <Floating3DCoins
                onSelectChain={handleSelectChainFromCoins}
                activeChain={selectedChain}
              />
              <NewInvestigation
                setActiveCase={setActiveCase}
                activeCase={activeCase}
                cases={cases}
                onCaseCreated={refreshCases}
                selectedChain={selectedChain}
                onSelectChain={setSelectedChain}
              />
            </div>
          )}

          {/* TAB 2: Only renders FundFlowGraph (full width, no side clocks) */}
          {location.pathname.startsWith('/graph') && (
            <div className="flex-1 flex flex-col h-full min-h-[550px]">
              <FundFlowGraph activeCase={activeCase} />
            </div>
          )}

          {/* TAB 3: Only renders RecoveryLayer */}
          {location.pathname.startsWith('/recovery') && (
            <RecoveryLayer activeCase={activeCase} />
          )}

          {/* TAB 4: Only renders EvidenceReport */}
          {location.pathname.startsWith('/report') && (
            <EvidenceReport activeCase={activeCase} />
          )}

          {/* TAB: Intake Queue (Registered Complaints) */}
          {location.pathname.startsWith('/intake') && (
            <IntakeQueue setActiveCase={setActiveCase} />
          )}

          {/* TAB: Citizen Victim Portal */}
          {location.pathname.startsWith('/victim') && (
            <div className="flex-1 -m-6">
              <VictimPortal
                onSwitchToInvestigator={() => (onSwitchToVictim ? onSwitchToVictim() : navigate('/'))}
                theme={theme}
                onToggleTheme={toggleTheme}
              />
            </div>
          )}

          {/* Secondary Telemetry Routes */}
          {location.pathname.startsWith('/risk') && (
            <RiskAttribution activeCase={activeCase} />
          )}
          {location.pathname.startsWith('/alerts') && (
            <MonitoringAlerts activeCase={activeCase} />
          )}

          {/* Defensive fallback for unmatched routes so screen is NEVER blank */}
          {!['/', '', '/graph', '/recovery', '/report', '/intake', '/victim', '/risk', '/alerts'].some(
            (p) => p === location.pathname || (p !== '' && p !== '/' && location.pathname.startsWith(p))
          ) && (
            <div className="flex-1 flex items-center justify-center p-8 text-center">
              <div className="max-w-md p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl space-y-3">
                <Inbox className="h-10 w-10 text-[var(--accent-primary)] mx-auto opacity-80" />
                <h3 className="text-sm font-bold text-[var(--text-primary)]">Module View Restored</h3>
                <p className="text-xs text-[var(--text-muted)]">
                  The requested path <code className="text-[var(--accent-primary)]">{location.pathname}</code> is not directly mapped. Choose a core module below:
                </p>
                <div className="pt-2 flex justify-center space-x-3">
                  <Link
                    to="/"
                    className="px-4 py-2 bg-[var(--accent-primary)] text-black rounded-xl text-xs font-bold hover:opacity-90 transition-all"
                  >
                    New Investigation
                  </Link>
                  <Link
                    to="/intake"
                    className="px-4 py-2 bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)] rounded-xl text-xs font-bold hover:bg-[var(--bg-card)] transition-all"
                  >
                    Registered Complaints
                  </Link>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

const DEV_SESSION_KEY = 'cryptotracer_dev_session';

function AppComponent() {
  const [session, setSession] = useState<Session | null>(null);
  const [devSession, setDevSession] = useState<Session | null>(() => {
    try {
      const stored = localStorage.getItem(DEV_SESSION_KEY);
      if (stored) return JSON.parse(stored);
    } catch {}
    return null;
  });
  const [loading, setLoading] = useState(true);
  const [portalMode, setPortalMode] = useState<'investigator' | 'victim'>(() => {
    if (typeof window !== 'undefined' && window.location.pathname.startsWith('/victim')) {
      return 'victim';
    }
    return 'investigator';
  });

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

  const handleDevLogin = (officerEmail: string) => {
    const mockSession = {
      access_token: 'dev-token-' + Date.now(),
      token_type: 'bearer',
      expires_in: 3600,
      refresh_token: 'dev-refresh',
      user: {
        id: 'dev-investigator-001',
        app_metadata: {},
        user_metadata: {},
        aud: 'authenticated',
        created_at: new Date().toISOString(),
        email: officerEmail || 'officer.lead@cryptotracer.gov',
      },
    } as unknown as Session;

    try {
      localStorage.setItem(DEV_SESSION_KEY, JSON.stringify(mockSession));
    } catch {}
    setDevSession(mockSession);
  };

  const handleSignOut = () => {
    try {
      localStorage.removeItem(DEV_SESSION_KEY);
    } catch {}
    setDevSession(null);
    setSession(null);
    supabase.auth.signOut().catch(() => {});
  };

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    }).catch(() => {
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

  // Standalone Citizen Victim Portal view (no investigator auth required)
  if (portalMode === 'victim') {
    return (
      <Router>
        <VictimPortal
          onSwitchToInvestigator={() => setPortalMode('investigator')}
          theme={theme}
          onToggleTheme={toggleTheme}
        />
      </Router>
    );
  }

  const currentSession = session || devSession;

  if (!currentSession) {
    return (
      <Login
        onOpenVictimPortal={() => setPortalMode('victim')}
        onVictimAuthenticated={() => setPortalMode('victim')}
        onInvestigatorDevLogin={handleDevLogin}
      />
    );
  }

  return (
    <Router>
      <Dashboard
        session={currentSession}
        onSwitchToVictim={() => setPortalMode('victim')}
        onSignOut={handleSignOut}
      />
    </Router>
  );
}

class AppErrorBoundary extends React.Component<
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
    console.error('App top-level error caught by boundary:', error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen bg-[#0B0B0D] text-[#F3F8F5] flex items-center justify-center p-6 font-['Montserrat']">
          <div className="bg-[#141419] border border-[#23232C] rounded-2xl p-8 text-center space-y-4 max-w-md w-full shadow-2xl">
            <div className="h-14 w-14 rounded-2xl bg-amber-500/10 text-amber-400 mx-auto flex items-center justify-center">
              <Shield className="h-7 w-7" />
            </div>
            <h2 className="text-base font-bold text-white">CryptoTracer Session Restored</h2>
            <p className="text-xs text-[#9E9EA8]">
              A temporary interface exception was caught. Click below to refresh your view.
            </p>
            <div className="pt-2">
              <button
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.reload();
                }}
                className="w-full py-2.5 px-4 rounded-xl bg-[#79E282] text-black font-bold text-xs hover:opacity-90 shadow-md cursor-pointer"
              >
                Reload Console
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <AppErrorBoundary>
      <AppComponent />
    </AppErrorBoundary>
  );
}
