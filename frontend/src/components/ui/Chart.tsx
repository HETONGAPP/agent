/**
 * Chart Component
 * Enhanced chart component with modern design, animations, and interactivity
 */

import { useState, useMemo } from 'react';

// Helper function to convert hex to RGB
function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : null;
}

interface ChartData {
  label: string;
  value: number;
  color?: string;
}

interface ChartProps {
  data: ChartData[];
  type?: 'bar' | 'line' | 'pie';
  height?: number;
  showLabels?: boolean;
  showGrid?: boolean;
  showLegend?: boolean;
}

export const Chart = ({ 
  data, 
  type = 'bar', 
  height = 200, 
  showLabels = true,
  showGrid = true,
  showLegend = false
}: ChartProps) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; label: string; value: number } | null>(null);

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center">
          <div className="text-4xl mb-2">📊</div>
          <div>No data available</div>
        </div>
      </div>
    );
  }

  const maxValue = Math.max(...data.map((d) => d.value));
  const chartId = useMemo(() => `chart-${Math.random().toString(36).substr(2, 9)}`, []);

  if (type === 'bar') {
    const padding = { top: 30, right: 20, bottom: 50, left: 20 };
    const chartHeight = height - padding.top - padding.bottom;
    const chartWidth = 100 - padding.left - padding.right;

    return (
      <div className="w-full relative" style={{ height: `${height}px` }}>
        <svg width="100%" height={height} className="overflow-visible">
          <defs>
            {/* Enhanced gradient definitions for each bar with glow effect */}
            {data.map((item, index) => {
              const gradientId = `${chartId}-gradient-${index}`;
              const glowId = `${chartId}-glow-${index}`;
              const baseColor = item.color || '#3B82F6';
              
              // Create a more vibrant gradient
              const rgb = hexToRgb(baseColor);
              return (
                <g key={gradientId}>
                  <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor={baseColor} stopOpacity="1" />
                    <stop offset="50%" stopColor={baseColor} stopOpacity="0.9" />
                    <stop offset="100%" stopColor={baseColor} stopOpacity="0.6" />
                  </linearGradient>
                  {/* Glow effect for hover */}
                  <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                    <feMerge>
                      <feMergeNode in="coloredBlur"/>
                      <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                  </filter>
                </g>
              );
            })}
            {/* Enhanced shadow filter */}
            <filter id={`${chartId}-shadow`} x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur in="SourceAlpha" stdDeviation="4" />
              <feOffset dx="0" dy="4" result="offsetblur" />
              <feComponentTransfer>
                <feFuncA type="linear" slope="0.4" />
              </feComponentTransfer>
              <feMerge>
                <feMergeNode />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Grid lines with better styling */}
          {showGrid && (
            <g className="opacity-10">
              {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                const y = padding.top + chartHeight - (ratio * chartHeight);
                return (
                  <line
                    key={ratio}
                    x1={`${padding.left}%`}
                    y1={y}
                    x2={`${100 - padding.right}%`}
                    y2={y}
                    stroke="currentColor"
                    strokeWidth="1"
                    strokeDasharray="4 4"
                    className="text-gray-500"
                  />
                );
              })}
            </g>
          )}

          {/* Bars with modern design */}
          {data.map((item, index) => {
            const barHeight = (item.value / maxValue) * chartHeight;
            const barWidth = chartWidth / data.length;
            const x = padding.left + (index * chartWidth / data.length);
            const y = padding.top + chartHeight - barHeight;
            const isHovered = hoveredIndex === index;
            const barPadding = 0.15; // More spacing between bars
            const barActualWidth = barWidth * (1 - barPadding * 2);

            return (
              <g 
                key={index}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
                className="cursor-pointer"
              >
                {/* Animated background glow */}
                {isHovered && (
                  <rect
                    x={`${x + barWidth * barPadding}%`}
                    y={padding.top}
                    width={`${barActualWidth}%`}
                    height={chartHeight}
                    fill={item.color || '#3B82F6'}
                    opacity="0.05"
                    rx="8"
                    className="transition-opacity duration-300"
                  />
                )}
                
                {/* Bar shadow with blur */}
                <rect
                  x={`${x + barWidth * barPadding}%`}
                  y={y + 4}
                  width={`${barActualWidth}%`}
                  height={barHeight}
                  fill="black"
                  opacity={isHovered ? 0.2 : 0.1}
                  rx="8"
                  className="transition-all duration-300"
                />
                
                {/* Main bar with rounded top corners */}
                <rect
                  x={`${x + barWidth * barPadding}%`}
                  y={y}
                  width={`${barActualWidth}%`}
                  height={barHeight}
                  fill={`url(#${chartId}-gradient-${index})`}
                  rx="8"
                  ry="8"
                  className="transition-all duration-300"
                  style={{
                    transform: isHovered ? 'translateY(-6px) scaleY(1.05)' : 'translateY(0) scaleY(1)',
                    transformOrigin: 'bottom',
                    filter: isHovered ? `url(#${chartId}-glow-${index}) url(#${chartId}-shadow)` : 'none',
                  }}
                />
                
                {/* Top highlight line */}
                <line
                  x1={`${x + barWidth * barPadding}%`}
                  y1={y}
                  x2={`${x + barWidth * (1 - barPadding)}%`}
                  y2={y}
                  stroke="white"
                  strokeWidth="2"
                  opacity="0.3"
                  className="transition-opacity duration-300"
                  style={{ opacity: isHovered ? 0.5 : 0.3 }}
                />
                
                {/* Value label with better styling */}
                {showLabels && (
                  <g>
                    <rect
                      x={`${x + barWidth * 0.5}%`}
                      y={y - 24}
                      width="40"
                      height="18"
                      fill="rgba(0, 0, 0, 0.7)"
                      rx="4"
                      transform={`translate(-20, 0)`}
                      className="transition-opacity duration-300"
                      style={{ opacity: isHovered ? 1 : 0 }}
                    />
                    <text
                      x={`${x + barWidth * 0.5}%`}
                      y={y - 12}
                      textAnchor="middle"
                      className="text-xs fill-white font-bold transition-opacity"
                      style={{ opacity: isHovered ? 1 : 0.9 }}
                    >
                      {item.value}
                    </text>
                  </g>
                )}
                
                {/* Category label with better styling */}
                {showLabels && (
                  <text
                    x={`${x + barWidth * 0.5}%`}
                    y={height - padding.bottom + 20}
                    textAnchor="middle"
                    className="text-xs fill-gray-300 font-medium transition-colors"
                    style={{ 
                      fill: isHovered ? '#fff' : '#9CA3AF',
                      fontWeight: isHovered ? '600' : '500'
                    }}
                  >
                    {item.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* Enhanced Tooltip */}
        {hoveredIndex !== null && (
          <div
            className="absolute bg-gray-800/95 backdrop-blur-sm border border-gray-700 rounded-xl px-4 py-2.5 shadow-2xl z-10 pointer-events-none transition-all duration-200"
            style={{
              left: `${padding.left + (hoveredIndex * chartWidth / data.length) + (chartWidth / data.length / 2)}%`,
              top: `${padding.top + chartHeight - (data[hoveredIndex].value / maxValue) * chartHeight - 50}px`,
              transform: 'translateX(-50%)',
            }}
          >
            <div className="flex items-center gap-2 mb-1">
              <div 
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: data[hoveredIndex].color || '#3B82F6' }}
              />
              <div className="text-xs text-gray-400 font-medium">{data[hoveredIndex].label}</div>
            </div>
            <div className="text-lg font-bold text-white">{data[hoveredIndex].value}</div>
            <div className="text-xs text-gray-500 mt-0.5">
              {((data[hoveredIndex].value / maxValue) * 100).toFixed(1)}% of max
            </div>
          </div>
        )}
      </div>
    );
  }

  if (type === 'line') {
    const points = data.map((item, index) => {
      const x = (index / Math.max(data.length - 1, 1)) * 100;
      const y = height - 20 - (item.value / maxValue) * (height - 40);
      return `${x}%,${y}`;
    }).join(' ');

    // Create gradient for line
    const gradientId = `gradient-${Math.random().toString(36).substr(2, 9)}`;

    return (
      <div className="w-full" style={{ height: `${height}px` }}>
        <svg width="100%" height={height} className="overflow-visible">
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.05" />
            </linearGradient>
          </defs>
          
          {/* Area under the line */}
          {data.length > 0 && (
            <polygon
              points={`${points} ${100}%,${height - 20} 0%,${height - 20}`}
              fill={`url(#${gradientId})`}
              className="transition-opacity"
            />
          )}
          
          {/* Line */}
          <polyline
            points={points}
            fill="none"
            stroke="#3B82F6"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="hover:stroke-blue-400 transition-colors"
          />
          
          {/* Data points */}
          {data.map((item, index) => {
            const x = (index / Math.max(data.length - 1, 1)) * 100;
            const y = height - 20 - (item.value / maxValue) * (height - 40);
            return (
              <g key={index}>
                <circle
                  cx={`${x}%`}
                  cy={y}
                  r="4"
                  fill="#3B82F6"
                  stroke="#1E3A8A"
                  strokeWidth="2"
                  className="hover:r-6 transition-all cursor-pointer"
                />
                {showLabels && index % Math.ceil(data.length / 8) === 0 && (
                  <text
                    x={`${x}%`}
                    y={height - 5}
                    textAnchor="middle"
                    className="text-xs fill-gray-400"
                  >
                    {item.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    );
  }

  // Enhanced Pie chart
  let currentAngle = 0;
  const total = data.reduce((sum, item) => sum + item.value, 0);
  const pieSize = Math.min(height - (showLegend ? 60 : 20), 200);
  const radius = pieSize / 2 - 20;
  const centerX = pieSize / 2;
  const centerY = pieSize / 2;

  return (
    <div className="w-full flex flex-col items-center justify-center" style={{ height: `${height}px` }}>
      <div className="relative" style={{ width: `${pieSize}px`, height: `${pieSize}px` }}>
        <svg width={pieSize} height={pieSize} viewBox={`0 0 ${pieSize} ${pieSize}`} className="overflow-visible">
          <defs>
            {/* Shadow filter */}
            <filter id={`${chartId}-pie-shadow`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceAlpha" stdDeviation="4" />
              <feOffset dx="0" dy="3" result="offsetblur" />
              <feComponentTransfer>
                <feFuncA type="linear" slope="0.4" />
              </feComponentTransfer>
              <feMerge>
                <feMergeNode />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {data.map((item, index) => {
            const angle = (item.value / total) * 360;
            const startAngle = currentAngle;
            currentAngle += angle;

            const startAngleRad = (startAngle * Math.PI) / 180;
            const endAngleRad = (currentAngle * Math.PI) / 180;
            const largeArc = angle > 180 ? 1 : 0;

            const x1 = centerX + radius * Math.cos(startAngleRad);
            const y1 = centerY + radius * Math.sin(startAngleRad);
            const x2 = centerX + radius * Math.cos(endAngleRad);
            const y2 = centerY + radius * Math.sin(endAngleRad);

            const midAngle = (startAngle + angle / 2) * Math.PI / 180;
            const labelX = centerX + (radius + 15) * Math.cos(midAngle);
            const labelY = centerY + (radius + 15) * Math.sin(midAngle);
            const percentage = ((item.value / total) * 100).toFixed(1);

            const isHovered = hoveredIndex === index;
            // Fix hover direction: always move outward from center
            const hoverOffset = isHovered ? 8 : 0;
            
            // Calculate hover position: move outward along the angle direction
            const hoverX1 = centerX + (radius + hoverOffset) * Math.cos(startAngleRad);
            const hoverY1 = centerY + (radius + hoverOffset) * Math.sin(startAngleRad);
            const hoverX2 = centerX + (radius + hoverOffset) * Math.cos(endAngleRad);
            const hoverY2 = centerY + (radius + hoverOffset) * Math.sin(endAngleRad);

            return (
              <g 
                key={index}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
                className="cursor-pointer"
              >
                {/* Pie slice */}
                <path
                  d={`M ${centerX} ${centerY} L ${isHovered ? hoverX1 : x1} ${isHovered ? hoverY1 : y1} A ${radius + hoverOffset} ${radius + hoverOffset} 0 ${largeArc} 1 ${isHovered ? hoverX2 : x2} ${isHovered ? hoverY2 : y2} Z`}
                  fill={item.color || `hsl(${(index * 360) / data.length}, 70%, 50%)`}
                  className="transition-all duration-300"
                  style={{
                    filter: isHovered ? `url(#${chartId}-pie-shadow)` : 'none',
                    opacity: isHovered ? 1 : 0.9,
                  }}
                />
                {/* Percentage label - moved further out to avoid overlap */}
                {showLabels && angle > 10 && (
                  <text
                    x={centerX + (radius + 25) * Math.cos(midAngle)}
                    y={centerY + (radius + 25) * Math.sin(midAngle)}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="text-[10px] fill-white font-bold transition-opacity"
                    style={{ opacity: isHovered ? 1 : 0.8 }}
                  >
                    {percentage}%
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* Center circle for donut effect */}
        <div 
          className="absolute bg-gray-900 rounded-full border-2 border-gray-800 flex items-center justify-center shadow-lg"
          style={{
            width: `${radius * 0.65}px`,
            height: `${radius * 0.65}px`,
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
          }}
        >
          <div className="text-center px-1">
            <div className="text-[9px] text-gray-400 leading-tight">Total</div>
            <div className="text-sm font-bold text-white leading-tight">{total}</div>
          </div>
        </div>
      </div>

      {/* Legend */}
      {showLegend && (
        <div className="flex flex-wrap justify-center gap-4 mt-4">
          {data.map((item, index) => (
            <div 
              key={index}
              className="flex items-center gap-2 cursor-pointer px-2 py-1 rounded transition-all"
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex(null)}
              style={{
                backgroundColor: hoveredIndex === index ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
              }}
            >
              <div 
                className="w-3 h-3 rounded-full transition-all shadow-sm"
                style={{ 
                  backgroundColor: item.color || `hsl(${(index * 360) / data.length}, 70%, 50%)`,
                  opacity: hoveredIndex === null || hoveredIndex === index ? 1 : 0.4,
                  transform: hoveredIndex === index ? 'scale(1.2)' : 'scale(1)',
                }}
              />
              <span className="text-xs text-gray-400 transition-colors" style={{ color: hoveredIndex === index ? '#fff' : undefined }}>
                {item.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};


