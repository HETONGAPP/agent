/**
 * Flow Canvas Component
 * Main React Flow canvas with controls and background
 */

import { useCallback, useEffect } from 'react';
import React from 'react';
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
} from 'reactflow';
import 'reactflow/dist/style.css';
import { CustomNode } from './CustomNode';
import { CustomEdge } from './CustomEdge';
import { useFlowStore } from '@/store/useFlowStore';
import { appConfig } from '@/config/app.config';

const nodeTypes: NodeTypes = {
  custom: CustomNode,
};

const edgeTypes: EdgeTypes = {
  custom: CustomEdge,
};

export const FlowCanvas = () => {
  const { nodes: storeNodes, edges: storeEdges, setNodes, setEdges, setSelectedNodeId } = useFlowStore();
  const [nodes, setNodesState, onNodesChange] = useNodesState(storeNodes);
  const [edges, setEdgesState, onEdgesChange] = useEdgesState(storeEdges);

  // Sync store to local state when store changes
  useEffect(() => {
    setNodesState(storeNodes);
  }, [storeNodes, setNodesState]);

  useEffect(() => {
    setEdgesState(storeEdges);
  }, [storeEdges, setEdgesState]);

  // Update store when nodes change (debounced to avoid infinite loops)
  const handleNodesChange = useCallback(
    (changes: any) => {
      onNodesChange(changes);
      // Update store after React Flow processes the changes
      setTimeout(() => {
        setNodes(nodes);
      }, 0);
    },
    [nodes, onNodesChange, setNodes]
  );

  const handleEdgesChange = useCallback(
    (changes: any) => {
      onEdgesChange(changes);
      // Update store after React Flow processes the changes
      setTimeout(() => {
        setEdges(edges);
      }, 0);
    },
    [edges, onEdgesChange, setEdges]
  );

  const onConnect = useCallback(
    (params: Connection) => {
      const newEdge = addEdge(params, edges);
      setEdgesState(newEdge);
      setEdges(newEdge);
    },
    [edges, setEdgesState, setEdges]
  );

  const onNodeClick = useCallback(
    (_event: any, node: Node) => {
      setSelectedNodeId(node.id);
    },
    [setSelectedNodeId]
  );

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, [setSelectedNodeId]);

  return (
    <div className="w-full h-full bg-gray-900 relative">
      {nodes.length === 0 ? (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <div className="text-6xl mb-4 opacity-50">📊</div>
            <h3 className="text-xl font-semibold text-white mb-2">Empty Canvas</h3>
            <p className="text-gray-400">Click "Add Node" buttons above to add nodes to the canvas</p>
          </div>
        </div>
      ) : null}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        minZoom={appConfig.flow.minZoom}
        maxZoom={appConfig.flow.maxZoom}
        defaultViewport={{ x: 0, y: 0, zoom: appConfig.flow.defaultZoom }}
      >
        <Background color="#374151" gap={16} />
        <Controls className="bg-gray-800 border border-gray-700" />
        <MiniMap
          className="bg-gray-800 border border-gray-700"
          nodeColor={(node: Node) => {
            switch (node.type) {
              case 'custom':
                const data = node.data as any;
                if (data.type === 'device') return '#10B981';
                if (data.type === 'alarm') return '#EF4444';
                if (data.type === 'diagnostic') return '#3B82F6';
                return '#6B7280';
              default:
                return '#6B7280';
            }
          }}
        />
      </ReactFlow>
    </div>
  );
};

