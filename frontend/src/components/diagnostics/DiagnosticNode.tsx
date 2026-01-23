/**
 * Diagnostic Node Component
 * Custom node for diagnostic tasks
 */

import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { motion } from 'framer-motion';
import { useDiagnosticAgentStore, TaskStatus, AgentStatus } from '@/store/useDiagnosticAgentStore';

interface DiagnosticNodeData {
  task: {
    task_id: string;
    agent: string;
    description: string;
    status: TaskStatus;
    error?: string;
  };
  agent: string;
  status: TaskStatus;
  agentStatus: AgentStatus;
  error?: string;
}

const statusColors: Record<TaskStatus, string> = {
  pending: 'bg-zinc-800 border-zinc-700',
  executing: 'bg-amber-500/20 border-amber-500',
  completed: 'bg-green-500/20 border-green-500',
  failed: 'bg-red-500/20 border-red-500',
};

const statusIcons: Record<TaskStatus, string> = {
  pending: '⏳',
  executing: '🔄',
  completed: '✅',
  failed: '❌',
};

const agentColors: Record<string, string> = {
  DataCollectorAgent: 'text-blue-400',
  AlarmAnalyzerAgent: 'text-pink-400',
  DeviceAnalyzerAgent: 'text-purple-400',
  TrendAnalyzerAgent: 'text-cyan-400',
  CorrelationAgent: 'text-yellow-400',
  ReportGeneratorAgent: 'text-green-400',
};

export const DiagnosticNode = memo(({ data, selected }: NodeProps<DiagnosticNodeData>) => {
  const { task, agent, status, agentStatus, error } = data;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
      className={`rounded-lg border-2 p-4 min-w-[260px] ${statusColors[status]} ${
        selected ? 'ring-2 ring-amber-500' : ''
      }`}
    >
      {/* Input handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-amber-500" />

      {/* Node content */}
      <div className="space-y-2">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">{statusIcons[status]}</span>
            <span className={`text-sm font-semibold ${agentColors[agent] || 'text-zinc-300'}`}>
              {agent}
            </span>
          </div>
          {agentStatus === 'working' && (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full"
            />
          )}
        </div>

        {/* Task ID */}
        <div className="text-xs text-zinc-400 font-mono">{task.task_id}</div>

        {/* Description */}
        <div className="text-xs text-zinc-300 line-clamp-2">{task.description}</div>

        {/* Error */}
        {error && (
          <div className="text-xs text-red-400 bg-red-500/10 p-2 rounded">
            {error}
          </div>
        )}

        {/* Status badge */}
        <div className="flex items-center gap-2">
          <div
            className={`text-xs px-2 py-1 rounded ${
              status === 'completed'
                ? 'bg-green-500/20 text-green-400'
                : status === 'executing'
                ? 'bg-amber-500/20 text-amber-400'
                : status === 'failed'
                ? 'bg-red-500/20 text-red-400'
                : 'bg-zinc-700 text-zinc-400'
            }`}
          >
            {status}
          </div>
        </div>
      </div>

      {/* Output handles */}
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-amber-500" />
    </motion.div>
  );
});

DiagnosticNode.displayName = 'DiagnosticNode';

