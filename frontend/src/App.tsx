import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Activity, ShieldAlert, FileText, Share2, Search, LogOut } from 'lucide-react';
import { supabase } from './lib/supabase';
import { apiJson } from './lib/api';
import type { Session } from '@supabase/supabase-js';

import Login from './components/Login';
import NewInvestigation from './components/NewInvestigation';
import FundFlowGraph from './components/FundFlowGraph';
import RiskAttribution from './components/RiskAttribution';
import MonitoringAlerts from './components/MonitoringAlerts';
import EvidenceReport from './components/EvidenceReport';

function Dashboard({ session }: { session: Session }) {
  const [activeCase, setActiveCase] = useState<string | null>(null);
  const [dataSource, setDataSource] = useState<string | null>(null);

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
            <div className="text-sm text-gray-500">
              {activeCase ? `Active Case: ${activeCase}` : 'No active case'}
            </div>
            <div className="text-sm font-medium text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full">
              {session.user.email}
            </div>
          </div>
        </header>
        {dataSource === 'mock' && (
          <div className="bg-yellow-100 border-b border-yellow-300 text-yellow-900 text-sm px-4 py-2">
            <strong>DEMO DATA:</strong> this case uses built-in mock transactions, not live blockchain data.
            Addresses, exchange labels and amounts are fake.
          </div>
        )}
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<NewInvestigation setActiveCase={setActiveCase} activeCase={activeCase} />} />
            <Route path="/graph" element={<FundFlowGraph activeCase={activeCase} />} />
            <Route path="/risk" element={<RiskAttribution activeCase={activeCase} />} />
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
