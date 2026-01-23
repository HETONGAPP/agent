/**
 * Time Series Chart Renderers
 * SVG rendering components
 */

import React from 'react';
import { TimeSeriesDataPoint, ScaleFunctions, HoverPosition, ChartDimensions } from './types';
import { formatTime, formatDate } from './utils';
import { parseTimestamp } from './utils';

interface GridLinesProps {
  yTicks: Array<{ value: number; y: number }>;
  xTicks: Array<{ x: number; timestamp: string }>;
  dimensions: ChartDimensions;
  showGrid: boolean;
}

export const GridLines: React.FC<GridLinesProps> = ({
  yTicks,
  xTicks,
  dimensions,
  showGrid,
}) => {
  if (!showGrid) return null;

  return (
    <>
      {yTicks.map((tick, i) => (
        <g key={`grid-y-${i}`}>
          <line
            x1={dimensions.padding.left}
            y1={tick.y + dimensions.padding.top}
            x2={dimensions.width - dimensions.padding.right}
            y2={tick.y + dimensions.padding.top}
            stroke="#374151"
            strokeWidth="1"
            strokeDasharray="2,2"
            opacity="0.5"
          />
        </g>
      ))}
      {xTicks.map((tick, i) => (
        <g key={`grid-x-${i}`}>
          <line
            x1={tick.x + dimensions.padding.left}
            y1={dimensions.padding.top}
            x2={tick.x + dimensions.padding.left}
            y2={dimensions.height - dimensions.padding.bottom}
            stroke="#374151"
            strokeWidth="1"
            strokeDasharray="2,2"
            opacity="0.5"
          />
        </g>
      ))}
    </>
  );
};

interface AreaPathProps {
  areaPath: string;
  color: string;
  realTime: boolean;
  pathChanged: boolean;
  padding: { top: number; left: number };
  pathRef?: React.RefObject<SVGPathElement>;
}

export const AreaPath: React.FC<AreaPathProps> = ({
  areaPath,
  color,
  realTime,
  pathChanged,
  padding,
  pathRef,
}) => {
  if (!areaPath) return null;

  return (
    <g transform={`translate(${padding.left}, ${padding.top})`}>
      <path
        ref={pathRef}
        key="area-path"
        d={areaPath}
        fill="url(#areaGradient)"
        style={{
          opacity: 1,
          // In real-time mode, transition is set dynamically in useLayoutEffect
          // For non-real-time, use conditional transition
          transition: realTime
            ? 'd 0.15s linear'
            : pathChanged
            ? 'd 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
            : 'none',
          willChange: realTime ? 'd' : 'auto',
          shapeRendering: 'geometricPrecision',
        }}
      />
    </g>
  );
};

interface LinePathProps {
  linePath: string;
  color: string;
  realTime: boolean;
  pathChanged: boolean;
  padding: { top: number; left: number };
  pathRef?: React.RefObject<SVGPathElement>;
}

export const LinePath: React.FC<LinePathProps> = ({
  linePath,
  color,
  realTime,
  pathChanged,
  padding,
  pathRef,
}) => {
  if (!linePath) return null;

  return (
    <g transform={`translate(${padding.left}, ${padding.top})`} key="line-path">
      <path
        ref={pathRef}
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        filter="url(#glow)"
        style={{
          opacity: 1,
          // In real-time mode, transition is set dynamically in useLayoutEffect
          // For non-real-time, use conditional transition
          transition: realTime
            ? 'd 0.15s linear'
            : pathChanged
            ? 'd 0.2s ease-out'
            : 'none',
          willChange: realTime ? 'd' : 'auto',
          shapeRendering: 'geometricPrecision',
        }}
      />
    </g>
  );
};

interface DataPointsProps {
  visibleData: TimeSeriesDataPoint[];
  scales: ScaleFunctions;
  color: string;
  hoveredPoint: TimeSeriesDataPoint | null;
  padding: { top: number; left: number };
}

export const DataPoints: React.FC<DataPointsProps> = ({
  visibleData,
  scales,
  color,
  hoveredPoint,
  padding,
}) => {
  // Only render points if reasonable amount for performance
  if (visibleData.length > 500) return null;

  return (
    <>
      {visibleData.map((point, index) => {
        const timestamp = parseTimestamp(point.timestamp);
        if (timestamp === null) return null;

        const x = scales.xScale(timestamp);
        const y = scales.yScale(point.value);

        if (isNaN(x) || isNaN(y) || !isFinite(x) || !isFinite(y)) {
          return null;
        }

        const isHovered = hoveredPoint?.timestamp === point.timestamp;
        const translateX = x + padding.left;
        const translateY = y + padding.top;

        if (isNaN(translateX) || isNaN(translateY) || !isFinite(translateX) || !isFinite(translateY)) {
          return null;
        }

        return (
          <g
            key={`point-${point.timestamp}-${index}`}
            transform={`translate(${translateX}, ${translateY})`}
          >
            <circle
              r={isHovered ? 6 : 4}
              fill={color}
              stroke="#1E3A8A"
              strokeWidth={isHovered ? 3 : 2}
              className="transition-all duration-300 ease-out cursor-pointer"
              style={{
                filter: isHovered
                  ? 'drop-shadow(0 0 4px rgba(59, 130, 246, 0.8))'
                  : 'none',
                opacity: 1,
              }}
            />
          </g>
        );
      })}
    </>
  );
};

