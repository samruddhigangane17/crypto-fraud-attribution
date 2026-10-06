import { useState, useEffect, useRef } from 'react';
import { supabase } from '../lib/supabase';
import { Lock, Mail, Sun, Moon, Shield } from 'lucide-react';
import CryptoTracerLogo from './CryptoTracerLogo';

export default function Login() {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  // Theme Toggle for Login Page
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try {
      return (localStorage.getItem('cryptotracer_theme') as 'dark' | 'light') || 'dark';
    } catch {
      return 'dark';
    }
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('cryptotracer_theme', theme);
    } catch {}
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  // 3D Cyber-Forensic Sphere Canvas Animation
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);

    // Generate 3D sphere points (Fibonacci sphere algorithm)
    const NUM_NODES = 85;
    const SPHERE_RADIUS = Math.min(width, height) * 0.38;
    const nodes: Array<{ x: number; y: number; z: number; size: number; color: string }> = [];

    const phi = Math.PI * (3 - Math.sqrt(5)); // Golden angle
    for (let i = 0; i < NUM_NODES; i++) {
      const y = 1 - (i / (NUM_NODES - 1)) * 2; // -1 to 1
      const radiusAtY = Math.sqrt(1 - y * y);
      const theta = phi * i;
      const x = Math.cos(theta) * radiusAtY;
      const z = Math.sin(theta) * radiusAtY;

      nodes.push({
        x: x * SPHERE_RADIUS,
        y: y * SPHERE_RADIUS,
        z: z * SPHERE_RADIUS,
        size: Math.random() * 2 + 2,
        color: i % 3 === 0 ? '#79E282' : i % 3 === 1 ? '#368980' : '#38BDF8',
      });
    }

    // Edges between nearby nodes
    const edges: Array<[number, number]> = [];
    for (let i = 0; i < NUM_NODES; i++) {
      for (let j = i + 1; j < NUM_NODES; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dz = nodes[i].z - nodes[j].z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist < SPHERE_RADIUS * 0.48) {
          edges.push([i, j]);
        }
      }
    }

    // Moving transaction packets along edges
    const packets = edges.slice(0, 30).map((edge) => ({
      edge,
      progress: Math.random(),
      speed: 0.004 + Math.random() * 0.006,
    }));

    let angleY = 0;
    const angleX = 0.22; // fixed gentle tilt

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;
      angleY += 0.003;

      const cosY = Math.cos(angleY);
      const sinY = Math.sin(angleY);
      const cosX = Math.cos(angleX);
      const sinX = Math.sin(angleX);

      // Rotate nodes in 3D
      const projected = nodes.map((node) => {
        // Rotate Y
        const x1 = node.x * cosY - node.z * sinY;
        const z1 = node.z * cosY + node.x * sinY;
        // Rotate X
        const y2 = node.y * cosX - z1 * sinX;
        const z2 = z1 * cosX + node.y * sinX;

        // Perspective projection
        const cameraDistance = SPHERE_RADIUS * 2.5;
        const scale = cameraDistance / (cameraDistance + z2);
        return {
          px: cx + x1 * scale,
          py: cy + y2 * scale,
          pz: z2,
          scale,
          color: node.color,
          size: node.size * scale,
        };
      });

      // Draw faint wireframe sphere rings
      ctx.save();
      ctx.strokeStyle = theme === 'dark' ? 'rgba(121, 226, 130, 0.04)' : 'rgba(15, 118, 110, 0.06)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, SPHERE_RADIUS, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // Draw edges
      ctx.lineWidth = 0.8;
      edges.forEach(([i, j]) => {
        const p1 = projected[i];
        const p2 = projected[j];

        // Depth fogging
        const avgZ = (p1.pz + p2.pz) / 2;
        const alpha = Math.max(0.04, Math.min(0.4, (avgZ + SPHERE_RADIUS) / (2 * SPHERE_RADIUS) * 0.4));

        ctx.strokeStyle = theme === 'dark' ? `rgba(121, 226, 130, ${alpha})` : `rgba(15, 118, 110, ${alpha * 0.8})`;
        ctx.beginPath();
        ctx.moveTo(p1.px, p1.py);
        ctx.lineTo(p2.px, p2.py);
        ctx.stroke();
      });

      // Draw moving transaction pulse packets
      packets.forEach((pkt) => {
        pkt.progress += pkt.speed;
        if (pkt.progress > 1) pkt.progress = 0;

        const p1 = projected[pkt.edge[0]];
        const p2 = projected[pkt.edge[1]];

        const x = p1.px + (p2.px - p1.px) * pkt.progress;
        const y = p1.py + (p2.py - p1.py) * pkt.progress;
        const avgZ = (p1.pz + p2.pz) / 2;

        if (avgZ > -SPHERE_RADIUS * 0.5) {
          ctx.fillStyle = '#79E282';
          ctx.shadowColor = '#79E282';
          ctx.shadowBlur = 8;
          ctx.beginPath();
          ctx.arc(x, y, 2.2, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;
        }
      });

      // Draw nodes sorted by Z (back to front)
      const sortedIndices = projected.map((_, i) => i).sort((a, b) => projected[a].pz - projected[b].pz);

      sortedIndices.forEach((idx) => {
        const p = projected[idx];
        const alpha = Math.max(0.2, (p.pz + SPHERE_RADIUS) / (2 * SPHERE_RADIUS));

        ctx.save();
        ctx.fillStyle = p.color;
        ctx.globalAlpha = alpha;
        ctx.shadowColor = p.color;
        ctx.shadowBlur = p.pz > 0 ? 10 : 2;

        ctx.beginPath();
        ctx.arc(p.px, p.py, Math.max(1.5, p.size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
    };
  }, [theme]);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);

    if (isSignUp) {
      const { error } = await supabase.auth.signUp({
        email,
        password,
      });

      if (error) {
        setError(error.message);
      } else {
        setMessage('Registration successful! You can now sign in.');
        setIsSignUp(false);
      }
    } else {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        setError(error.message);
      }
    }
    setLoading(false);
  };

  return (
    <div className="relative min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] flex items-center justify-center p-4 sm:p-6 overflow-hidden font-['Montserrat']">
      {/* 3D Cyber-Forensic Sphere Canvas Backdrop */}
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none z-0" />

      {/* Top Navbar / Theme Switcher */}
      <div className="absolute top-5 right-5 z-20 flex items-center space-x-3">
        <button
          onClick={toggleTheme}
          className="flex items-center space-x-2 px-3 py-1.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)]/80 backdrop-blur-md text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all shadow-sm"
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
        >
          {theme === 'dark' ? (
            <>
              <Sun className="h-4 w-4 text-[#E6A94A]" />
              <span className="text-xs font-semibold hidden sm:inline">Light</span>
            </>
          ) : (
            <>
              <Moon className="h-4 w-4 text-[#0F766E]" />
              <span className="text-xs font-semibold hidden sm:inline">Dark</span>
            </>
          )}
        </button>
      </div>

      {/* 4 3D Extruded Metallic Coins Floating in Corners */}
      {/* 1. Top-Left: Bitcoin (BTC) */}
      <div className="hidden lg:flex absolute top-12 left-12 z-10 flex-col items-center animate-float-1 pointer-events-none select-none">
        <div className="w-20 h-20 rounded-full border-4 border-[#FBBF24] shadow-2xl flex items-center justify-center animate-coin-spin"
          style={{
            background: 'radial-gradient(circle at 35% 30%, #FFFFFF 0%, transparent 40%), linear-gradient(135deg, #F59E0B 0%, #78350F 100%)',
            boxShadow: '0 12px 28px rgba(245, 158, 11, 0.35)',
          }}
        >
          <span className="text-2xl font-black text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]">₿</span>
        </div>
        <div className="mt-2 text-center">
          <span className="text-[11px] font-mono font-bold text-[var(--text-primary)] block">Bitcoin BTC</span>
          <span className="text-[9px] text-[var(--text-muted)] font-mono">UTXO Clustering</span>
        </div>
      </div>

      {/* 2. Top-Right: Ethereum (ETH) */}
      <div className="hidden lg:flex absolute top-12 right-24 z-10 flex-col items-center animate-float-2 pointer-events-none select-none">
        <div className="w-20 h-20 rounded-full border-4 border-[#818CF8] shadow-2xl flex items-center justify-center animate-coin-spin"
          style={{
            background: 'radial-gradient(circle at 35% 30%, #FFFFFF 0%, transparent 40%), linear-gradient(135deg, #6366F1 0%, #312E81 100%)',
            boxShadow: '0 12px 28px rgba(99, 102, 241, 0.35)',
          }}
        >
          <svg className="w-8 h-8 text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]" viewBox="0 0 256 417" fill="currentColor">
            <path d="M127.961 0l-2.795 9.5v275.668l2.795 2.79 127.962-75.638z" fillOpacity="0.9" />
            <path d="M127.962 0L0 212.32l127.962 75.639V0z" fillOpacity="0.7" />
            <path d="M127.961 312.187l-1.575 1.92v100.088l1.575 4.605 128.038-179.99z" fillOpacity="0.9" />
            <path d="M127.962 418.8lV312.187L0 238.805z" fillOpacity="0.7" />
          </svg>
        </div>
        <div className="mt-2 text-center">
          <span className="text-[11px] font-mono font-bold text-[var(--text-primary)] block">Ethereum ETH</span>
          <span className="text-[9px] text-[var(--text-muted)] font-mono">ERC-20 & Mixers</span>
        </div>
      </div>

      {/* 3. Bottom-Left: TRON (TRX) */}
      <div className="hidden lg:flex absolute bottom-12 left-16 z-10 flex-col items-center animate-float-3 pointer-events-none select-none">
        <div className="w-20 h-20 rounded-full border-4 border-[#F87171] shadow-2xl flex items-center justify-center animate-coin-spin"
          style={{
            background: 'radial-gradient(circle at 35% 30%, #FFFFFF 0%, transparent 40%), linear-gradient(135deg, #EF4444 0%, #7F1D1D 100%)',
            boxShadow: '0 12px 28px rgba(239, 68, 68, 0.35)',
          }}
        >
          <svg className="w-7 h-7 text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]" viewBox="0 0 32 32" fill="currentColor">
            <path d="M29.5 7.5L2.5 3.5l10 24.5 17-20.5zm-3.2 2.6L14.7 20.3 6.4 5.9l19.9 4.2z" />
          </svg>
        </div>
        <div className="mt-2 text-center">
          <span className="text-[11px] font-mono font-bold text-[var(--text-primary)] block">TRON TRX</span>
          <span className="text-[9px] text-[var(--text-muted)] font-mono">USDT-TRC20 Velocity</span>
        </div>
      </div>

      {/* 4. Bottom-Right: BNB Chain (BSC) */}
      <div className="hidden lg:flex absolute bottom-12 right-16 z-10 flex-col items-center animate-float-4 pointer-events-none select-none">
        <div className="w-20 h-20 rounded-full border-4 border-[#FACC15] shadow-2xl flex items-center justify-center animate-coin-spin"
          style={{
            background: 'radial-gradient(circle at 35% 30%, #FFFFFF 0%, transparent 40%), linear-gradient(135deg, #EAB308 0%, #713F12 100%)',
            boxShadow: '0 12px 28px rgba(234, 179, 8, 0.35)',
          }}
        >
          <svg className="w-7 h-7 text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]" viewBox="0 0 32 32" fill="currentColor">
            <path d="M16 4l4 4-4 4-4-4 4-4zm8 8l4 4-4 4-4-4 4-4zm-16 0l4 4-4 4-4-4 4-4zm8 8l4 4-4 4-4-4 4-4z" />
          </svg>
        </div>
        <div className="mt-2 text-center">
          <span className="text-[11px] font-mono font-bold text-[var(--text-primary)] block">BNB Chain BSC</span>
          <span className="text-[9px] text-[var(--text-muted)] font-mono">DEX Liquidity</span>
        </div>
      </div>

      {/* Main Glassmorphic Sign-In Card */}
      <div className="relative z-10 w-full max-w-md">
        <div className="bg-[var(--bg-card)]/85 backdrop-blur-xl py-8 px-6 sm:px-10 shadow-2xl rounded-3xl border border-[var(--border-color)] transition-all duration-300">
          <div className="flex flex-col items-center mb-6">
            <CryptoTracerLogo className="mb-3 scale-105" />
            <h2 className="text-center text-xl font-extrabold tracking-tight text-[var(--text-primary)]">
              {isSignUp ? 'Create Forensic Credential' : 'Sign in to Forensic Console'}
            </h2>
            <p className="mt-1 text-xs text-[var(--text-muted)] text-center leading-relaxed">
              Cryptographically authenticated workspace for cryptocurrency fraud attribution
            </p>
          </div>

          <form className="space-y-4" onSubmit={handleAuth}>
            {error && (
              <div className="bg-[var(--status-critical)]/10 border border-[var(--status-critical)]/30 text-[var(--status-critical)] px-3.5 py-2.5 rounded-xl text-xs" role="alert">
                <span className="block sm:inline">{error}</span>
              </div>
            )}

            {message && (
              <div className="bg-[var(--accent-primary)]/10 border border-[var(--accent-primary)]/30 text-[var(--accent-primary)] px-3.5 py-2.5 rounded-xl text-xs" role="alert">
                <span className="block sm:inline">{message}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                Officer / Investigator Email
              </label>
              <div className="relative rounded-xl">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                  <Mail className="h-4 w-4 text-[var(--text-muted)]" />
                </div>
                <input
                  type="email"
                  required
                  className="pl-10 w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl p-2.5 text-xs text-[var(--text-primary)] focus:ring-2 focus:ring-[var(--accent-primary)] focus:border-[var(--accent-primary)] font-mono transition-all"
                  placeholder="investigator@agency.gov"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                Security Password
              </label>
              <div className="relative rounded-xl">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                  <Lock className="h-4 w-4 text-[var(--text-muted)]" />
                </div>
                <input
                  type="password"
                  required
                  className="pl-10 w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl p-2.5 text-xs text-[var(--text-primary)] focus:ring-2 focus:ring-[var(--accent-primary)] focus:border-[var(--accent-primary)] font-mono transition-all"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 flex justify-center items-center py-3 px-4 rounded-xl shadow-lg text-xs font-bold text-[var(--bg-card)] bg-[var(--accent-primary)] hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] disabled:opacity-50 transition-all cursor-pointer"
            >
              <Shield className="h-4 w-4 mr-2" />
              {loading ? (isSignUp ? 'Registering Credential...' : 'Authenticating Session...') : (isSignUp ? 'Create Investigator Credential' : 'Authenticate Forensic Session')}
            </button>
          </form>

          <div className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-[var(--border-color)]" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="px-2 bg-[var(--bg-card)] text-[var(--text-muted)] uppercase tracking-wider text-[10px]">
                  Access Control
                </span>
              </div>
            </div>

            <div className="mt-4">
              <button
                type="button"
                onClick={() => {
                  setIsSignUp(!isSignUp);
                  setError(null);
                  setMessage(null);
                }}
                className="w-full flex justify-center py-2.5 px-4 border border-[var(--border-color)] rounded-xl text-xs font-semibold text-[var(--text-muted)] bg-[var(--bg-secondary)] hover:text-[var(--accent-primary)] hover:border-[var(--accent-primary)] transition-all cursor-pointer"
              >
                {isSignUp ? 'Already have an authenticated account? Sign in' : "Register new investigator credential"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
