/**
 * Time Series Chart Component
 * Professional line chart with hover, zoom, and real-time updates
 * Optimized for smooth, stutter-free updates
 */

import { useState, useRef, useLayoutEffect, memo } from 'react';
import { TimeSeriesChartProps, TimeSeriesDataPoint } from './types';
import {
  GridLines,
  AreaPath,
  LinePath,
  DataPoints,
  AxisLabels,
  HoverIndicator,
  Tooltip,
} from './renderers';
import {
  useChartDimensions,
  useChartDOMUpdate,
  useDataProcessing,
  useChartScales,
  useChartPaths,
  useChartInteractions,
} from './hooks';

export const TimeSeriesChart = ({
  data,
  height = 400,
  color = '#3B82F6',
  showGrid = true,
  realTime = false,
  onHover,
}: TimeSeriesChartProps) => {
  // Validate input data
  if (!data || !Array.isArray(data)) {
    console.error('[TimeSeriesChart] Invalid data prop:', data);
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <div className="text-center text-red-400">
          <p>Invalid chart data</p>
        </div>
      </div>
    );
  }

  // Refs for DOM elements
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const linePathRef = useRef<SVGPathElement>(null);
  const areaPathRef = useRef<SVGPathElement>(null);
  const previousPathRef = useRef<string>('');

  // Error state
  const [renderError, setRenderError] = useState<string | null>(null);

  // Chart dimensions and responsive width
  const { containerWidth, dimensions } = useChartDimensions(containerRef, height);
  const padding = dimensions.padding;
  const chartHeight = height;
  const chartWidth = dimensions.width;
  const innerWidth = dimensions.innerWidth;

  // Single source of truth: one pair of refs shared by data processing, scales, and DOM update
  const displayDataRef = useRef<TimeSeriesDataPoint[]>([]);
  const visibleDataRef = useRef<TimeSeriesDataPoint[]>([]);
  const [displayDataVersion, setDisplayDataVersion] = useState(0);

  // Scales first — produces scaleStateRef/scalesRef used by DOM update.
  // displayDataVersion ensures useMemo re-runs when useDataProcessing fills the refs.
  const { scales, scalesRef, scaleStateRef, stableYTicks, xTicks } = useChartScales(
    displayDataRef,
    visibleDataRef,
    dimensions,
    realTime,
    containerWidth,
    innerWidth,
    displayDataVersion
  );

  // DOM update uses the same display/visible refs and scale refs from useChartScales
  const updateChartDOM = useChartDOMUpdate(
    displayDataRef,
    visibleDataRef,
    scaleStateRef,
    scalesRef,
    linePathRef,
    areaPathRef,
    previousPathRef,
    realTime,
    containerWidth,
    chartHeight,
    padding
  );

  // Data processing writes into the same refs that scales and DOM update read.
  // setDisplayDataVersion causes useChartScales to recompute when refs are filled.
  useDataProcessing(data, realTime, containerWidth, updateChartDOM, {
    displayDataRef,
    visibleDataRef,
    onDisplayDataUpdate: () => setDisplayDataVersion((v) => v + 1),
  });

  // Initial render setup
  useLayoutEffect(() => {
    if (displayDataRef.current.length > 0) {
      updateChartDOM();
    }
  }, [containerWidth, height, updateChartDOM, displayDataRef]);

  // Generate paths
  const { linePath, areaPath, pathChanged } = useChartPaths(
    visibleDataRef,
    scales,
    containerWidth
  );

  // Mouse interactions
  const {
    hoveredPoint,
    hoverPosition,
    handleMouseMoveEvent,
    handleMouseLeaveEvent,
  } = useChartInteractions(
    svgRef,
    containerRef,
    visibleDataRef,
    scales,
    padding,
    onHover
  );

  // Error boundary
  if (renderError) {
    return (
      <div className="flex items-center justify-center h-full text-red-400 bg-gray-900/50 rounded-lg p-8">
        <div className="text-center">
          <p className="text-lg mb-2">Chart rendering error</p>
          <p className="text-sm text-gray-500">{renderError}</p>
          <button
            onClick={() => setRenderError(null)}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 bg-gray-900/50 rounded-lg p-8">
        <div className="text-center">
          <p className="text-lg mb-2">No data available</p>
          <p className="text-sm text-gray-500">Select devices and metrics to view time series data</p>
        </div>
      </div>
    );
  }

  const currentScales = scales || scalesRef.current;

  // Always mount the container so useChartDimensions can measure width.
  // When scales aren't ready, show same layout with empty chart area (no "please wait" text);
  // when ready, chart fades in for a smooth transition.
  try {
    return (
      <div
        ref={containerRef}
        className="relative w-full bg-gray-900/30 rounded-lg border border-gray-700/50 p-4"
      >
        {/* Controls — keep layout stable */}
        <div className="flex items-center justify-end mb-4">
          <div className="text-xs text-gray-500">
            {realTime && (
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                Live
              </span>
            )}
          </div>
        </div>

        {/* Chart area: empty placeholder when scales not ready, chart with fade-in when ready */}
        {!currentScales ? (
          <div
            className="relative w-full bg-gray-800/20 rounded"
            style={{ height: `${chartHeight}px` }}
            aria-hidden
          />
        ) : (
          <>
            <div
              className="relative w-full chart-fade-in"
              style={{ height: `${chartHeight}px` }}
            >
              <svg
                ref={svgRef}
                width="100%"
                height={chartHeight}
                viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                preserveAspectRatio="xMidYMid meet"
                className="cursor-crosshair"
                style={{
                  display: 'block',
                  width: '100%',
                  willChange: realTime ? 'contents' : 'auto',
                  minHeight: `${chartHeight}px`,
                }}
                onMouseMove={handleMouseMoveEvent}
                onMouseLeave={handleMouseLeaveEvent}
              >
                <defs>
                  <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor={color} stopOpacity="0.3" />
                    <stop offset="100%" stopColor={color} stopOpacity="0.05" />
                  </linearGradient>
                  <filter id="glow">
                    <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                    <feMerge>
                      <feMergeNode in="coloredBlur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>

                <GridLines
                  yTicks={stableYTicks}
                  xTicks={xTicks}
                  dimensions={dimensions}
                  showGrid={showGrid}
                />

                <AreaPath
                  areaPath={areaPath}
                  color={color}
                  realTime={realTime}
                  pathChanged={pathChanged}
                  padding={padding}
                  pathRef={areaPathRef}
                />

                <LinePath
                  linePath={linePath}
                  color={color}
                  realTime={realTime}
                  pathChanged={pathChanged}
                  padding={padding}
                  pathRef={linePathRef}
                />

                {currentScales && visibleDataRef.current.length > 0 && (
                  <DataPoints
                    visibleData={visibleDataRef.current}
                    scales={currentScales}
                    color={color}
                    hoveredPoint={hoveredPoint}
                    padding={padding}
                  />
                )}

                <AxisLabels
                  yTicks={stableYTicks}
                  xTicks={xTicks}
                  dimensions={dimensions}
                  realTime={realTime}
                />

                {hoveredPoint && hoverPosition && (
                  <HoverIndicator
                    hoverPosition={hoverPosition}
                    color={color}
                    dimensions={dimensions}
                  />
                )}
              </svg>

              {hoveredPoint && hoverPosition && (
                <Tooltip
                  hoveredPoint={hoveredPoint}
                  hoverPosition={hoverPosition}
                  chartWidth={chartWidth}
                  containerWidth={containerRef.current?.clientWidth}
                />
              )}
            </div>

            {/* Instructions */}
            <div className="mt-4 text-xs text-gray-500 flex items-center justify-center">
              <span>🖱️ Hover to see values</span>
            </div>
          </>
        )}
      </div>
    );
  } catch (error) {
    console.error('[TimeSeriesChart] Rendering error:', error);
    const errorMessage = error instanceof Error ? error.message : String(error);
    setRenderError(errorMessage);
    return (
      <div className="flex items-center justify-center h-full text-red-400 bg-gray-900/50 rounded-lg p-8">
        <div className="text-center">
          <p className="text-lg mb-2">Chart rendering error</p>
          <p className="text-sm text-gray-500">{errorMessage}</p>
          <button
            onClick={() => setRenderError(null)}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }
};

