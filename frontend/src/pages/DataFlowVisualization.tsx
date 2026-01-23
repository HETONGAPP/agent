/**
 * Data Flow Visualization Page
 * React Flow canvas for visualizing data flow
 */

import { useEffect, useState } from 'react';
import { FlowCanvas } from '@/components/flow/FlowCanvas';
import { NodeDetailsPanel } from '@/components/flow/NodeDetailsPanel';
import { useFlowStore } from '@/store/useFlowStore';
import { useDevices } from '@/hooks/useDevices';
import { useAlarms } from '@/hooks/useAlarms';
import { useDiagnostics } from '@/hooks/useDiagnostics';
import { Button } from '@/components/ui/Button';
import { FlowNode, Device, Alarm, Diagnostic } from '@/types';

export const DataFlowVisualization = () => {
  const { nodes, addNode, clearCanvas, selectedNodeId, setSelectedNodeId } = useFlowStore();
  const { devices, fetchDevices } = useDevices(true);
  const { alarms, fetchAlarms } = useAlarms(true);
  const { diagnostics, fetchDiagnostics } = useDiagnostics(true);
  const [selectedNode, setSelectedNode] = useState<{
    type: 'device' | 'alarm' | 'diagnostic';
    data: Device | Alarm | Diagnostic;
  } | null>(null);

  useEffect(() => {
    fetchDevices();
    fetchAlarms();
    fetchDiagnostics();
  }, [fetchDevices, fetchAlarms, fetchDiagnostics]);

  // Update selected node when selection changes
  useEffect(() => {
    if (selectedNodeId) {
      const node = nodes.find((n) => n.id === selectedNodeId);
      if (node && node.type === 'custom') {
        const nodeData = node.data as any;
        setSelectedNode({
          type: nodeData.type,
          data: nodeData.data,
        });
      }
    } else {
      setSelectedNode(null);
    }
  }, [selectedNodeId, nodes]);

  const handleAddNode = (type: 'device' | 'alarm' | 'diagnostic') => {
    let data: any;
    let label: string;
    let sourceData: Device | Alarm | Diagnostic | undefined;

    switch (type) {
      case 'device':
        if (devices.length === 0) return;
        sourceData = devices[Math.floor(Math.random() * devices.length)];
        data = { type: 'device', data: sourceData, label: sourceData.device_id };
        break;
      case 'alarm':
        if (alarms.length === 0) return;
        sourceData = alarms[Math.floor(Math.random() * alarms.length)];
        data = { type: 'alarm', data: sourceData, label: sourceData.alarm_id };
        break;
      case 'diagnostic':
        if (diagnostics.length === 0) return;
        sourceData = diagnostics[Math.floor(Math.random() * diagnostics.length)];
        data = { type: 'diagnostic', data: sourceData, label: sourceData.alarm_id };
        break;
    }

    const newNode: FlowNode = {
      id: `${type}-${Date.now()}`,
      type: 'custom',
      data,
      position: {
        x: Math.random() * 400 + 100,
        y: Math.random() * 400 + 100,
      },
    };

    addNode(newNode);
  };

  const handleClosePanel = () => {
    setSelectedNodeId(null);
    setSelectedNode(null);
  };

  return (
    <div className="space-y-6 h-full flex flex-col relative">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-1">Data Flow Visualization</h1>
          <p className="text-gray-400 text-sm">Visualize data flow and relationships</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={clearCanvas}>
            Clear Canvas
          </Button>
        </div>
      </div>

      {/* Node Palette */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Add Nodes</h2>
        <div className="flex items-center gap-4 flex-wrap">
          <Button
            variant="primary"
            size="sm"
            onClick={() => handleAddNode('device')}
            disabled={devices.length === 0}
          >
            Add Device Node ({devices.length})
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => handleAddNode('alarm')}
            disabled={alarms.length === 0}
          >
            Add Alarm Node ({alarms.length})
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => handleAddNode('diagnostic')}
            disabled={diagnostics.length === 0}
          >
            Add Diagnostic Node ({diagnostics.length})
          </Button>
        </div>
      </div>

      {/* Flow Canvas */}
      <div className="flex-1 relative" style={{ minHeight: '600px', height: 'calc(100vh - 300px)' }}>
        <div className="absolute inset-0 card p-0 overflow-hidden">
          <FlowCanvas />
        </div>
        {selectedNode && <NodeDetailsPanel node={selectedNode} onClose={handleClosePanel} />}
      </div>
    </div>
  );
};

