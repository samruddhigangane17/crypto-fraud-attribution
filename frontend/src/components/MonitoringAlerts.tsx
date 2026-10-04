import { useEffect, useState } from 'react';
import { Bell, ShieldAlert, CheckCircle } from 'lucide-react';
import { supabase } from '../lib/supabase';
import { apiJson } from '../lib/api';

interface MonitoringAlertsProps {
  activeCase: string | null;
}

const severityStyles: Record<string, string> = {
  INFO: 'bg-blue-50 border-blue-200 text-blue-900',
  WARNING: 'bg-yellow-50 border-yellow-200 text-yellow-900',
  HIGH: 'bg-orange-50 border-orange-200 text-orange-900',
  CRITICAL: 'bg-red-50 border-red-200 text-red-900',
};

const MonitoringAlerts: React.FC<MonitoringAlertsProps> = ({ activeCase }) => {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [monitoring, setMonitoring] = useState(false);

  useEffect(() => {
    if (!activeCase) return;
    setLoading(true);
    setError(null);
    setMonitoring(false);

    apiJson(`/api/investigations/${activeCase}/alerts`)
      .then((data) => setAlerts(data))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));

    // Supabase Realtime: live alerts written to the alerts table
    const channel = supabase
      .channel(`alerts-${activeCase}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'alerts',
          filter: `investigation_id=eq.${activeCase}`,
        },
        (payload) => {
          setAlerts((prev) => [payload.new, ...prev]);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [activeCase]);

  const enableMonitoring = async () => {
    if (!activeCase) return;
    setError(null);
    try {
      const inv = await apiJson(`/api/investigations/${activeCase}`);
      await apiJson(`/api/investigations/${activeCase}/monitor`, {
        method: 'POST',
        body: JSON.stringify({
          investigation_id: activeCase,
          chain: inv.chain,
          watched_addresses: [inv.reported_address, ...(inv.intermediate_addresses ?? [])],
          is_active: true,
        }),
      });
      setMonitoring(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  if (!activeCase) return <div className="p-8 text-center text-gray-500">No active case selected.</div>;
  if (loading) return <div>Loading alerts...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div className="flex justify-between items-center mb-6 border-b pb-4">
          <h2 className="text-2xl font-bold text-gray-800 flex items-center">
            <Bell className="mr-3 text-indigo-600" />
            Monitoring and Alerts
          </h2>
          {monitoring ? (
            <span className="px-3 py-1 bg-green-100 text-green-800 text-sm font-medium rounded-full flex items-center">
              <CheckCircle className="w-4 h-4 mr-1" />
              Monitoring enabled
            </span>
          ) : (
            <button
              onClick={enableMonitoring}
              className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700"
            >
              Enable monitoring
            </button>
          )}
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm">{error}</div>
        )}

        <div className="space-y-4">
          {alerts.length === 0 ? (
            <div className="text-gray-500 text-center py-8">No alerts generated yet.</div>
          ) : (
            alerts.map((alert: any) => (
              <div
                key={alert.id}
                className={`flex p-4 rounded-lg border ${severityStyles[alert.severity] ?? severityStyles.INFO}`}
              >
                <ShieldAlert className="mr-4 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">
                    {alert.title ?? String(alert.alert_type ?? '').replace(/_/g, ' ').toUpperCase()}
                    {alert.severity ? ` · ${alert.severity}` : ''}
                  </h4>
                  <p className="text-sm mt-1">{alert.message}</p>
                  {alert.tx_hash && <p className="text-xs mt-1 opacity-75 break-all">Tx: {alert.tx_hash}</p>}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default MonitoringAlerts;
