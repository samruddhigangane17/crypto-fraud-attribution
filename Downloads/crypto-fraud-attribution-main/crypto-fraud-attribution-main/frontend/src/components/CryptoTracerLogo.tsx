import React from 'react';

interface CryptoTracerLogoProps {
  className?: string;
  iconOnly?: boolean;
}

export const CryptoTracerLogo: React.FC<CryptoTracerLogoProps> = ({ className = '', iconOnly = false }) => {
  return (
    <div className={`flex items-center space-x-3 ${className}`}>
      {/* Official CryptoTracer Thick Segmented C-Shield + Pillar + Glowing 3-Node Trace */}
      <svg
        width="46"
        height="46"
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0 drop-shadow-[0_0_10px_rgba(121,226,130,0.35)]"
      >
        <defs>
          <linearGradient id="ctOuterGrad" x1="15" y1="10" x2="75" y2="90" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#89F792" />
            <stop offset="55%" stopColor="#48B88A" />
            <stop offset="100%" stopColor="#1D6A6B" />
          </linearGradient>
          <linearGradient id="ctInnerGrad" x1="25" y1="25" x2="65" y2="85" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#79E282" />
            <stop offset="100%" stopColor="#26736E" />
          </linearGradient>
          <filter id="ctNodeGlow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Top Outer C Segment */}
        <path d="M 76 23 A 40 40 0 0 0 11 46 L 23 46 A 28 28 0 0 1 67 32 Z" fill="url(#ctOuterGrad)" />
        {/* Bottom Outer C Segment */}
        <path d="M 11 51 A 40 40 0 0 0 45 90 L 45 77 A 28 28 0 0 1 23 51 Z" fill="url(#ctOuterGrad)" />
        {/* Inner Top Arc */}
        <path d="M 52 27 A 24 24 0 0 0 26 46 L 34 46 A 16 16 0 0 1 48 34 Z" fill="#5CE085" />
        {/* Inner Bottom Arc */}
        <path d="M 26 51 A 24 24 0 0 0 45 73 L 45 64 A 16 16 0 0 1 34 51 Z" fill="#287672" />
        {/* Center Vertical Pillar */}
        <path d="M 49 52 L 49 90 L 61 84 L 61 60 L 69 52 L 65 46 L 55 46 Z" fill="url(#ctInnerGrad)" />
        {/* Glowing Circuit Trace Node & Line */}
        <g filter="url(#ctNodeGlow)">
          <path d="M 48 46 L 63 37 L 82 51" stroke="#79E282" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="45" cy="48" r="5.5" fill="var(--bg-card, #11171A)" stroke="#89F792" strokeWidth="4" />
          <circle cx="63" cy="37" r="4.5" fill="var(--bg-card, #11171A)" stroke="#5CE085" strokeWidth="3.5" />
          <circle cx="85" cy="53" r="5" fill="var(--bg-card, #11171A)" stroke="#48B88A" strokeWidth="3.8" />
        </g>
      </svg>

      {!iconOnly && (
        <div className="flex flex-col">
          <div className="flex items-center">
            <span className="text-xl font-extrabold tracking-tight text-[var(--text-primary)]">
              Crypto<span className="text-[var(--accent-primary)]">Tracer</span>
            </span>
          </div>
          <span className="text-[9px] tracking-[0.22em] font-semibold text-[var(--text-muted)] uppercase leading-tight">
            REAL-TIME CRYPTO FRAUD ATTRIBUTION
          </span>
        </div>
      )}
    </div>
  );
};

export default CryptoTracerLogo;
