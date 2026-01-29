/**
 * Diagnostic Page
 * Main page for site diagnostic agent
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { DiagnosticCanvas } from '@/components/diagnostics/DiagnosticCanvas';
import { useDiagnosticAgentStore } from '@/store/useDiagnosticAgentStore';
import { useDiagnosticWebSocket } from '@/hooks/useDiagnosticWebSocket';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PageLoading } from '@/components/ui/PageLoading';
import { appConfig } from '@/config/app.config';
import { ArrowLeft, RefreshCw } from 'lucide-react';

export const DiagnosticPage = () => {
  const { siteId } = useParams<{ siteId: string }>();
  const navigate = useNavigate();
  const [timeRange, setTimeRange] = useState('-24h');
  const [isStarting, setIsStarting] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);

  const { isRunning, diagnosticId, startDiagnostic, reset } = useDiagnosticAgentStore();

  // Connect WebSocket
  const { isConnected } = useDiagnosticWebSocket({
    siteId: siteId || null,
    enabled: !!siteId,
    baseUrl: appConfig.apiBaseUrl,
  });

  // Set initial loading to false once WebSocket is connected or after a short delay
  useEffect(() => {
    if (isConnected) {
      setInitialLoading(false);
    } else {
      // If WebSocket doesn't connect within 2 seconds, show page anyway
      const timer = setTimeout(() => {
        setInitialLoading(false);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [isConnected]);

  const handleStartDiagnostic = async () => {
    if (!siteId) return;

    setIsStarting(true);
    try {
      const response = await fetch(
        `${appConfig.apiBaseUrl}/sites/${siteId}/diagnostics/agent/start?time_range=${timeRange}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to start diagnostic');
      }

      const data = await response.json();
      if (data.diagnostic_id) {
        startDiagnostic(siteId, data.diagnostic_id);
      }
    } catch (error) {
      console.error('Error starting diagnostic:', error);
      alert('Failed to start diagnostic. Please try again.');
    } finally {
      setIsStarting(false);
    }
  };

  const handleReset = () => {
    reset();
  };

  if (!siteId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-zinc-400 mb-4">No site ID provided</p>
          <Button onClick={() => navigate('/sites')}>Go to Sites</Button>
        </div>
      </div>
    );
  }

  // Show loading state during initial connection
  if (initialLoading) {
    return <PageLoading message="Connecting to diagnostic service..." />;
  }

  return (
    <div className="w-full h-full flex flex-col bg-black">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4 p-3 sm:p-4 border-b border-amber-500/20 bg-zinc-900">
        <div className="flex items-center gap-2 sm:gap-4">
          <Button
            variant="outline"
            onClick={() => navigate(`/sites/${siteId}`)}
            className="border-amber-500/20 text-amber-500 hover:bg-amber-500/10 text-sm sm:text-base"
          >
            <ArrowLeft size={16} className="sm:mr-2" />
            <span className="hidden sm:inline">Back to Site</span>
          </Button>
          <h1 className="text-lg sm:text-xl font-semibold text-amber-500">Site Diagnostic</h1>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
          {/* Time Range Selector */}
          {!isRunning && (
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="bg-zinc-800 border border-amber-500/20 text-zinc-300 rounded px-3 py-2 text-sm w-full sm:w-auto"
            >
              <option value="-1h">Last Hour</option>
              <option value="-24h">Last 24 Hours</option>
              <option value="-7d">Last 7 Days</option>
              <option value="-30d">Last 30 Days</option>
            </select>
          )}

          {/* WebSocket Status */}
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
              }`}
            />
            <span className="text-xs text-zinc-400">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          {/* Start/Reset Button */}
          {!isRunning ? (
            <Button
              onClick={handleStartDiagnostic}
              disabled={isStarting || !isConnected}
              className="bg-amber-500 hover:bg-amber-600 text-black text-sm sm:text-base w-full sm:w-auto"
            >
              {isStarting ? (
                <>
                  <LoadingSpinner size="sm" className="sm:mr-2" />
                  <span className="hidden sm:inline">Starting...</span>
                </>
              ) : (
                <>
                  <span className="hidden sm:inline">Start Diagnostic</span>
                  <span className="sm:hidden">Start</span>
                </>
              )}
            </Button>
          ) : (
            <Button
              onClick={handleReset}
              variant="outline"
              className="border-red-500/20 text-red-400 hover:bg-red-500/10 text-sm sm:text-base w-full sm:w-auto"
            >
              <RefreshCw size={16} className="sm:mr-2" />
              <span className="hidden sm:inline">Reset</span>
            </Button>
          )}
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative">
        {isRunning || diagnosticId ? (
          <DiagnosticCanvas siteId={siteId} />
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-4">
              <div className="text-6xl mb-4">🔍</div>
              <h2 className="text-2xl font-semibold text-zinc-300">Ready to Diagnose</h2>
              <p className="text-zinc-400">
                Click "Start Diagnostic" to begin analyzing site {siteId}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

