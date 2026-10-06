import React, { useState } from 'react';
import { ChevronUp, ChevronDown, ArrowRight, Zap, Shield, Search } from 'lucide-react';

interface Floating3DCoinsProps {
  onSelectChain: (chain: 'ethereum' | 'tron' | 'bitcoin' | 'bsc') => void;
  activeChain?: string;
}

interface CoinConfig {
  id: 'ethereum' | 'tron' | 'bitcoin' | 'bsc';
  name: 'Ethereum' | 'TRON' | 'Bitcoin' | 'BNB Chain';
  ticker: 'ETH' | 'TRX' | 'BTC' | 'BSC';
  tag: string;
  gradient: string;
  rimColor: string;
  glowColor: string;
  accentHex: string;
  floatClass: string;
  sampleAddr: string;
}

const COINS: CoinConfig[] = [
  {
    id: 'ethereum',
    name: 'Ethereum',
    ticker: 'ETH',
    tag: 'Account Model · ERC-20 & Mixers',
    gradient: 'from-[#C7D2FE] via-[#6366F1] to-[#312E81]',
    rimColor: '#818CF8',
    glowColor: 'rgba(99, 102, 241, 0.35)',
    accentHex: '#6366F1',
    floatClass: 'animate-float-1',
    sampleAddr: '0xmock_wallet_a',
  },
  {
    id: 'tron',
    name: 'TRON',
    ticker: 'TRX',
    tag: 'High-Velocity · USDT-TRC20',
    gradient: 'from-[#FCA5A5] via-[#EF4444] to-[#7F1D1D]',
    rimColor: '#F87171',
    glowColor: 'rgba(239, 68, 68, 0.35)',
    accentHex: '#EF4444',
    floatClass: 'animate-float-2',
    sampleAddr: 'T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb',
  },
  {
    id: 'bitcoin',
    name: 'Bitcoin',
    ticker: 'BTC',
    tag: 'UTXO Model · Co-Spend Clustering',
    gradient: 'from-[#FDE68A] via-[#F59E0B] to-[#78350F]',
    rimColor: '#FBBF24',
    glowColor: 'rgba(245, 158, 11, 0.35)',
    accentHex: '#F59E0B',
    floatClass: 'animate-float-3',
    sampleAddr: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
  },
  {
    id: 'bsc',
    name: 'BNB Chain',
    ticker: 'BSC',
    tag: 'EVM Layer · DEX Liquidity Swaps',
    gradient: 'from-[#FEF08A] via-[#EAB308] to-[#713F12]',
    rimColor: '#FACC15',
    glowColor: 'rgba(234, 179, 8, 0.35)',
    accentHex: '#EAB308',
    floatClass: 'animate-float-4',
    sampleAddr: '0x8894e0a0c962cb723c1976a4421c95949be2d4e3',
  },
];