interface AxisLabelsProps {
  yTicks: Array<{ value: number; y: number }>;
  xTicks: Array<{ x: number; timestamp: string }>;
  dimensions: ChartDimensions;
  realTime: boolean;
}

export const AxisLabels: React.FC<AxisLabelsProps> = ({
  yTicks,
  xTicks,
  dimensions,
  realTime,
}) => {
  return (
    <>
      {/* Y-axis labels */}
      <g>
        {yTicks.map((tick, i) => (
          <g key={`y-label-${i}`}>
            <text
              x={dimensions.padding.left - 10}
              y={tick.y + dimensions.padding.top + 4}
              textAnchor="end"
              className="text-xs fill-gray-400"
              style={{
                transition: realTime ? 'y 0.3s ease-out' : 'none',
              }}
            >
              {tick.value.toFixed(2)}
            </text>
          </g>
        ))}
      </g>

      {/* X-axis labels */}
      <g>
        {xTicks.map((tick, i) => (
          <g key={`x-label-${i}`}>
            <text
              x={tick.x + dimensions.padding.left}
              y={dimensions.height - dimensions.padding.bottom + 15}
              textAnchor="middle"
              className="text-xs fill-gray-400"
              style={{ dominantBaseline: 'hanging' }}
            >
              {formatTime(tick.timestamp)}
            </text>
            <text
              x={tick.x + dimensions.padding.left}
              y={dimensions.height - dimensions.padding.bottom + 28}
              textAnchor="middle"
              className="text-xs fill-gray-500"
              style={{ dominantBaseline: 'hanging' }}
            >
              {formatDate(tick.timestamp)}
            </text>
          </g>
        ))}
      </g>
    </>
  );
};

interface HoverIndicatorProps {
  hoverPosition: HoverPosition;
  color: string;
  dimensions: ChartDimensions;
}

export const HoverIndicator: React.FC<HoverIndicatorProps> = ({
  hoverPosition,
  color,
  dimensions,
}) => {
  return (
    <g>
      <line
        x1={hoverPosition.x}
        y1={dimensions.padding.top}
        x2={hoverPosition.x}
        y2={dimensions.height - dimensions.padding.bottom}
        stroke={color}
        strokeWidth="1.5"
        strokeDasharray="4,4"
        opacity="0.6"
      />
      <circle
        cx={hoverPosition.x}
        cy={hoverPosition.y}
        r="6"
        fill={color}
        stroke="#1E3A8A"
        strokeWidth="3"
        style={{ filter: 'drop-shadow(0 0 6px rgba(59, 130, 246, 0.8))' }}
      />
    </g>
  );
};

interface TooltipProps {
  hoveredPoint: TimeSeriesDataPoint;
  hoverPosition: HoverPosition;
  chartWidth: number;
  containerWidth?: number;
}

export const Tooltip: React.FC<TooltipProps> = ({
  hoveredPoint,
  hoverPosition,
  chartWidth,
  containerWidth,
}) => {
  if (hoverPosition.pixelX === undefined || hoverPosition.pixelY === undefined) {
    return null;
  }

  return (
    <div
      className="absolute bg-gray-800 border border-gray-700 rounded-lg shadow-xl p-3 pointer-events-none z-10"
      style={{
        left: `${Math.min(
          hoverPosition.pixelX + 10,
          (containerWidth || chartWidth) - 200
        )}px`,
        top: `${Math.max(hoverPosition.pixelY - 60, 10)}px`,
        transform: 'translateX(-50%)',
      }}
    >
      <div className="text-xs text-gray-400 mb-1">
        {formatDate(hoveredPoint.timestamp)} {formatTime(hoveredPoint.timestamp)}
      </div>
      <div className="text-sm font-semibold text-white">
        Value: <span className="text-blue-400">{hoveredPoint.value.toFixed(2)}</span>
      </div>
      {hoveredPoint.device_id && (
        <div className="text-xs text-gray-400 mt-1">
          Device: {hoveredPoint.device_id}
        </div>
      )}
    </div>
  );
};

