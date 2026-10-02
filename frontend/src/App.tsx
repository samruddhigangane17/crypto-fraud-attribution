import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Activity, ShieldAlert, FileText, Share2, Search } from 'lucide-react';
import NewInvestigation from './components/NewInvestigation';
import FundFlowGraph from './components/FundFlowGraph';
import RiskAttribution from './components/RiskAttribution';
import MonitoringAlerts from './components/MonitoringAlerts';
import EvidenceReport from './components/EvidenceReport';

function Dashboard() {
  const [activeCase, setActiveCase] = useState<string | null>(null);

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
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b border-gray-200 p-4 flex justify-between items-center">
          <h2 className="text-lg font-medium text-gray-800">Investigator Dashboard</h2>
          <div className="text-sm text-gray-500">
            {activeCase ? `Active Case: ${activeCase}` : 'No active case'}
          </div>
        </header>
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
  return (
    <Router>
      <Dashboard />
    </Router>
  );
}

export default App;