const Floating3DCoins: React.FC<Floating3DCoinsProps> = ({ onSelectChain, activeChain }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [hoveredCoin, setHoveredCoin] = useState<string | null>(null);

  const handleCoinClick = (chain: 'ethereum' | 'tron' | 'bitcoin' | 'bsc') => {
    onSelectChain(chain);
    // Smooth scroll to the investigation form
    const formElement = document.getElementById('investigation-form') || document.getElementById('wallet-address-input');
    if (formElement) {
      formElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // Focus the input if available
      const input = document.getElementById('wallet-address-input') as HTMLInputElement | null;
      if (input) {
        setTimeout(() => input.focus(), 300);
      }
    }
  };

  return (
    <div className="relative mb-6 rounded-2xl overflow-hidden border border-[#243338] bg-[#11171A] shadow-xl transition-all duration-300">
      {/* Decorative ambient background mesh */}
      <div className="absolute inset-0 pointer-events-none opacity-20">
        <div className="absolute -top-24 left-1/4 w-96 h-96 bg-[#79E282] rounded-full blur-3xl" />
        <div className="absolute -bottom-24 right-1/4 w-96 h-96 bg-[#368980] rounded-full blur-3xl" />
      </div>

      {/* Header bar with collapse toggle */}
      <div className="relative z-10 px-6 py-4 flex items-center justify-between border-b border-[#1C272A] bg-[#0E1315]/80 backdrop-blur-md">
        <div className="flex items-center space-x-3">
          <div className="h-2 w-2 rounded-full bg-[#79E282] animate-ping" />
          <span className="text-[11px] font-bold tracking-widest text-[#79E282] uppercase">
            Multi-Chain Interactive Traversal
          </span>
          <span className="text-xs text-[#899695] hidden sm:inline">| Click any 3D asset to activate live trace</span>
        </div>
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="flex items-center space-x-1.5 px-2.5 py-1 text-xs font-medium text-[#899695] hover:text-[#E8EEEB] bg-[#182124] hover:bg-[#1F2B2F] border border-[#243338] rounded-md transition-colors"
          title={isCollapsed ? 'Expand 3D Hero' : 'Collapse 3D Hero'}
        >
          <span>{isCollapsed ? 'Show 3D Coins' : 'Collapse'}</span>
          {isCollapsed ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
        </button>
      </div>

      {!isCollapsed && (
        <div className="relative z-10 p-6 md:p-8">
          <div className="text-center max-w-2xl mx-auto mb-8">
            <h2 className="text-2xl md:text-3xl font-extrabold text-[#E8EEEB] tracking-tight mb-2">
              Select Blockchain Architecture
            </h2>
            <p className="text-sm text-[#899695] leading-relaxed">
              Real-time heuristic clustering and forward taint-flow analysis across UTXO and EVM chains. Click a coin to auto-configure investigation parameters.
            </p>
          </div>

          {/* 3D Extruded Coins Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {COINS.map((c) => {
              const isSelected = activeChain === c.id;
              const isHovered = hoveredCoin === c.id;

              return (
                <div
                  key={c.id}
                  onClick={() => handleCoinClick(c.id)}
                  onMouseEnter={() => setHoveredCoin(c.id)}
                  onMouseLeave={() => setHoveredCoin(null)}
                  className={`group relative cursor-pointer rounded-xl p-5 border transition-all duration-300 flex flex-col items-center text-center ${
                    isSelected
                      ? 'border-[#79E282] bg-[#182124] ring-2 ring-[#79E282]/40 shadow-lg'
                      : 'border-[#243338] bg-[#141C1F] hover:border-[#368980] hover:bg-[#182124]'
                  }`}
                  style={{
                    boxShadow: isHovered || isSelected ? `0 12px 30px -8px ${c.glowColor}` : undefined,
                  }}
                >
                  {/* Active selection badge */}
                  {isSelected && (
                    <div className="absolute top-2.5 right-2.5 flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#79E282]/20 text-[#79E282] border border-[#79E282]/40">
                      <Zap className="h-3 w-3" />
                      <span>SELECTED</span>
                    </div>
                  )}

                  {/* 3D Coin Pure CSS Container */}
                  <div className={`relative w-28 h-28 my-3 preserve-3d perspective-1000 ${c.floatClass}`}>
                    <div
                      className={`w-full h-full preserve-3d transition-transform duration-700 ease-out ${
                        isHovered ? 'scale-110' : ''
                      }`}
                      style={{
                        animation: isHovered ? 'coin-spin-slow 3s infinite linear' : 'coin-spin-slow 12s infinite linear',
                        transformStyle: 'preserve-3d',
                      }}
                    >
                      {/* FRONT FACE OF COIN */}
                      <div
                        className="absolute inset-0 rounded-full flex items-center justify-center backface-hidden shadow-2xl border-4"
                        style={{
                          background: `radial-gradient(circle at 35% 30%, #FFFFFF 0%, transparent 40%), linear-gradient(135deg, ${c.accentHex} 0%, #111827 100%)`,
                          borderColor: c.rimColor,
                          boxShadow: `inset 0 0 12px rgba(255,255,255,0.4), 0 8px 20px ${c.glowColor}`,
                          transform: 'translateZ(6px)',
                        }}
                      >
                        {/* Coin Inner Concentric Ring */}
                        <div
                          className="w-20 h-20 rounded-full border-2 border-dashed flex items-center justify-center"
                          style={{ borderColor: 'rgba(255,255,255,0.3)' }}
                        >
                          {/* Coin Emblem SVGs */}
                          {c.id === 'bitcoin' && (
                            <span className="text-3xl font-black text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]">
                              ₿
                            </span>
                          )}
                          {c.id === 'ethereum' && (
                            <svg className="w-9 h-9 text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]" viewBox="0 0 256 417" fill="currentColor">
                              <path d="M127.961 0l-2.795 9.5v275.668l2.795 2.79 127.962-75.638z" fillOpacity="0.9" />
                              <path d="M127.962 0L0 212.32l127.962 75.639V0z" fillOpacity="0.7" />
                              <path d="M127.961 312.187l-1.575 1.92v100.088l1.575 4.605 128.038-179.99z" fillOpacity="0.9" />
                              <path d="M127.962 418.8lV312.187L0 238.805z" fillOpacity="0.7" />
                            </svg>
                          )}
                          {c.id === 'tron' && (
                            <svg className="w-9 h-9 text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]" viewBox="0 0 32 32" fill="currentColor">
                              <path d="M29.5 7.5L2.5 3.5l10 24.5 17-20.5zm-3.2 2.6L14.7 20.3 6.4 5.9l19.9 4.2z" />
                            </svg>
                          )}
                          {c.id === 'bsc' && (
                            <svg className="w-9 h-9 text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]" viewBox="0 0 32 32" fill="currentColor">
                              <path d="M16 4l4 4-4 4-4-4 4-4zm8 8l4 4-4 4-4-4 4-4zm-16 0l4 4-4 4-4-4 4-4zm8 8l4 4-4 4-4-4 4-4z" />
                            </svg>
                          )}
                        </div>
                      </div>

                      {/* BACK FACE OF COIN */}
                      <div
                        className="absolute inset-0 rounded-full flex items-center justify-center backface-hidden shadow-2xl border-4"
                        style={{
                          background: `radial-gradient(circle at 65% 70%, #FFFFFF 0%, transparent 40%), linear-gradient(315deg, ${c.accentHex} 0%, #111827 100%)`,
                          borderColor: c.rimColor,
                          boxShadow: `inset 0 0 12px rgba(255,255,255,0.4), 0 8px 20px ${c.glowColor}`,
                          transform: 'rotateY(180deg) translateZ(6px)',
                        }}
                      >
                        <div
                          className="w-20 h-20 rounded-full border-2 border-dashed flex flex-col items-center justify-center"
                          style={{ borderColor: 'rgba(255,255,255,0.3)' }}
                        >
                          <Shield className="h-5 w-5 text-white/90 mb-0.5" />
                          <span className="text-[10px] font-bold uppercase tracking-wider text-white/90">
                            {c.ticker}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Label & Details */}
                  <div className="mt-2 w-full">
                    <div className="flex items-center justify-center space-x-1.5 font-bold text-base text-[#E8EEEB]">
                      <span>{c.name}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-[#1C272A] text-[#899695] font-mono">
                        {c.ticker}
                      </span>
                    </div>
                    <div className="text-[11px] text-[#899695] mt-1 line-clamp-1">{c.tag}</div>
                  </div>

                  {/* Interactive Button */}
                  <div className="mt-4 w-full pt-3 border-t border-[#1C272A] flex items-center justify-between text-xs font-medium text-[#79E282] group-hover:text-white transition-colors">
                    <span className="flex items-center">
                      <Search className="h-3 w-3 mr-1" />
                      Trace {c.ticker}
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 transform group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default Floating3DCoins;
