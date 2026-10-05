import { useEffect, useState } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import { apiJson } from '../lib/api';
import { Play, RefreshCw, AlertCircle } from 'lucide-react';

interface FundFlowGraphProps {
  activeCase: string | null;
}

interface InvestigationInfo {
  id: string;
  status: string;
  chain?: string;
  reported_address?: string;
  data_source?: string | null;
  notice?: string | null;
  created_at?: string;
}

const FundFlowGraph: React.FC<FundFlowGraphProps> = ({ activeCase }) => {
  const [elements, setElements] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [isTracing, setIsTracing] = useState(false);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [traceError, setTraceError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [caseInfo, setCaseInfo] = useState<InvestigationInfo | null>(null);

  const loadGraph = async () => {
    if (!activeCase) return;
    setLoading(true);
    setError(null);
    setTraceError(null);
    setNotice(null);

    // 1. Fetch investigation metadata
    try {
      const c = await apiJson<InvestigationInfo>(`/api/investigations/${activeCase}`);
      setCaseInfo(c);
      setNotice(c.notice ?? null);
      if (c.status === 'Reported') {
        // Case has not been traced yet
        setElements([]);
        setLoading(false);
        return;
      }
    } catch {
      // Continue to graph fetch
    }

    // 2. Fetch graph data
    try {
      const data = await apiJson(`/api/investigations/${activeCase}/graph`);
      const cytoscapeElements = [
        ...data.nodes.map((n: any) => ({ data: n.data })),
        ...data.edges.map((e: any) => ({ data: e.data })),
      ];
      setElements(cytoscapeElements);
    } catch (err: any) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGraph();
  }, [activeCase]);

  const handleStartTrace = async () => {
    if (!activeCase) return;
    setIsTracing(true);
    setTraceError(null);
    try {
      const startTime = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
      const traced = await apiJson(`/api/investigations/${activeCase}/trace`, {
        method: 'POST',
        body: JSON.stringify({
          max_hops: 5,
          min_taint_share: 0.05,
          start_time: startTime,
        }),
      });

      if (traced.notice) {
        setNotice(traced.notice);
      }

      // Re-fetch graph data
      const data = await apiJson(`/api/investigations/${activeCase}/graph`);
      const cytoscapeElements = [
        ...data.nodes.map((n: any) => ({ data: n.data })),
        ...data.edges.map((e: any) => ({ data: e.data })),
      ];
      setElements(cytoscapeElements);

      // Re-fetch case metadata to reflect status: 'completed'
      const updated = await apiJson<InvestigationInfo>(`/api/investigations/${activeCase}`);
      setCaseInfo(updated);
      setError(null);
    } catch (err: any) {
      setTraceError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsTracing(false);
    }
  };

  if (!activeCase) {
    return <div className="p-8 text-center text-gray-500">No active case selected. Please start an investigation.</div>;
  }

  // Detect whether this case has not been traced yet
  const isUntraced =
    (caseInfo && caseInfo.status === 'Reported' && elements.length === 0) ||
    Boolean(error && error.toLowerCase().includes('tracing has not been executed'));

  if (isUntraced) {
    return (
      <div className="max-w-2xl mx-auto my-8 bg-white p-8 rounded-lg shadow-sm border border-gray-200 text-center">
        <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <Play className="h-6 w-6 ml-0.5" />
        </div>
        <h3 className="text-xl font-bold text-gray-800 mb-2">Tracing Has Not Been Executed</h3>
        <p className="text-sm text-gray-600 mb-6 max-w-md mx-auto">
          This investigation was registered with status <strong>Reported</strong> (e.g. from a bulk CSV feed), but
          blockchain transaction tracing has not been performed yet. Start multi-hop tracing to analyze fund flows
          and construct the transaction graph.
        </p>

        {caseInfo && (
          <div className="bg-gray-50 border border-gray-200 rounded-md p-4 mb-6 text-left max-w-md mx-auto text-xs space-y-1.5 font-mono">
            <div className="flex justify-between">
              <span className="text-gray-500">Case ID:</span>
              <span className="font-semibold text-gray-800">{activeCase}</span>
            </div>
            {caseInfo.chain && (
              <div className="flex justify-between">
                <span className="text-gray-500">Blockchain:</span>
                <span className="font-semibold text-indigo-600 uppercase">{caseInfo.chain}</span>
              </div>
            )}
            {caseInfo.reported_address && (
              <div className="flex justify-between">
                <span className="text-gray-500">Reported Address:</span>
                <span className="font-semibold text-gray-800 truncate max-w-[220px]" title={caseInfo.reported_address}>
                  {caseInfo.reported_address}
                </span>
              </div>
            )}
          </div>
        )}

        {traceError && (
          <div className="mb-6 p-4 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm text-left max-w-md mx-auto flex items-start space-x-2">
            <AlertCircle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
            <span>{traceError}</span>
          </div>
        )}

        <button
          onClick={handleStartTrace}
          disabled={isTracing}
          className="inline-flex items-center px-6 py-2.5 bg-indigo-600 text-white font-medium text-sm rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-indigo-300 disabled:cursor-not-allowed shadow-sm transition-colors"
        >
          {isTracing ? (
            <>
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              Tracing Transactions (up to 5 hops)...
            </>
          ) : (
            <>
              <Play className="h-4 w-4 mr-2" />
              Start Trace
            </>
          )}
        </button>
      </div>
    );
  }

  if (error) {
    return <div className="p-4 bg-red-50 text-red-700 border border-red-200 rounded-md">{error}</div>;
  }

  if (!loading && elements.length === 0 && notice) {
    return <div className="p-4 bg-amber-50 text-amber-800 border border-amber-200 rounded-md">{notice}</div>;
  }

  const layout = { name: 'breadthfirst', directed: true, spacingFactor: 1.5 };
  const style = [
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'text-valign': 'bottom' as any,
        'background-color': '#4f46e5',
        'color': '#1f2937',
        'font-size': '12px'
      }
    },
    {
      selector: 'node[type="victim"]',
      style: { 'background-color': '#ef4444' }
    },
    {
      selector: 'node[type="exchange"]',
      style: { 'background-color': '#10b981', 'shape': 'rectangle' as any }
    },
    {
      selector: 'edge',
      style: {
        'width': 2,
        'line-color': '#9ca3af',
        'target-arrow-color': '#9ca3af',
        'target-arrow-shape': 'triangle' as any,
        'curve-style': 'bezier' as any,
        'label': 'data(amount)',
        'font-size': '10px'
      }
    }
  ];

  return (
    <div className="flex h-full gap-4">
      <div className="flex-1 bg-white border border-gray-200 rounded-lg overflow-hidden flex flex-col relative">
        <div className="p-4 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
          <h3 className="font-semibold text-gray-800">Transaction Graph</h3>
          <span className="text-sm text-gray-500">{elements.length} elements</span>
        </div>
        {loading ? (
          <div className="flex-1 flex items-center justify-center">Loading graph...</div>
        ) : (
          <div className="flex-1 bg-gray-50">
            <CytoscapeComponent 
              elements={elements} 
              style={{ width: '100%', height: '100%' }} 
              layout={layout}
              stylesheet={style}
              cy={(cy) => {
                cy.on('tap', 'node', (evt) => {
                  setSelectedNode(evt.target.data());
                });
                cy.on('tap', 'edge', (evt) => {
                  setSelectedNode(evt.target.data());
                });
              }}
            />
          </div>
        )}
      </div>
      
      {selectedNode && (
        <div className="w-80 bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-800 mb-4 border-b pb-2">Details</h3>
          <div className="space-y-3 text-sm">
            {Object.entries(selectedNode).map(([k, v]) => (
              <div key={k}>
                <span className="text-gray-500 block text-xs uppercase tracking-wider">{k}</span>
                <span className="font-medium text-gray-900 break-all">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FundFlowGraph;
