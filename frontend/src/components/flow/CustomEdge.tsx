/**
 * Custom Edge Component for React Flow
 * Customized connection lines with animations
 */

import { BaseEdge, EdgeProps, getBezierPath } from 'reactflow';

export const CustomEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
}: EdgeProps) => {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          stroke: '#60A5FA',
          strokeWidth: 2,
        }}
        markerEnd={markerEnd}
      />
      <path
        d={edgePath}
        fill="none"
        stroke="#3B82F6"
        strokeWidth={1}
        strokeDasharray="5,5"
        className="animate-pulse"
        opacity={0.3}
      />
    </>
  );
};














