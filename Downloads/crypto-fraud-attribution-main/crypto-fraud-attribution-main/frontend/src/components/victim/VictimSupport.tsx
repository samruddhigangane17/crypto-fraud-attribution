import React from 'react';
import {
  ShieldAlert,
  PhoneCall,
  HeartHandshake,
  Lock,
  HelpCircle,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  BookOpen,
} from 'lucide-react';

export const VictimSupport: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* High-Contrast Recovery-Scam Warning Banner */}
      <div className="bg-[var(--status-critical)]/10 border-2 border-[var(--status-critical)]/40 rounded-2xl p-6 shadow-xl flex items-start space-x-4">
        <div className="h-12 w-12 rounded-xl bg-[var(--status-critical)]/20 text-[var(--status-critical)] flex items-center justify-center shrink-0">
          <ShieldAlert className="h-6 w-6" />
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center space-x-2">
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-[var(--status-critical)] text-white">
              Critical Warning
            </span>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              Beware of "Crypto Recovery" Scammers
            </h2>
          </div>
          <p className="text-xs text-[var(--text-primary)] leading-relaxed">
            Anyone messaging you on Telegram, Instagram, WhatsApp, or email claiming they can "hack back" your lost crypto or recover your stolen funds for an upfront fee is a <strong>secondary recovery scammer</strong>.
            <br />
            Legitimate law enforcement officers and government nodal agencies <strong>never</strong> charge victims or ask for seed phrases, passwords, or remote desktop access.
          </p>
        </div>
      </div>

      {/* Emergency Helpline Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* National Cyber Crime Helpline */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-6 shadow-md flex flex-col justify-between space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--accent-primary)] bg-[var(--accent-primary)]/10 px-2 py-0.5 rounded">
                Financial Fraud Emergency
              </span>
              <PhoneCall className="h-4 w-4 text-[var(--accent-primary)]" />
            </div>
            <h3 className="text-base font-bold text-[var(--text-primary)]">
              National Cyber Helpline (1930)
            </h3>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              Dial <strong>1930</strong> immediately if funds were moved via UPI, bank transfer, or P2P within the last 2-4 hours. State police cyber cells can trigger emergency payment gateway holds.
            </p>
          </div>

          <div className="pt-2 flex items-center justify-between border-t border-[var(--border-color)]">
            <a
              href="https://cybercrime.gov.in"
              target="_blank"
              rel="noreferrer"
              className="text-xs font-bold text-[var(--accent-primary)] hover:underline flex items-center space-x-1"
            >
              <span>cybercrime.gov.in</span>
              <ExternalLink className="h-3 w-3" />
            </a>
            <span className="text-xs font-mono font-bold text-[var(--text-primary)]">Toll-Free 24x7</span>
          </div>
        </div>

        {/* Tele-MANAS Mental Health Support (Tele-MANAS 14416) */}
        <div className="bg-[var(--bg-card)] border border-purple-500/30 rounded-2xl p-6 shadow-md flex flex-col justify-between space-y-4 relative overflow-hidden">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded">
                Confidential Psychological Support
              </span>
              <HeartHandshake className="h-4 w-4 text-purple-400" />
            </div>
            <h3 className="text-base font-bold text-[var(--text-primary)]">
              Tele-MANAS Helpline (14416)
            </h3>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              Experiencing immense distress, sextortion blackmail, or severe financial anxiety? Dial <strong>14416</strong> for free, round-the-clock professional mental health counselling provided by the Ministry of Health.
            </p>
          </div>

          <div className="pt-2 flex items-center justify-between border-t border-[var(--border-color)]">
            <span className="text-xs font-semibold text-purple-400">
              100% Confidential & Free
            </span>
            <span className="text-xs font-mono font-bold text-[var(--text-primary)]">Dial 14416 or 1800 891 4416</span>
          </div>
        </div>
      </div>

      {/* "What Freezing Can and Cannot Do" Explainer Card */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center space-x-2">
          <HelpCircle className="h-5 w-5 text-[var(--accent-primary)]" />
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            What Freezing Can and Cannot Do (Transparent Forensic Reality)
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          {/* What Freezing CAN Do */}
          <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20 space-y-2">
            <div className="flex items-center space-x-1.5 text-emerald-400 font-bold">
              <CheckCircle2 className="h-4 w-4" />
              <span>What Law Enforcement CAN Do</span>
            </div>
            <ul className="space-y-1.5 text-[var(--text-muted)] list-disc list-inside">
              <li>
                <strong>Regulated Exchanges (VASPs):</strong> Issue BSA s.63 freeze notices to centralized exchanges (Binance, CoinDCX, WazirX) where scammer accounts are KYC-identified.
              </li>
              <li>
                <strong>Taint Tagging:</strong> Mark stolen wallet addresses in forensic surveillance databases to alert international exchange compliance desks.
              </li>
              <li>
                <strong>Bank Account Freezes:</strong> Intercept domestic P2P payment aggregator accounts via NCRP 1930 nodal officers.
              </li>
            </ul>
          </div>

          {/* What Freezing CANNOT Do */}
          <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-2">
            <div className="flex items-center space-x-1.5 text-amber-400 font-bold">
              <AlertTriangle className="h-4 w-4" />
              <span>What CANNOT Be Remotely Frozen</span>
            </div>
            <ul className="space-y-1.5 text-[var(--text-muted)] list-disc list-inside">
              <li>
                <strong>Unhosted Private Hardware Wallets:</strong> No government or police department has the mathematical ability to confiscate funds stored on private seed phrases without the private key.
              </li>
              <li>
                <strong>Decentralized Liquidity Pools:</strong> Permissionless smart contracts execute autonomously and cannot be reversed by human intervention.
              </li>
              <li>
                <strong>Instant Reversal:</strong> Cryptocurrency transactions are immutable by design; recovery requires legal coordination once funds hit a regulated fiat exit.
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Account-Securing Checklist */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center space-x-2">
          <Lock className="h-5 w-5 text-[var(--accent-primary)]" />
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            Immediate Account-Securing Checklist
          </h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div className="p-3 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] flex items-start space-x-2.5">
            <div className="h-5 w-5 rounded-full bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] flex items-center justify-center font-bold text-[10px] shrink-0">1</div>
            <div>
              <span className="font-semibold text-[var(--text-primary)]">Revoke Token Allowances:</span>
              <p className="text-[11px] text-[var(--text-muted)] mt-0.5">If you approved a malicious smart contract, use Revoke.cash or your wallet security tab to cancel approvals.</p>
            </div>
          </div>

          <div className="p-3 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] flex items-start space-x-2.5">
            <div className="h-5 w-5 rounded-full bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] flex items-center justify-center font-bold text-[10px] shrink-0">2</div>
            <div>
              <span className="font-semibold text-[var(--text-primary)]">Migrate Surviving Funds:</span>
              <p className="text-[11px] text-[var(--text-muted)] mt-0.5">Create a brand new wallet with a new seed phrase on a fresh device and transfer any remaining tokens.</p>
            </div>
          </div>

          <div className="p-3 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] flex items-start space-x-2.5">
            <div className="h-5 w-5 rounded-full bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] flex items-center justify-center font-bold text-[10px] shrink-0">3</div>
            <div>
              <span className="font-semibold text-[var(--text-primary)]">Change Passwords & Enable 2FA:</span>
              <p className="text-[11px] text-[var(--text-muted)] mt-0.5">Use hardware authenticators (YubiKey / Google Authenticator) rather than SMS OTPs on crypto exchange accounts.</p>
            </div>
          </div>

          <div className="p-3 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] flex items-start space-x-2.5">
            <div className="h-5 w-5 rounded-full bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] flex items-center justify-center font-bold text-[10px] shrink-0">4</div>
            <div>
              <span className="font-semibold text-[var(--text-primary)]">Preserve Evidence Intact:</span>
              <p className="text-[11px] text-[var(--text-muted)] mt-0.5">Export full Telegram/WhatsApp chat history as JSON/TXT before deleting or blocking the suspect account.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Plain Language Glossary */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center space-x-2">
          <BookOpen className="h-5 w-5 text-[var(--accent-primary)]" />
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            Plain Language Crypto Forensics Glossary
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)]">
            <span className="font-mono font-bold text-[var(--accent-primary)]">Taint Share</span>
            <p className="text-[11px] text-[var(--text-muted)] mt-1">The calculated percentage of your stolen cryptocurrency flowing into downstream intermediary wallets.</p>
          </div>
          <div className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)]">
            <span className="font-mono font-bold text-[var(--accent-primary)]">VASP (Virtual Asset Service Provider)</span>
            <p className="text-[11px] text-[var(--text-muted)] mt-1">A regulated cryptocurrency exchange (like Binance or CoinDCX) that holds user KYC identity information and can freeze accounts.</p>
          </div>
          <div className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)]">
            <span className="font-mono font-bold text-[var(--accent-primary)]">Cross-Chain Bridge</span>
            <p className="text-[11px] text-[var(--text-muted)] mt-1">A protocol used by scammers to swap tokens across different blockchains (e.g. Ethereum to TRON) to obscure trace paths.</p>
          </div>
          <div className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)]">
            <span className="font-mono font-bold text-[var(--accent-primary)]">Unhosted Wallet</span>
            <p className="text-[11px] text-[var(--text-muted)] mt-1">A non-custodial software or hardware wallet (e.g. MetaMask, Ledger) owned entirely by the key holder with no intermediary company.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
