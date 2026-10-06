import { useEffect, useState, useRef } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import { apiJson } from '../lib/api';
import {
  Play,
  RefreshCw,
  AlertCircle,
  Box,
  Layers,
  Info,
  Compass,
  ZoomIn,
  ZoomOut,
  Maximize2,
} from 'lucide-react';
import Sphere3DGraph from './Sphere3DGraph';

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
  const [currentTheme, setCurrentTheme] = useState<'dark' | 'light'>(() => {
    return (document.documentElement.getAttribute('data-theme') as 'dark' | 'light') || 'dark';
  });
  const cyRef = useRef<any>(null);

  useEffect(() => {
    const observer = new MutationObserver(() => {
      const theme = (document.documentElement.getAttribute('data-theme') as 'dark' | 'light') || 'dark';
      setCurrentTheme(theme);
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  const handleZoomIn = () => {
    if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 1.25);
  };
  const handleZoomOut = () => {
    if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 0.8);
  };
  const handleFit = () => {
    if (cyRef.current) cyRef.current.fit(undefined, 40);
  };

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

  // Theme-Aware CryptoTracer Cytoscape styling
  const isLight = currentTheme === 'light';

  const style = [
    // Base node style (Intermediary / Hop)
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'text-valign': 'bottom' as any,
        'text-margin-y': 6,
        'width': 38,
        'height': 38,
        'background-fill': 'radial-gradient' as any,
        'background-gradient-stop-colors': '#89F792 #26736E #0D3533',
        'background-gradient-stop-positions': '0% 55% 100%',
        'border-color': '#79E282',
        'border-width': 2,
        'color': isLight ? '#0B1512' : '#E8EEEB',
        'font-family': 'Montserrat, sans-serif',
        'font-size': '11px',
        'font-weight': 600,
        'text-background-opacity': 0.92,
        'text-background-color': isLight ? '#E2ECE7' : '#182124',
        'text-background-padding': '3px',
        'text-background-shape': 'roundrectangle' as any,
        'text-border-width': 1,
        'text-border-color': isLight ? '#B8CFC5' : '#243338',
      },
    },
    // Victim / Source Node: radial gradient #FF9E9E -> #D95F63 -> #6E1A1E with glowing red halo
    {
      selector: 'node[type="victim"], node[type="source"]',
      style: {
        'background-fill': 'radial-gradient' as any,
        'background-gradient-stop-colors': '#FF9E9E #D95F63 #6E1A1E',
        'background-gradient-stop-positions': '0% 55% 100%',
        'width': 48,
        'height': 48,
        'border-width': 6,
        'border-color': '#D95F63',
        'border-opacity': 0.35,
      },
    },
    // Intermediary Node: radial gradient #89F792 -> #26736E -> #0D3533 with teal halo
    {
      selector: 'node[type="intermediate"], node[type="hop"], node[type="mule"]',
      style: {
        'background-fill': 'radial-gradient' as any,
        'background-gradient-stop-colors': '#89F792 #26736E #0D3533',
        'background-gradient-stop-positions': '0% 55% 100%',
        'width': 38,
        'height': 38,
        'border-color': '#79E282',
        'border-width': 3,
        'border-opacity': 0.7,
      },
    },
    // Exchange / VASP Node: radial gradient #C8FFCD -> #79E282 -> #1B6B36 with bright mint aura
    {
      selector: 'node[type="exchange"], node[type="vasp"]',
      style: {
        'background-fill': 'radial-gradient' as any,
        'background-gradient-stop-colors': '#C8FFCD #79E282 #1B6B36',
        'background-gradient-stop-positions': '0% 55% 100%',
        'shape': 'hexagon' as any,
        'width': 46,
        'height': 46,
        'border-color': '#FFFFFF',
        'border-width': 3,
        'border-opacity': 0.9,
      },
    },
    // Mixer Node: radial gradient #FFE082 -> #E6A94A -> #7A4B08
    {
      selector: 'node[type="mixer"]',
      style: {
        'background-fill': 'radial-gradient' as any,
        'background-gradient-stop-colors': '#FFE082 #E6A94A #7A4B08',
        'background-gradient-stop-positions': '0% 55% 100%',
        'shape': 'diamond' as any,
        'width': 44,
        'height': 44,
        'border-color': '#FDE68A',
        'border-width': 3,
      },
    },
    // Bridge Node: radial gradient #BAE6FD -> #38BDF8 -> #0369A1
    {
      selector: 'node[type="bridge"]',
      style: {
        'background-fill': 'radial-gradient' as any,
        'background-gradient-stop-colors': '#BAE6FD #38BDF8 #0369A1',
        'background-gradient-stop-positions': '0% 55% 100%',
        'shape': 'round-rectangle' as any,
        'width': 42,
        'height': 42,
        'border-color': '#BAE6FD',
        'border-width': 3,
      },
    },
    // Curved Glowing Edges & Styled Amount Pills
    {
      selector: 'edge',
      style: {
        'width': 2.5,
        'curve-style': 'bezier' as any,
        'control-point-step-size': 35,
        'line-color': isLight ? '#0F766E' : '#368980',
        'target-arrow-color': isLight ? '#0F766E' : '#79E282',
        'target-arrow-shape': 'triangle' as any,
        'label': 'data(amount)',
        'font-size': '10px',
        'font-family': 'JetBrains Mono, monospace',
        'font-weight': 600,
        'color': isLight ? '#0F766E' : '#79E282',
        'text-background-opacity': 0.92,
        'text-background-color': isLight ? '#E2ECE7' : '#182124',
        'text-background-padding': '4px',
        'text-background-shape': 'roundrectangle' as any,
        'text-border-width': 1,
        'text-border-color': isLight ? '#B8CFC5' : '#368980',
      },
    },
  ];

  return (
    <div className="flex flex-col lg:flex-row h-full gap-5">
      {/* Graph Visualiser Container */}
      <div className="flex-1 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl overflow-hidden flex flex-col relative shadow-xl transition-all duration-300">
        {/* Header Controls */}
        <div className="p-4 bg-[var(--bg-secondary)] border-b border-[var(--border-color)] flex flex-wrap justify-between items-center gap-3">
          <div className="flex items-center space-x-3">
            <div className="p-1.5 bg-[var(--accent-primary)]/10 rounded-lg text-[var(--accent-primary)]">
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
              <span className="flex items-center text-[var(--accent-primary)]">
                <span className="h-2 w-2 bg-[var(--accent-primary)] mr-1" /> VASP
              </span>
            </div>

            {/* 2D / 3D Interactive Sphere View Toggle */}
            <button
              onClick={() => setIs3DView(!is3DView)}
              className={`flex items-center space-x-1.5 px-3 py-1.5 text-xs font-bold rounded-lg border transition-all duration-200 cursor-pointer ${
                is3DView
                  ? 'bg-[var(--accent-primary)] text-[var(--bg-card)] border-[var(--accent-primary)] shadow-md'
                  : 'bg-[var(--bg-card)] text-[var(--text-muted)] border-[var(--border-color)] hover:text-[var(--accent-primary)]'
              }`}
              title="Toggle between 2D Cytoscape view and 360-degree interactive 3D spherical globe"
            >
              <Box className="h-3.5 w-3.5" />
              <span>{is3DView ? '3D Sphere Active' : '2D / 3D Sphere View'}</span>
            </button>
          </div>
        </div>

        {/* Graph Canvas */}
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center space-y-2 text-xs font-mono text-[var(--accent-primary)]">
            <RefreshCw className="h-6 w-6 animate-spin text-[var(--accent-primary)]" />
            <span>RENDERING GRAPH TOPOLOGY...</span>
          </div>
        ) : is3DView ? (
          /* True Interactive 3D Spherical Graph Canvas */
          <div className="flex-1 flex flex-col relative overflow-hidden">
            <Sphere3DGraph
              elements={elements}
              selectedNode={selectedNode}
              onSelectNode={setSelectedNode}
              theme={currentTheme}
            />
          </div>
        ) : (
          /* 2D Topology with 3D Lit Nodes */
          <div
            className="flex-1 relative overflow-hidden transition-all duration-300"
            style={{
              backgroundColor: 'var(--graph-bg)',
              backgroundImage: `radial-gradient(circle at 50% 50%, var(--border-color) 0%, transparent 75%),
                radial-gradient(var(--graph-grid) 1.5px, transparent 1.5px)`,
              backgroundSize: '100% 100%, 24px 24px',
            }}
          >
            {/* Quick Floating Zoom & View Controls */}
            <div className="absolute top-4 right-4 z-10 flex items-center space-x-1.5 bg-[var(--bg-card)]/90 backdrop-blur-md p-1.5 rounded-xl border border-[var(--border-color)] shadow-lg">
              <button
                onClick={handleZoomIn}
                className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
                title="Zoom In (+)"
              >
                <ZoomIn className="h-4 w-4" />
              </button>
              <button
                onClick={handleZoomOut}
                className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
                title="Zoom Out (-)"
              >
                <ZoomOut className="h-4 w-4" />
              </button>
              <button
                onClick={handleFit}
                className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
                title="Fit Graph to Screen"
              >
                <Maximize2 className="h-4 w-4" />
              </button>
            </div>

            <CytoscapeComponent
              elements={elements}
              style={{ width: '100%', height: '100%' }}
              layout={layout}
              stylesheet={style}
              cy={(cy) => {
                cyRef.current = cy;
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
              <Info className="h-4 w-4 mr-2 text-[var(--accent-primary)]" />
              Entity Telemetry
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--bg-secondary)] text-[var(--accent-primary)] uppercase border border-[var(--border-color)]">
              {selectedNode.type || 'HOP'}
            </span>
          </div>

          <div className="space-y-3 text-xs overflow-y-auto max-h-[500px]">
            {Object.entries(selectedNode).map(([k, v]) => (
              <div key={k} className="p-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]">
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
