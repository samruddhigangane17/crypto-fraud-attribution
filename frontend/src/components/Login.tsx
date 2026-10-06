import { useState } from 'react';
import { supabase } from '../lib/supabase';
import { Lock, Mail } from 'lucide-react';
import CryptoTracerLogo from './CryptoTracerLogo';

export default function Login() {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

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
    <div className="min-h-screen bg-[#0B0B0D] flex flex-col justify-center py-12 sm:px-6 lg:px-8 font-['Montserrat']">
      <div className="sm:mx-auto sm:w-full sm:max-w-md flex flex-col items-center">
        <CryptoTracerLogo className="mb-4 scale-110" />
        <h2 className="mt-4 text-center text-2xl font-bold tracking-tight text-[#E8EEEB]">
          {isSignUp ? 'Create Investigator Credential' : 'Sign in to Forensic Console'}
        </h2>
        <p className="mt-1 text-xs text-[#899695] text-center">
          Cryptographically authenticated workspace for cryptocurrency fraud attribution
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-[#11171A] py-8 px-6 shadow-2xl rounded-2xl border border-[#243338] sm:px-10">
          <form className="space-y-5" onSubmit={handleAuth}>
            {error && (
              <div className="bg-[#D95F63]/10 border border-[#D95F63]/30 text-[#D95F63] px-3.5 py-2.5 rounded-xl text-xs" role="alert">
                <span className="block sm:inline">{error}</span>
              </div>
            )}

            {message && (
              <div className="bg-[#79E282]/10 border border-[#79E282]/30 text-[#79E282] px-3.5 py-2.5 rounded-xl text-xs" role="alert">
                <span className="block sm:inline">{message}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[#899695]">
                Officer / Investigator Email
              </label>
              <div className="mt-1.5 relative rounded-xl shadow-inner">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                  <Mail className="h-4 w-4 text-[#899695]" />
                </div>
                <input
                  type="email"
                  required
                  className="pl-10 w-full bg-[#182124] border border-[#243338] rounded-xl p-2.5 text-xs text-[#E8EEEB] focus:ring-2 focus:ring-[#79E282] focus:border-[#79E282] font-mono shadow-inner"
                  placeholder="investigator@agency.gov"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[#899695]">
                Security Password
              </label>
              <div className="mt-1.5 relative rounded-xl shadow-inner">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                  <Lock className="h-4 w-4 text-[#899695]" />
                </div>
                <input
                  type="password"
                  required
                  className="pl-10 w-full bg-[#182124] border border-[#243338] rounded-xl p-2.5 text-xs text-[#E8EEEB] focus:ring-2 focus:ring-[#79E282] focus:border-[#79E282] font-mono shadow-inner"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center py-3 px-4 rounded-xl shadow-lg text-xs font-bold text-[#0B0B0D] bg-[#79E282] hover:bg-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#79E282] disabled:bg-[#368980]/40 disabled:text-[#899695] transition-colors"
            >
              {loading ? (isSignUp ? 'Registering Credential...' : 'Authenticating Session...') : (isSignUp ? 'Create Account' : 'Authenticate Session')}
            </button>
          </form>

          <div className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-[#1C272A]" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="px-2 bg-[#11171A] text-[#899695] uppercase tracking-wider text-[10px]">Or</span>
              </div>
            </div>

            <div className="mt-6">
              <button
                type="button"
                onClick={() => {
                  setIsSignUp(!isSignUp);
                  setError(null);
                  setMessage(null);
                }}
                className="w-full flex justify-center py-2.5 px-4 border border-[#243338] rounded-xl text-xs font-medium text-[#899695] bg-[#182124] hover:text-[#79E282] hover:bg-[#1F2B2F] transition-colors"
              >
                {isSignUp ? 'Already have an authenticated account? Sign in' : "Register new investigator account"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
