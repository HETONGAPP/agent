/**
 * Diagnostic Canvas Component
 * Infinite canvas visualization for diagnostic agent workflow
 */

import { useCallback, useEffect, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  Connection,
  addEdge,
  useNodesState,
  useEdgesState,
  NodeTypes,
  EdgeTypes,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { motion } from 'framer-motion';
import { useDiagnosticAgentStore } from '@/store/useDiagnosticAgentStore';
import { DiagnosticNode } from './DiagnosticNode';
import { DiagnosticOutput } from './DiagnosticOutput';

const nodeTypes: NodeTypes = {
  diagnostic: DiagnosticNode,
};

const edgeTypes: EdgeTypes = {
  default: {
    style: { stroke: '#f59e0b', strokeWidth: 2 },
    animated: true,
  },
};

interface DiagnosticCanvasProps {
  siteId: string;
  onStart?: () => void;
}

export const DiagnosticCanvas = ({ siteId, onStart }: DiagnosticCanvasProps) => {
  const {
    tasks,
    agents,
    messages,
    isRunning,
    finalResult,
    startTime,
    endTime,
  } = useDiagnosticAgentStore();

  // Convert tasks to nodes
  const taskNodes = useMemo(() => {
    const nodes: Node[] = [];
    const nodePositions: Record<string, { x: number; y: number }> = {};
    const nodeWidth = 280;
    const nodeHeight = 120;
    const horizontalSpacing = 350;
    const verticalSpacing = 200;

    // Group tasks by level (based on dependencies)
    const levels: string[][] = [];
    const processed = new Set<string>();

    // Find root tasks (no dependencies)
    const rootTasks = tasks.filter((t) => t.dependencies.length === 0);
    if (rootTasks.length > 0) {
      levels.push(rootTasks.map((t) => t.task_id));
      rootTasks.forEach((t) => processed.add(t.task_id));
    }

    // Build levels iteratively
    while (processed.size < tasks.length) {
      const currentLevel: string[] = [];
      tasks.forEach((task) => {
        if (processed.has(task.task_id)) return;
        const allDepsProcessed = task.dependencies.every((dep) => processed.has(dep));
        if (allDepsProcessed) {
          currentLevel.push(task.task_id);
          processed.add(task.task_id);
        }
      });
      if (currentLevel.length > 0) {
        levels.push(currentLevel);
      } else {
        break; // Prevent infinite loop
      }
    }

    // Position nodes by level
    levels.forEach((level, levelIndex) => {
      level.forEach((taskId, indexInLevel) => {
        const task = tasks.find((t) => t.task_id === taskId);
        if (!task) return;

        const x = levelIndex * horizontalSpacing + 100;
        const y = indexInLevel * verticalSpacing + 100;
        nodePositions[taskId] = { x, y };

        const agentState = agents[task.agent] || { status: 'idle' };

        nodes.push({
          id: taskId,
          type: 'diagnostic',
          position: { x, y },
          data: {
            task,
            agent: task.agent,
            status: task.status,
            agentStatus: agentState.status,
            error: task.error,
          },
        });
      });
    });

    return { nodes, nodePositions };
  }, [tasks, agents]);

  // Convert dependencies to edges
  const taskEdges = useMemo(() => {
    const edges: Edge[] = [];
    tasks.forEach((task) => {
      task.dependencies.forEach((depId) => {
        edges.push({
          id: `${depId}-${task.task_id}`,
          source: depId,
          target: task.task_id,
          type: 'default',
          animated: task.status === 'executing',
        });
      });
    });
    return edges;
  }, [tasks]);

  const [nodes, setNodes, onNodesChange] = useNodesState(taskNodes.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(taskEdges);

  // Update nodes when tasks change
  useEffect(() => {
    setNodes(taskNodes.nodes);
  }, [taskNodes.nodes, setNodes]);

  useEffect(() => {
    setEdges(taskEdges);
  }, [taskEdges, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => addEdge(params, eds));
    },
    [setEdges]
  );

  // Calculate progress
  const progress = useMemo(() => {
    if (tasks.length === 0) return 0;
    const completed = tasks.filter((t) => t.status === 'completed').length;
    return (completed / tasks.length) * 100;
  }, [tasks]);

  const elapsedTime = useMemo(() => {
    if (!startTime) return 0;
    const end = endTime || Date.now();
    return Math.floor((end - startTime) / 1000);
  }, [startTime, endTime]);

  return (
    <div className="relative w-full h-full bg-black">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 bg-black/80 backdrop-blur-sm border-b border-amber-500/20 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-amber-500">Site Diagnostic</h2>
            <p className="text-sm text-zinc-400">Site ID: {siteId}</p>
          </div>
          <div className="flex items-center gap-4">
            {isRunning && (
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse" />
                <span className="text-sm text-zinc-300">Running...</span>
              </div>
            )}
            <div className="text-sm text-zinc-400">
              {tasks.length > 0 && (
                <>
                  {tasks.filter((t) => t.status === 'completed').length} / {tasks.length} tasks
                </>
              )}
            </div>
            {elapsedTime > 0 && (
              <div className="text-sm text-zinc-400">Time: {elapsedTime}s</div>
            )}
          </div>
        </div>
        {progress > 0 && (
          <div className="mt-2">
            <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-amber-500"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Canvas */}
      <div className="w-full h-full pt-24">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          minZoom={0.1}
          maxZoom={2}
          defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
        >
          <Background color="#27272a" gap={20} />
          <Controls className="bg-zinc-900 border border-zinc-800" />
          <MiniMap
            className="bg-zinc-900 border border-zinc-800"
            nodeColor={(node) => {
              const status = node.data?.status;
              if (status === 'completed') return '#10b981';
              if (status === 'executing') return '#f59e0b';
              if (status === 'failed') return '#ef4444';
              return '#6b7280';
            }}
          />
        </ReactFlow>
      </div>

      {/* Output Panel */}
      {finalResult && (
        <DiagnosticOutput result={finalResult} />
      )}

      {/* Messages Panel */}
      {messages.length > 0 && (
        <div className="absolute bottom-4 right-4 w-80 max-h-64 overflow-y-auto bg-zinc-900/90 backdrop-blur-sm border border-amber-500/20 rounded-lg p-3 space-y-2">
          <div className="text-xs font-semibold text-amber-500 mb-2">Messages</div>
          {messages.slice(-5).map((msg) => (
            <div
              key={msg.id}
              className={`text-xs p-2 rounded ${
                msg.type === 'error'
                  ? 'bg-red-500/20 text-red-400'
                  : msg.type === 'success'
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-zinc-800 text-zinc-300'
              }`}
            >
              {msg.content}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

