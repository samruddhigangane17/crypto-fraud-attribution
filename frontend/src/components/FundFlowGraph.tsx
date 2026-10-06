import { useEffect, useState } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import { apiJson } from '../lib/api';
import { Play, RefreshCw, AlertCircle, Box, Layers, Info, Compass } from 'lucide-react';

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
  const [is3DView, setIs3DView] = useState(false);

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
        setElements([]);
        setLoading(false);
        return;
      }
    } catch {}

    // 2. Fetch graph elements
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

      const data = await apiJson(`/api/investigations/${activeCase}/graph`);
      const cytoscapeElements = [
        ...data.nodes.map((n: any) => ({ data: n.data })),
        ...data.edges.map((e: any) => ({ data: e.data })),
      ];
      setElements(cytoscapeElements);

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
    return (
      <div className="p-12 text-center text-[var(--text-muted)] bg-[var(--bg-card)] rounded-2xl border border-[var(--border-color)] max-w-xl mx-auto my-12">
        <Compass className="h-10 w-10 text-[#79E282] mx-auto mb-3 animate-spin" />
        <h3 className="text-base font-bold text-[var(--text-primary)]">No Active Case Loaded</h3>
        <p className="text-xs mt-1">Please select an investigation from the top console or initiate a new trace.</p>
      </div>
    );
  }

  const isUntraced =
    (caseInfo && caseInfo.status === 'Reported' && elements.length === 0) ||
    Boolean(error && error.toLowerCase().includes('tracing has not been executed'));

  if (isUntraced) {
    return (
      <div className="max-w-2xl mx-auto my-10 bg-[var(--bg-card)] p-8 rounded-2xl shadow-xl border border-[var(--border-color)] text-center transition-colors">
        <div className="w-14 h-14 bg-[#79E282]/10 text-[#79E282] rounded-full flex items-center justify-center mx-auto mb-4 border border-[#79E282]/30">
          <Play className="h-6 w-6 ml-0.5" />
        </div>
        <h3 className="text-xl font-bold text-[var(--text-primary)] mb-2">Forward Tracing Pending</h3>
        <p className="text-xs text-[var(--text-muted)] mb-6 max-w-md mx-auto leading-relaxed">
          This investigation was registered as <strong>Reported</strong>. Execute automated multi-hop forward tracing
          to reconstruct transaction flow paths, identify intermediary mule wallets, and attribute VASP off-ramps.
        </p>

        {caseInfo && (
          <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-xl p-4 mb-6 text-left max-w-md mx-auto text-xs space-y-2 font-mono">
            <div className="flex justify-between">
              <span className="text-[var(--text-muted)]">Investigation ID:</span>
              <span className="font-bold text-[var(--text-primary)]">{activeCase}</span>
            </div>
            {caseInfo.chain && (
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Target Chain:</span>
                <span className="font-bold text-[#79E282] uppercase">{caseInfo.chain}</span>
              </div>
            )}
            {caseInfo.reported_address && (
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Reported Wallet:</span>
                <span className="font-bold text-[var(--text-primary)] truncate max-w-[200px]" title={caseInfo.reported_address}>
                  {caseInfo.reported_address}
                </span>
              </div>
            )}
          </div>
        )}

        {traceError && (
          <div className="mb-6 p-4 bg-[#D95F63]/10 text-[#D95F63] border border-[#D95F63]/30 rounded-xl text-xs text-left max-w-md mx-auto flex items-start space-x-2">
            <AlertCircle className="h-4 w-4 text-[#D95F63] shrink-0 mt-0.5" />
            <span>{traceError}</span>
          </div>
        )}

        <button
          onClick={handleStartTrace}
          disabled={isTracing}
          className="inline-flex items-center px-6 py-3 bg-[#79E282] text-[#0B0B0D] font-bold text-xs rounded-xl hover:bg-white disabled:bg-[#368980]/40 disabled:text-[#899695] shadow-lg shadow-[#79E282]/10 transition-colors"
        >
          {isTracing ? (
            <>
              <RefreshCw className="h-4 w-4 mr-2 animate-spin text-[#0B0B0D]" />
              Traversing Blockchain Graphs (up to 5 hops)...
            </>
          ) : (
            <>
              <Play className="h-4 w-4 mr-2" />
              Execute Live Forward Trace
            </>
          )}
        </button>
      </div>
    );
  }

  if (error) {
    return <div className="p-4 bg-[#D95F63]/10 text-[#D95F63] border border-[#D95F63]/30 rounded-xl text-xs">{error}</div>;
  }

  if (!loading && elements.length === 0 && notice) {
    return <div className="p-4 bg-[#E6A94A]/10 text-[#E6A94A] border border-[#E6A94A]/30 rounded-xl text-xs">{notice}</div>;
  }

  const layout = {
    name: 'breadthfirst',
    directed: true,
    spacingFactor: 1.6,
    avoidOverlap: true,
  };

  // Official CryptoTracer Cytoscape styling
  const style = [
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'text-valign': 'bottom' as any,
        'text-margin-y': 6,
        'background-color': '#368980',
        'color': '#E8EEEB',
        'font-family': 'Montserrat, sans-serif',
        'font-size': '11px',
        'font-weight': 600,
        'text-background-opacity': 0.8,
        'text-background-color': '#0B0B0D',
        'text-background-padding': '2px',
        'text-background-shape': 'roundrectangle' as any,
        'border-width': 2,
        'border-color': '#243338',
      },
    },
    {
      selector: 'node[type="victim"], node[type="source"]',
      style: {
        'background-color': '#D95F63', // Critical / Victim
        'border-color': '#FF8E92',
        'border-width': 3,
      },
    },
    {
      selector: 'node[type="exchange"], node[type="vasp"]',
      style: {
        'background-color': '#79E282', // Electric Mint / Exchange
        'shape': 'rectangle' as any,
        'border-color': '#FFFFFF',
        'border-width': 2,
      },
    },
    {
      selector: 'node[type="mixer"]',
      style: {
        'background-color': '#E6A94A', // Amber / Mixer
        'shape': 'diamond' as any,
        'border-color': '#FDE68A',
        'border-width': 2,
      },
    },
    {
      selector: 'node[type="bridge"]',
      style: {
        'background-color': '#38BDF8', // Sky Blue / Bridge
        'shape': 'hexagon' as any,
        'border-color': '#BAE6FD',
        'border-width': 2,
      },
    },
    {
      selector: 'edge',
      style: {
        'width': 2.5,
        'line-color': '#368980',
        'target-arrow-color': '#79E282',
        'target-arrow-shape': 'triangle' as any,
        'curve-style': 'bezier' as any,
        'label': 'data(amount)',
        'font-size': '10px',
        'font-family': 'JetBrains Mono, monospace',
        'color': '#79E282',
        'text-background-opacity': 0.85,
        'text-background-color': '#11171A',
        'text-background-padding': '2px',
      },
    },
  ];

  return (
    <div className="flex flex-col lg:flex-row h-full gap-5">
      {/* Graph Visualiser Container */}
      <div className="flex-1 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl overflow-hidden flex flex-col relative shadow-xl transition-all duration-300">
        {/* Header Controls */}
        <div className="p-4 bg-[var(--bg-surface)] border-b border-[var(--border-color)] flex flex-wrap justify-between items-center gap-3">
          <div className="flex items-center space-x-3">
            <div className="p-1.5 bg-[#79E282]/10 rounded-lg text-[#79E282]">
              <Layers className="h-4 w-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-[var(--text-primary)]">Transaction Topology Graph</h3>
              <p className="text-[11px] text-[var(--text-muted)] font-mono">
                {elements.length} Graph Elements Reconstructed
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {/* Legend Badges */}
            <div className="hidden sm:flex items-center space-x-2 text-[10px] font-mono">
              <span className="flex items-center text-[#D95F63]">
                <span className="h-2 w-2 rounded-full bg-[#D95F63] mr-1" /> Victim
              </span>
              <span className="flex items-center text-[#368980]">
                <span className="h-2 w-2 rounded-full bg-[#368980] mr-1" /> Intermediate
              </span>
              <span className="flex items-center text-[#E6A94A]">
                <span className="h-2 w-2 rotate-45 bg-[#E6A94A] mr-1" /> Mixer
              </span>
              <span className="flex items-center text-[#38BDF8]">
                <span className="h-2 w-2 bg-[#38BDF8] mr-1" /> Bridge
              </span>
              <span className="flex items-center text-[#79E282]">
                <span className="h-2 w-2 bg-[#79E282] mr-1" /> VASP
              </span>
            </div>

            {/* 2D / 3D Isometric Plane View Toggle */}
            <button
              onClick={() => setIs3DView(!is3DView)}
              className={`flex items-center space-x-1.5 px-3 py-1.5 text-xs font-bold rounded-lg border transition-all duration-200 ${
                is3DView
                  ? 'bg-[#79E282] text-[#0B0B0D] border-[#79E282] shadow-md shadow-[#79E282]/20'
                  : 'bg-[var(--bg-card)] text-[var(--text-muted)] border-[var(--border-color)] hover:text-[#79E282]'
              }`}
              title="Toggle between standard 2D and 3D isometric plane projection"
            >
              <Box className="h-3.5 w-3.5" />
              <span>{is3DView ? '3D Isometric Active' : '2D / 3D Plane View'}</span>
            </button>
          </div>
        </div>

        {/* Graph Canvas */}
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center space-y-2 text-xs font-mono text-[#79E282]">
            <RefreshCw className="h-6 w-6 animate-spin text-[#79E282]" />
            <span>RENDERING GRAPH TOPOLOGY...</span>
          </div>
        ) : (
          <div
            className={`flex-1 relative overflow-hidden bg-[var(--bg-main)] ${
              is3DView ? 'graph-3d-plane' : 'graph-2d-plane'
            }`}
            style={{
              backgroundImage: is3DView
                ? 'radial-gradient(circle at 50% 50%, rgba(121,226,130,0.08) 0%, transparent 70%), linear-gradient(rgba(36,51,56,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(36,51,56,0.3) 1px, transparent 1px)'
                : undefined,
              backgroundSize: is3DView ? '100% 100%, 30px 30px, 30px 30px' : undefined,
            }}
          >
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

      {/* Selected Node Details Side Panel */}
      {selectedNode && (
        <div className="w-full lg:w-80 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-5 shadow-xl flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
            <h3 className="font-bold text-sm text-[var(--text-primary)] flex items-center">
              <Info className="h-4 w-4 mr-2 text-[#79E282]" />
              Entity Telemetry
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--bg-surface)] text-[#79E282] uppercase border border-[var(--border-color)]">
              {selectedNode.type || 'HOP'}
            </span>
          </div>

          <div className="space-y-3 text-xs overflow-y-auto max-h-[500px]">
            {Object.entries(selectedNode).map(([k, v]) => (
              <div key={k} className="p-2.5 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-color)]">
                <span className="text-[10px] uppercase font-bold tracking-wider text-[var(--text-muted)] block mb-0.5">
                  {k}
                </span>
                <span className="font-mono text-xs text-[var(--text-primary)] break-all">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FundFlowGraph;
