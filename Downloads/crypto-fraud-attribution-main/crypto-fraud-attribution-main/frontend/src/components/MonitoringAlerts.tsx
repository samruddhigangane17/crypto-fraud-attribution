import { useEffect, useState } from 'react';
import { Bell, ShieldAlert, CheckCircle, Activity } from 'lucide-react';
import { supabase } from '../lib/supabase';
import { apiJson } from '../lib/api';

interface MonitoringAlertsProps {
  activeCase: string | null;
}

const severityStyles: Record<string, string> = {
  INFO: 'bg-[#38BDF8]/10 border-[#38BDF8]/30 text-[#38BDF8]',
  WARNING: 'bg-[#E6A94A]/10 border-[#E6A94A]/30 text-[#E6A94A]',
  HIGH: 'bg-[#F97316]/10 border-[#F97316]/30 text-[#F97316]',
  CRITICAL: 'bg-[#D95F63]/15 border-[#D95F63]/40 text-[#D95F63]',
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

  if (!activeCase) {
    return (
      <div className="p-12 text-center text-[var(--text-muted)] bg-[var(--bg-card)] rounded-2xl border border-[var(--border-color)] max-w-xl mx-auto my-12">
        <Activity className="h-10 w-10 text-[#79E282] mx-auto mb-3" />
        <h3 className="text-base font-bold text-[var(--text-primary)]">No Active Case Selected</h3>
        <p className="text-xs mt-1">Please select an investigation from the header console to view Monitoring Alerts.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-12 text-center text-xs font-mono text-[#79E282] bg-[var(--bg-card)] rounded-2xl border border-[var(--border-color)] max-w-xl mx-auto my-12">
        CONNECTING REAL-TIME ALERT MONITORING STREAM...
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-[var(--bg-card)] p-8 rounded-2xl shadow-xl border border-[var(--border-color)] transition-colors">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 border-b border-[var(--border-color)] pb-4 gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center">
              <Bell className="mr-3 text-[var(--accent-primary)] h-6 w-6" />
              Real-Time Sentinel Alerts
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Automated notifications for high-risk threshold breaches, mixer interactions, and VASP deposits.
            </p>
          </div>

          {monitoring ? (
            <span className="px-3 py-1.5 bg-[var(--accent-primary)]/15 text-[var(--accent-primary)] text-xs font-bold rounded-xl border border-[var(--accent-primary)]/30 flex items-center shadow-sm">
              <CheckCircle className="w-3.5 h-3.5 mr-1.5" />
              Monitoring Active
            </span>
          ) : (
            <button
              onClick={enableMonitoring}
              className="px-4 py-2 bg-[var(--accent-primary)] text-[var(--bg-card)] text-xs font-bold rounded-xl hover:opacity-90 transition-opacity shadow-md"
            >
              Activate Wallet Sentinel
            </button>
          )}
        </div>

        {error && (
          <div className="mb-4 p-3 bg-[#D95F63]/10 text-[#D95F63] border border-[#D95F63]/30 rounded-xl text-xs">{error}</div>
        )}

        <div className="space-y-3">
          {alerts.length === 0 ? (
            <div className="text-[var(--text-muted)] text-center py-12 text-xs">
              No active security alerts generated for this investigation. All observed transfers remain within baseline parameters.
            </div>
          ) : (
            alerts.map((alert: any) => (
              <div
                key={alert.id}
                className={`flex p-4 rounded-xl border ${severityStyles[alert.severity] ?? severityStyles.INFO}`}
              >
                <ShieldAlert className="mr-3.5 flex-shrink-0 h-5 w-5 mt-0.5" />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-xs uppercase tracking-wider">
                      {alert.title ?? String(alert.alert_type ?? '').replace(/_/g, ' ')}
                    </h4>
                    {alert.severity && (
                      <span className="text-[10px] font-mono font-bold uppercase px-1.5 py-0.5 rounded bg-[var(--bg-card)]">
                        {alert.severity}
                      </span>
                    )}
                  </div>
                  <p className="text-xs mt-1 text-[var(--text-primary)] leading-relaxed">{alert.message}</p>
                  {alert.tx_hash && (
                    <p className="text-[10px] mt-1.5 font-mono text-[var(--text-muted)] break-all">
                      Tx: {alert.tx_hash}
                    </p>
                  )}
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