// Memoized version with ultra-strict comparison to prevent unnecessary re-renders
export const TimeSeriesChartMemo = memo(TimeSeriesChart, (prevProps, nextProps) => {
  if (prevProps.data.length === 0 && nextProps.data.length === 0) return true;

  if (prevProps.realTime && nextProps.realTime) {
    if (prevProps.data === nextProps.data) {
      return true;
    }

    if (prevProps.data.length > 0 && nextProps.data.length > 0) {
      const prevFirst = prevProps.data[0];
      const nextFirst = nextProps.data[0];

      if (prevFirst?.timestamp && nextFirst?.timestamp) {
        const prevFirstTime = new Date(prevFirst.timestamp).getTime();
        const nextFirstTime = new Date(nextFirst.timestamp).getTime();
        if (Math.abs(prevFirstTime - nextFirstTime) > 60000) {
          return false;
        }
      }

      const prevLast = prevProps.data[prevProps.data.length - 1];
      const nextLast = nextProps.data[nextProps.data.length - 1];

      if (prevLast?.timestamp === nextLast?.timestamp) {
        if (
          prevProps.height !== nextProps.height ||
          prevProps.color !== nextProps.color ||
          prevProps.showGrid !== nextProps.showGrid
        ) {
          return false;
        }
        return true;
      }

      if (prevLast?.timestamp && nextLast?.timestamp) {
        const prevLastTime = new Date(prevLast.timestamp).getTime();
        const nextLastTime = new Date(nextLast.timestamp).getTime();

        if (nextLastTime > prevLastTime) {
          if (
            prevProps.height !== nextProps.height ||
            prevProps.color !== nextProps.color ||
            prevProps.showGrid !== nextProps.showGrid
          ) {
            return false;
          }
          return true;
        }
      }
    }

    if (
      prevProps.height !== nextProps.height ||
      prevProps.color !== nextProps.color ||
      prevProps.showGrid !== nextProps.showGrid
    ) {
      return false;
    }

    return true;
  }

  const lengthDiff = Math.abs(prevProps.data.length - nextProps.data.length);
  const maxLength = Math.max(prevProps.data.length, nextProps.data.length);
  if (maxLength > 0 && lengthDiff / maxLength > 0.1) {
    return false;
  }

  if (prevProps.data.length > 0 && nextProps.data.length > 0) {
    const prevFirst = prevProps.data[0];
    const nextFirst = nextProps.data[0];
    const prevLast = prevProps.data[prevProps.data.length - 1];
    const nextLast = nextProps.data[nextProps.data.length - 1];

    if (
      prevFirst?.timestamp !== nextFirst?.timestamp ||
      prevLast?.timestamp !== nextLast?.timestamp
    ) {
      return false;
    }
  }

  if (
    prevProps.height !== nextProps.height ||
    prevProps.color !== nextProps.color ||
    prevProps.showGrid !== nextProps.showGrid ||
    prevProps.realTime !== nextProps.realTime
  ) {
    return false;
  }

  return true;
});
