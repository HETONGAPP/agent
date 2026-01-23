/**
 * Diagnostic Store
 * Zustand store for diagnostic agent state management
 */

import { create } from 'zustand';

export type TaskStatus = 'pending' | 'executing' | 'completed' | 'failed';
export type AgentStatus = 'idle' | 'working' | 'complete' | 'error';

export interface DiagnosticTask {
  task_id: string;
  agent: string;
  description: string;
  dependencies: string[];
  status: TaskStatus;
  started_at?: number;
  completed_at?: number;
  error?: string;
}

export interface AgentState {
  name: string;
  status: AgentStatus;
  currentTaskId?: string;
  error?: string;
}

export interface DiagnosticMessage {
  id: string;
  type: 'info' | 'success' | 'error' | 'warning';
  content: string;
  timestamp: number;
  agent?: string;
}

interface DiagnosticStore {
  // Diagnostic session
  diagnosticId: string | null;
  siteId: string | null;
  isRunning: boolean;
  startTime: number | null;
  endTime: number | null;

  // Tasks
  tasks: DiagnosticTask[];
  setTasks: (tasks: DiagnosticTask[]) => void;
  updateTask: (taskId: string, updates: Partial<DiagnosticTask>) => void;

  // Agents
  agents: Record<string, AgentState>;
  updateAgentStatus: (agentName: string, status: AgentStatus, taskId?: string, error?: string) => void;

  // Messages
  messages: DiagnosticMessage[];
  addMessage: (message: Omit<DiagnosticMessage, 'id' | 'timestamp'>) => void;
  clearMessages: () => void;

  // Final result
  finalResult: any | null;
  setFinalResult: (result: any) => void;

  // Actions
  startDiagnostic: (siteId: string, diagnosticId: string) => void;
  completeDiagnostic: (result: any) => void;
  reset: () => void;
}

const initialAgentStates: Record<string, AgentState> = {
  DataCollectorAgent: { name: 'DataCollectorAgent', status: 'idle' },
  AlarmAnalyzerAgent: { name: 'AlarmAnalyzerAgent', status: 'idle' },
  DeviceAnalyzerAgent: { name: 'DeviceAnalyzerAgent', status: 'idle' },
  TrendAnalyzerAgent: { name: 'TrendAnalyzerAgent', status: 'idle' },
  CorrelationAgent: { name: 'CorrelationAgent', status: 'idle' },
  ReportGeneratorAgent: { name: 'ReportGeneratorAgent', status: 'idle' },
};

export const useDiagnosticAgentStore = create<DiagnosticStore>((set) => ({
  // Session
  diagnosticId: null,
  siteId: null,
  isRunning: false,
  startTime: null,
  endTime: null,

  // Tasks
  tasks: [],
  setTasks: (tasks) => set({ tasks }),
  updateTask: (taskId, updates) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.task_id === taskId ? { ...t, ...updates } : t
      ),
    })),

  // Agents
  agents: initialAgentStates,
  updateAgentStatus: (agentName, status, taskId, error) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [agentName]: {
          name: agentName,
          status,
          currentTaskId: taskId,
          error,
        },
      },
    })),

  // Messages
  messages: [],
  addMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
          timestamp: Date.now(),
        },
      ],
    })),
  clearMessages: () => set({ messages: [] }),

  // Final result
  finalResult: null,
  setFinalResult: (result) => set({ finalResult: result }),

  // Actions
  startDiagnostic: (siteId, diagnosticId) =>
    set({
      diagnosticId,
      siteId,
      isRunning: true,
      startTime: Date.now(),
      endTime: null,
      tasks: [],
      agents: initialAgentStates,
      messages: [],
      finalResult: null,
    }),

  completeDiagnostic: (result) =>
    set({
      isRunning: false,
      endTime: Date.now(),
      finalResult: result,
    }),

  reset: () =>
    set({
      diagnosticId: null,
      siteId: null,
      isRunning: false,
      startTime: null,
      endTime: null,
      tasks: [],
      agents: initialAgentStates,
      messages: [],
      finalResult: null,
    }),
}));

