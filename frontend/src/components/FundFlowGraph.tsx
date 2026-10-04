import { useEffect, useState } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import { apiJson } from '../lib/api';

interface FundFlowGraphProps {
  activeCase: string | null;
}

const FundFlowGraph: React.FC<FundFlowGraphProps> = ({ activeCase }) => {
  const [elements, setElements] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!activeCase) return;
    setLoading(true);
    setError(null);
    setNotice(null);
    apiJson(`/api/investigations/${activeCase}`)
      .then((c) => setNotice(c.notice ?? null))
      .catch(() => setNotice(null));
    apiJson(`/api/investigations/${activeCase}/graph`)
      .then((data) => {
        const cytoscapeElements = [
          ...data.nodes.map((n: any) => ({ data: n.data })),
          ...data.edges.map((e: any) => ({ data: e.data }))
        ];
        setElements(cytoscapeElements);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [activeCase]);

  if (!activeCase) {
    return <div className="p-8 text-center text-gray-500">No active case selected. Please start an investigation.</div>;
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
