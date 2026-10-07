import React, { useState, useEffect } from 'react';
import {
  Shield,
  FileText,
  Clock,
  Layers,
  HelpCircle,
  LogOut,
  ExternalLink,
  Sun,
  Moon,
  User,
} from 'lucide-react';
import { VictimAuth } from './VictimAuth';
import { ComplaintWizard } from './ComplaintWizard';
import { EvidenceVault } from './EvidenceVault';
import { VictimTracker } from './VictimTracker';
import { VictimSupport } from './VictimSupport';
import CryptoTracerLogo from '../CryptoTracerLogo';
import {
  getStoredVictimSession,
  clearVictimSession,
  type VictimSession,
  type ComplaintData,
} from '../../lib/victimApi';

export interface VictimPortalProps {
  onSwitchToInvestigator: () => void;
  theme?: 'dark' | 'light';
  onToggleTheme?: () => void;
}

const VictimPortalComponent: React.FC<VictimPortalProps> = ({
  onSwitchToInvestigator,
  theme = 'dark',
  onToggleTheme,
}) => {
  const [session, setSession] = useState<VictimSession | null>(getStoredVictimSession);
  const [activeTab, setActiveTab] = useState<'wizard' | 'tracker' | 'vault' | 'support'>('wizard');
  const [activeComplaintId, setActiveComplaintId] = useState<string>('');

  useEffect(() => {
    const s = getStoredVictimSession();
    if (s) setSession(s);
  }, []);

  const handleAuthenticated = (newSession: VictimSession) => {
    setSession(newSession);
  };

  const handleLogout = () => {
    clearVictimSession();
    setSession(null);
  };

  const handleComplaintSubmitted = (complaint: ComplaintData) => {
    setActiveComplaintId(complaint.ack_id || complaint.id || '');
    // Retain wizard view so citizen sees the Acknowledgement / Success screen with their ACK ID
  };

  // If not authenticated, show VictimAuth gateway
  if (!session) {
    return (
      <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
        <header className="border-b border-[var(--border-color)] bg-[var(--bg-card)] px-6 py-3 flex items-center justify-between">
          <CryptoTracerLogo />
          <button
            onClick={onSwitchToInvestigator}
            className="text-xs font-semibold text-[var(--accent-primary)] hover:underline flex items-center space-x-1.5"
          >
            <span>Forensic Investigator Console</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
        </header>
        <VictimAuth
          onAuthenticated={handleAuthenticated}
          onSwitchToInvestigator={onSwitchToInvestigator}
        />
      </div>
    );
  }

  const tabs = [
    { id: 'wizard', label: 'Lodge Complaint', icon: FileText },
    { id: 'tracker', label: 'Case Status Tracker', icon: Clock },
    { id: 'vault', label: 'Evidence Vault', icon: Layers },
    { id: 'support', label: 'Safety & Support Center', icon: HelpCircle },
  ] as const;

  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg-primary)] text-[var(--text-primary)] transition-colors duration-200">
      {/* Top Citizen Header Bar */}
      <header className="bg-[var(--bg-card)] border-b border-[var(--border-color)] px-6 py-3 flex flex-wrap justify-between items-center gap-4 shadow-sm">
        <div className="flex items-center space-x-4">
          <CryptoTracerLogo />
          <div className="hidden sm:flex items-center space-x-1.5 text-xs text-[var(--text-muted)] border-l border-[var(--border-color)] pl-4">
            <Shield className="h-3.5 w-3.5 text-[var(--accent-primary)]" />
            <span className="font-semibold text-[var(--text-primary)]">Citizen Victim Portal</span>
            <span className="text-[10px] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border border-[var(--accent-primary)]/20 px-2 py-0.5 rounded-full font-mono">
              DPDP Safe Realm
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {/* Theme Toggle */}
          {onToggleTheme && (
            <button
              onClick={onToggleTheme}
              className="p-1.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
            >
              {theme === 'dark' ? <Sun className="h-4 w-4 text-[#E6A94A]" /> : <Moon className="h-4 w-4 text-[#368980]" />}
            </button>
          )}

          {/* User Pseudonym Pill */}
          <div className="flex items-center space-x-1.5 px-3 py-1 rounded-full bg-[var(--bg-secondary)] border border-[var(--border-color)] text-xs font-mono text-[var(--text-primary)]">
            <User className="h-3 w-3 text-[var(--accent-primary)]" />
            <span>{session.displayName || session.email || (session.phone ? `+91 ***${session.phone.slice(-4)}` : 'Citizen')}</span>
          </div>

          {/* Switch to Investigator Console Button */}
          <button
            onClick={onSwitchToInvestigator}
            className="px-3 py-1.5 rounded-xl bg-[var(--bg-secondary)] hover:bg-[var(--bg-card)] border border-[var(--border-color)] text-xs font-semibold text-[var(--accent-primary)] flex items-center space-x-1.5 transition-colors shadow-sm"
          >
            <span>Investigator Console</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </button>

          {/* Sign Out */}
          <button
            onClick={handleLogout}
            className="p-1.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--status-critical)] transition-colors"
            title="Log Out of Portal"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* Citizen Protective Notice Banner */}
      <div className="bg-[var(--bg-secondary)] border-b border-[var(--border-color)] px-6 py-2 text-xs text-[var(--text-muted)] flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="h-2 w-2 rounded-full bg-[var(--accent-primary)] animate-pulse" />
          <span>
            <strong>Zero Vigilante / Anti-Leakage Shield Active:</strong> Internal risk scores and investigator notes are strictly quarantined.
          </span>
        </div>
        <span className="hidden md:inline font-mono text-[10px] text-[var(--accent-primary)]">
          CONFIDENTIAL CITIZEN CHANNEL
        </span>
      </div>

      {/* Main Container */}
      <div className="flex-1 max-w-5xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Navigation Tabs */}
        <div className="flex border-b border-[var(--border-color)] space-x-2 overflow-x-auto pb-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                  isActive
                    ? 'bg-[var(--bg-card)] text-[var(--accent-primary)] border border-[var(--border-color)] shadow-sm'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]/50'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-[var(--accent-primary)]' : 'text-[var(--text-muted)]'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab Views */}
        <div className="pt-2">
          {activeTab === 'wizard' && (
            <ComplaintWizard
              onComplaintSubmitted={handleComplaintSubmitted}
              onNavigateToVault={(cid) => {
                setActiveComplaintId(cid);
                setActiveTab('vault');
              }}
              onNavigateToTracker={(cid) => {
                setActiveComplaintId(cid);
                setActiveTab('tracker');
              }}
            />
          )}

          {activeTab === 'tracker' && (
            <VictimTracker
              complaintId={activeComplaintId}
              onNavigateToVault={(cid) => {
                setActiveComplaintId(cid);
                setActiveTab('vault');
              }}
            />
          )}

          {activeTab === 'vault' && (
            <EvidenceVault
              complaintId={activeComplaintId}
              userPseudonym={session.displayName}
            />
          )}

          {activeTab === 'support' && <VictimSupport />}
        </div>
      </div>
    </div>
  );
};

class PortalErrorBoundary extends React.Component<
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
    console.error('VictimPortal error caught by boundary:', error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] flex items-center justify-center p-6 font-['Montserrat']">
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-8 text-center space-y-4 max-w-lg w-full shadow-2xl">
            <div className="h-14 w-14 rounded-2xl bg-amber-500/10 text-amber-400 mx-auto flex items-center justify-center">
              <Shield className="h-7 w-7" />
            </div>
            <h3 className="text-base font-bold text-[var(--text-primary)]">
              Citizen Portal Display Recovered
            </h3>
            <p className="text-xs text-[var(--text-muted)]">
              A temporary render exception occurred. Your report session is safely preserved. Click below to continue.
            </p>
            <div className="pt-2 flex justify-center space-x-3">
              <button
                onClick={() => this.setState({ hasError: false, error: null })}
                className="px-5 py-2.5 rounded-xl bg-[var(--accent-primary)] text-black font-bold text-xs hover:opacity-90 shadow-md transition-opacity cursor-pointer"
              >
                Reload Portal View
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export const VictimPortal: React.FC<VictimPortalProps> = (props) => {
  return (
    <PortalErrorBoundary>
      <VictimPortalComponent {...props} />
    </PortalErrorBoundary>
  );
};
