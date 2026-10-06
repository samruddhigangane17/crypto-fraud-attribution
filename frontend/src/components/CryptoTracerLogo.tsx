import React from 'react';

interface CryptoTracerLogoProps {
  className?: string;
  iconOnly?: boolean;
}

export const CryptoTracerLogo: React.FC<CryptoTracerLogoProps> = ({ className = '', iconOnly = false }) => {
  return (
    <div className={`flex items-center space-x-3 ${className}`}>
      {/* Segmented C-Ring + 3-Node Circuit Trace Vector Mark */}
      <div className="relative flex-shrink-0 flex items-center justify-center">
        <svg
          className="w-10 h-10 drop-shadow-[0_0_8px_rgba(121,226,130,0.45)]"
          viewBox="0 0 48 48"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="ctGradient" x1="4" y1="4" x2="44" y2="44" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#79E282" />
              <stop offset="100%" stopColor="#368980" />
            </linearGradient>
            <linearGradient id="pulseGrad" x1="12" y1="24" x2="36" y2="24" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#79E282" />
              <stop offset="100%" stopColor="#38BDF8" />
            </linearGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Segmented Outer C-Ring (Arc with open right side) */}
          <path
            d="M 36 12 A 18 18 0 1 0 36 36"
            stroke="url(#ctGradient)"
            strokeWidth="3.5"
            strokeLinecap="round"
          />

          {/* Upper decorative segment dash */}
          <path
            d="M 40 18 A 18 18 0 0 0 38 14"
            stroke="#79E282"
            strokeWidth="2.5"
            strokeLinecap="round"
            opacity="0.7"
          />

          {/* Inner 3-Node Forward Circuit Trace */}
          {/* Edge 1: Origin to Upper Hop */}
          <path
            d="M 17 24 L 24 17 L 32 17"
            stroke="url(#pulseGrad)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="2 1"
          />
          {/* Edge 2: Origin to Lower Hop */}
          <path
            d="M 17 24 L 24 31 L 32 31"
            stroke="url(#pulseGrad)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="2 1"
          />

          {/* Node 1: Origin Wallet */}
          <circle cx="17" cy="24" r="3.2" fill="#0B0B0D" stroke="#79E282" strokeWidth="2.2" />
          <circle cx="17" cy="24" r="1.2" fill="#79E282" />

          {/* Node 2: Intermediate Hop */}
          <circle cx="32" cy="17" r="2.8" fill="#0B0B0D" stroke="#38BDF8" strokeWidth="2" />
          <circle cx="32" cy="17" r="1" fill="#38BDF8" />

          {/* Node 3: Attributed Endpoint */}
          <circle cx="32" cy="31" r="3.2" fill="#79E282" stroke="#E8EEEB" strokeWidth="1.5" filter="url(#glow)" />
        </svg>
      </div>

      {!iconOnly && (
        <div className="flex flex-col">
          <div className="flex items-center space-x-1">
            <span className="text-xl font-extrabold tracking-tight text-[#E8EEEB]">
              Crypto<span className="text-[#79E282]">Tracer</span>
            </span>
            <span className="h-1.5 w-1.5 rounded-full bg-[#79E282] animate-pulse" />
          </div>
          <span className="text-[8.5px] font-bold tracking-[0.22em] text-[#899695] uppercase leading-tight">
            Real-Time Crypto Fraud Attribution
          </span>
        </div>
      )}
    </div>
  );
};

export default CryptoTracerLogo;
