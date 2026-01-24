/**
 * Flow Store
 * Zustand store for React Flow canvas state management
 */

import { create } from 'zustand';
import { FlowNode, FlowEdge } from '@/types';

interface FlowState {
  nodes: FlowNode[];
  edges: FlowEdge[];
  selectedNodeId: string | null;
  
  // Actions
  setNodes: (nodes: FlowNode[]) => void;
  addNode: (node: FlowNode) => void;
  updateNode: (nodeId: string, updates: Partial<FlowNode>) => void;
  removeNode: (nodeId: string) => void;
  setEdges: (edges: FlowEdge[]) => void;
  addEdge: (edge: FlowEdge) => void;
  removeEdge: (edgeId: string) => void;
  setSelectedNodeId: (nodeId: string | null) => void;
  clearCanvas: () => void;
}

export const useFlowStore = create<FlowState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,

  setNodes: (nodes) => {
    set({ nodes });
  },

  addNode: (node) => {
    set((state) => ({
      nodes: [...state.nodes, node],
    }));
  },

  updateNode: (nodeId, updates) => {
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === nodeId ? { ...node, ...updates } : node
      ),
    }));
  },

  removeNode: (nodeId) => {
    set((state) => ({
      nodes: state.nodes.filter((node) => node.id !== nodeId),
      edges: state.edges.filter(
        (edge) => edge.source !== nodeId && edge.target !== nodeId
      ),
    }));
  },

  setEdges: (edges) => {
    set({ edges });
  },

  addEdge: (edge) => {
    set((state) => ({
      edges: [...state.edges, edge],
    }));
  },

  removeEdge: (edgeId) => {
    set((state) => ({
      edges: state.edges.filter((edge) => edge.id !== edgeId),
    }));
  },

  setSelectedNodeId: (nodeId) => {
    set({ selectedNodeId: nodeId });
  },

  clearCanvas: () => {
    set({ nodes: [], edges: [], selectedNodeId: null });
  },
}));













