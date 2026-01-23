/**
 * Time Series Chart Component
 * Professional line chart with hover, zoom, and real-time updates
 * Optimized for smooth, stutter-free updates
 */

import { useState, useRef, useEffect, useLayoutEffect, useCallback, useMemo, memo } from 'react';
import { TimeSeriesChartProps, TimeSeriesDataPoint, ChartDimensions, ScaleFunctions } from './types';
import { sampleData, parseTimestamp } from './utils';
import { processRealTimeUpdate, DataProcessorState } from './dataProcessor';
import { calculateScales, generateYTicks, generateStableYTicks, generateXTicks, ScaleState } from './scales';
import { generateLinePath, generateAreaPath, hasPathChanged } from './paths';
import { handleMouseMove } from './interactions';
import {
  GridLines,
  AreaPath,
  LinePath,
  DataPoints,
  AxisLabels,
  HoverIndicator,
  Tooltip,
} from './renderers';

export const TimeSeriesChart = ({
  data,
  height = 400,
  color = '#3B82F6',
  showGrid = true,
  showLegend = false,
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

  // Refs for DOM elements and state
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const previousPathRef = useRef<string>('');
  const rafRef = useRef<number | null>(null);
  const linePathRef = useRef<SVGPathElement>(null);
  const areaPathRef = useRef<SVGPathElement>(null);
  const updateScheduledRef = useRef(false);
  const dataUpdateRef = useRef<TimeSeriesDataPoint[] | null>(null);

  // Store display data in ref to avoid triggering re-renders
  const displayDataRef = useRef<TimeSeriesDataPoint[]>([]);
  const visibleDataRef = useRef<TimeSeriesDataPoint[]>([]);
  const scalesRef = useRef<ScaleFunctions | null>(null);

  // State - only for initial render and major changes
  const [hoveredPoint, setHoveredPoint] = useState<TimeSeriesDataPoint | null>(null);
  const [hoverPosition, setHoverPosition] = useState<{ x: number; y: number; pixelX?: number; pixelY?: number } | null>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [, forceUpdate] = useState(0); // Force update trigger

  // Data processor state (stored in ref to avoid re-renders)
  const dataProcessorStateRef = useRef<DataProcessorState>({
    previousData: [],
    stableYRange: null,
    yRangeUpdateCounter: 0,
  });

  // Scale state (stored in ref to avoid re-renders)
  const scaleStateRef = useRef<ScaleState>({
    previousYRange: null,
    stableYRange: null,
    yRangeUpdateCounter: 0,
    previousYTicks: [],
    stableTimeWindow: null, // Track time window to prevent X-axis jumping
  });

  // Chart dimensions
  const padding = { top: 20, right: 40, bottom: 60, left: 60 };
  const chartHeight = height;
  const chartWidth = containerWidth > 0 ? containerWidth : 800;
  const innerWidth = Math.max(0, chartWidth - padding.left - padding.right);
  const innerHeight = Math.max(0, chartHeight - padding.top - padding.bottom);

  const dimensions: ChartDimensions = useMemo(() => ({
    width: chartWidth,
    height: chartHeight,
    padding,
    innerWidth,
    innerHeight,
  }), [chartWidth, chartHeight, innerWidth, innerHeight]);

  // Update container width on resize
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        const containerPadding = 32;
        const actualWidth = containerRef.current.clientWidth;
        const width = Math.max(actualWidth - containerPadding, 400);
        setContainerWidth(width);
      }
    };

    let attempts = 0;
    const tryUpdate = () => {
      if (containerRef.current && containerRef.current.clientWidth > 0) {
        updateWidth();
      } else if (attempts < 10) {
        attempts++;
        requestAnimationFrame(tryUpdate);
      }
    };
    
    requestAnimationFrame(tryUpdate);

    const resizeObserver = new ResizeObserver(() => {
      requestAnimationFrame(() => {
        updateWidth();
      });
    });

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    const handleResize = () => {
      requestAnimationFrame(() => {
        updateWidth();
      });
    };
    window.addEventListener('resize', handleResize);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // Process data updates without triggering re-renders
  useEffect(() => {
    // Ensure container width is up to date
    if (containerRef.current && containerWidth === 0) {
      const containerPadding = 32;
      const actualWidth = containerRef.current.clientWidth;
      const width = Math.max(actualWidth - containerPadding, 400);
      if (width > 0) {
        setContainerWidth(width);
      }
    }

    if (data.length === 0) {
      dataProcessorStateRef.current = {
        previousData: [],
        stableYRange: null,
        yRangeUpdateCounter: 0,
      };
      displayDataRef.current = [];
      visibleDataRef.current = [];
      scalesRef.current = null;
      // Only force update if we had data before
      if (displayDataRef.current.length > 0) {
        forceUpdate(prev => prev + 1);
      }
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      return;
    }

    // Clear any pending RAF
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
    }

    // Process data update using requestAnimationFrame for smooth updates
    // CRITICAL: This runs in useEffect, so it doesn't trigger React re-render
    rafRef.current = requestAnimationFrame(() => {
      const state = dataProcessorStateRef.current;
      let processedData: TimeSeriesDataPoint[];
      let needsFullRender = false;

      if (realTime) {
        // Real-time mode: merge data smoothly
        const result = processRealTimeUpdate(
          state.previousData,
          data,
          state
        );
        processedData = result.displayData;
        dataProcessorStateRef.current = result.updatedState;
        // In real-time mode, NEVER trigger full re-render
        needsFullRender = false;
      } else {
        // Non-real-time mode: check if different dataset
        const isDifferent = 
          state.previousData.length === 0 ||
          state.previousData.length !== data.length ||
          (data.length > 0 && state.previousData.length > 0 && (
            state.previousData[0]?.timestamp !== data[0]?.timestamp ||
            state.previousData[state.previousData.length - 1]?.timestamp !== data[data.length - 1]?.timestamp
          ));

        if (isDifferent) {
          processedData = data;
          dataProcessorStateRef.current = {
            ...state,
            previousData: data,
          };
          // Different dataset - need full re-render
          needsFullRender = true;
        } else {
          // Same dataset, keep current display data
          processedData = state.previousData;
          needsFullRender = false;
        }
      }

      // Update refs without triggering re-render
      displayDataRef.current = processedData;
      dataUpdateRef.current = processedData;
      
      // Mark that we need to update the DOM
      updateScheduledRef.current = true;
      
      if (needsFullRender) {
        // Only trigger React re-render for truly different datasets
        forceUpdate(prev => prev + 1);
      } else {
        // Directly update DOM in next animation frame - NO React re-render
        // This is the key to eliminating flicker
        requestAnimationFrame(() => {
          updateChartDOM();
        });
      }
      
      rafRef.current = null;
    });

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [data, realTime, containerWidth]);

  // Direct DOM update function - completely bypasses React rendering
  // This function is called directly from RAF, not from React lifecycle
  const updateChartDOM = useCallback(() => {
    // Only update if we have data
    if (displayDataRef.current.length === 0) {
      return;
    }

    // Get current dimensions from refs/state (avoid closure issues)
    const currentWidth = containerWidth > 0 ? containerWidth : 800;
    const currentInnerWidth = Math.max(0, currentWidth - padding.left - padding.right);
    const currentInnerHeight = Math.max(0, chartHeight - padding.top - padding.bottom);
    
    const currentDimensions: ChartDimensions = {
      width: currentWidth,
      height: chartHeight,
      padding,
      innerWidth: currentInnerWidth,
      innerHeight: currentInnerHeight,
    };

    // In real-time mode, use sliding window approach to maintain continuity
    let visibleData: TimeSeriesDataPoint[];
    const maxPoints = realTime ? 1500 : 2000;
    
    if (realTime && visibleDataRef.current.length > 0 && displayDataRef.current.length > 0) {
      // Check if new data extends previous data
      const prevLastTime = parseTimestamp(
        visibleDataRef.current[visibleDataRef.current.length - 1]?.timestamp || ''
      );
      const newFirstTime = parseTimestamp(displayDataRef.current[0]?.timestamp || '');
      const newLastTime = parseTimestamp(
        displayDataRef.current[displayDataRef.current.length - 1]?.timestamp || ''
      );
      
      // If new data extends previous data (time window continues)
      if (prevLastTime && newFirstTime && newLastTime && 
          newFirstTime >= prevLastTime - 60000) { // Allow 1 minute overlap
        // Continuous - use displayData directly (it's already merged in dataProcessor)
        visibleData = sampleData(displayDataRef.current, maxPoints);
      } else if (prevLastTime && newFirstTime && newLastTime && 
                 newFirstTime < prevLastTime && newLastTime > prevLastTime) {
        // New data overlaps - use displayData (already merged)
        visibleData = sampleData(displayDataRef.current, maxPoints);
      } else {
        // Time window changed significantly - use new data
        visibleData = sampleData(displayDataRef.current, maxPoints);
      }
    } else {
      // Non-real-time or first load
      visibleData = sampleData(displayDataRef.current, maxPoints);
    }
    
    visibleDataRef.current = visibleData;

    // Calculate scales - this will use stable Y-range in real-time mode
    const scaleResult = calculateScales(
      visibleData,
      currentDimensions,
      realTime,
      scaleStateRef.current
    );

    if (scaleResult.updatedState) {
      scaleStateRef.current = scaleResult.updatedState;
    }

    if (!scaleResult.scales) {
      return;
    }

    scalesRef.current = scaleResult.scales;

    // Generate paths
    const linePath = generateLinePath(visibleData, scaleResult.scales);
    const areaPath = generateAreaPath(linePath, visibleData, scaleResult.scales);

    // Update SVG paths directly - NO React involvement
    // This is the key to eliminating flicker
    if (linePathRef.current && linePath) {
      if (realTime && previousPathRef.current && previousPathRef.current !== linePath) {
        // In real-time mode, use CSS transition for smooth path updates
        linePathRef.current.style.transition = 'd 0.15s linear';
        linePathRef.current.setAttribute('d', linePath);
      } else {
        // Non-real-time or first render - no transition
        linePathRef.current.style.transition = 'none';
        linePathRef.current.setAttribute('d', linePath);
      }
      previousPathRef.current = linePath;
    }

    if (areaPathRef.current && areaPath) {
      if (realTime && previousPathRef.current) {
        // In real-time mode, use CSS transition for smooth path updates
        areaPathRef.current.style.transition = 'd 0.15s linear';
        areaPathRef.current.setAttribute('d', areaPath);
      } else {
        // Non-real-time or first render - no transition
        areaPathRef.current.style.transition = 'none';
        areaPathRef.current.setAttribute('d', areaPath);
      }
    }

    updateScheduledRef.current = false;
  }, [realTime, containerWidth, chartHeight, padding]);

  // Initial render and dimension changes only - use useLayoutEffect for initial setup
  useLayoutEffect(() => {
    if (displayDataRef.current.length > 0) {
      updateChartDOM();
    }
  }, [containerWidth, height, updateChartDOM]); // Only re-render on dimension changes

  // Calculate scales for initial render only
  // Subsequent updates are handled by updateChartDOM() directly
  const { scales } = useMemo(() => {
    // Only calculate on initial render or dimension change
    // Data updates are handled by updateChartDOM() to avoid re-renders
    const visibleData = visibleDataRef.current.length > 0 
      ? visibleDataRef.current 
      : (displayDataRef.current.length > 0 
          ? sampleData(displayDataRef.current, realTime ? 1500 : 2000)
          : []);

    if (visibleData.length === 0) {
      return { scales: scalesRef.current };
    }

    const result = calculateScales(
      visibleData,
      dimensions,
      realTime,
      scaleStateRef.current
    );
    
    if (result.updatedState) {
      scaleStateRef.current = result.updatedState;
    }

    scalesRef.current = result.scales;
    if (visibleDataRef.current.length === 0) {
      visibleDataRef.current = visibleData;
    }
    
    return {
      scales: result.scales,
    };
  }, [dimensions, realTime, containerWidth]); // Only recalculate on dimension changes

  // Generate paths for initial render
  const linePath = useMemo(() => {
    if (!scales || visibleDataRef.current.length === 0) return '';
    return generateLinePath(visibleDataRef.current, scales);
  }, [scales, containerWidth]);

  const areaPath = useMemo(() => {
    if (!scales || !linePath || visibleDataRef.current.length === 0) return '';
    return generateAreaPath(linePath, visibleDataRef.current, scales);
  }, [linePath, scales]);

  const pathChanged = useMemo(() => {
    const changed = hasPathChanged(linePath, previousPathRef.current);
    if (changed) {
      previousPathRef.current = linePath;
    }
    return changed;
  }, [linePath]);

  // Generate axis ticks
  const yTicks = useMemo(() => {
    const currentScales = scales || scalesRef.current;
    if (!currentScales) return [];
    return generateYTicks(currentScales.yScale, currentScales.minValue, currentScales.maxValue);
  }, [scales, containerWidth]);

  const stableYTicks = useMemo(() => {
    const result = generateStableYTicks(
      yTicks,
      scaleStateRef.current.previousYTicks,
      realTime
    );
    scaleStateRef.current.previousYTicks = result.updatedPrevious;
    return result.ticks;
  }, [yTicks, realTime]);

  const xTicks = useMemo(() => {
    const currentScales = scales || scalesRef.current;
    const currentVisibleData = visibleDataRef.current;
    if (!currentScales || currentVisibleData.length === 0) return [];
    return generateXTicks(currentVisibleData, currentScales.xScale, innerWidth);
  }, [scales, innerWidth, containerWidth]);

  // Handle mouse interactions
  const handleMouseMoveEvent = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const currentScales = scales || scalesRef.current;
    const currentVisibleData = visibleDataRef.current;
    if (!svgRef.current || !currentScales || currentVisibleData.length === 0) return;

    const containerRect = containerRef.current?.getBoundingClientRect() || null;
    const result = handleMouseMove(
      e,
      svgRef.current,
      currentVisibleData,
      currentScales,
      padding,
      containerRect,
      onHover
    );

    setHoveredPoint(result.hoveredPoint);
    setHoverPosition(result.hoverPosition);
  }, [scales, padding, onHover]);

  const handleMouseLeaveEvent = useCallback(() => {
    setHoveredPoint(null);
    setHoverPosition(null);
    if (onHover) onHover(null);
  }, [onHover]);

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
  if (!currentScales) {
    return (
      <div className="flex items-center justify-center h-full text-yellow-400 bg-gray-900/50 rounded-lg p-8">
        <div className="text-center">
          <p className="text-lg mb-2">Chart scales not ready</p>
          <p className="text-sm text-gray-500">Please wait...</p>
        </div>
      </div>
    );
  }

  try {
    return (
      <div ref={containerRef} className="relative w-full bg-gray-900/30 rounded-lg border border-gray-700/50 p-4">
        {/* Controls */}
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

        {/* Chart */}
        <div className="relative w-full" style={{ height: `${chartHeight}px` }}>
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
// In real-time mode, we allow data updates to pass through but handle them internally
export const TimeSeriesChartMemo = memo(TimeSeriesChart, (prevProps, nextProps) => {
  // Both empty, no need to re-render
  if (prevProps.data.length === 0 && nextProps.data.length === 0) return true;
  
  // For real-time mode, be VERY strict - only re-render if truly different
  if (prevProps.realTime && nextProps.realTime) {
    // Check if it's the same array reference (same object)
    if (prevProps.data === nextProps.data) {
      return true; // Same reference, no re-render needed
    }
    
    // Check if first timestamp changed (indicates different time range)
    if (prevProps.data.length > 0 && nextProps.data.length > 0) {
      const prevFirst = prevProps.data[0];
      const nextFirst = nextProps.data[0];
      
      // If first timestamp changed significantly (more than 1 minute), it's different
      if (prevFirst?.timestamp && nextFirst?.timestamp) {
        const prevFirstTime = new Date(prevFirst.timestamp).getTime();
        const nextFirstTime = new Date(nextFirst.timestamp).getTime();
        if (Math.abs(prevFirstTime - nextFirstTime) > 60000) {
          return false; // Different time range, need re-render
        }
      }
      
      // Check if only last point changed (incremental update)
      const prevLast = prevProps.data[prevProps.data.length - 1];
      const nextLast = nextProps.data[nextProps.data.length - 1];
      
      if (prevLast?.timestamp === nextLast?.timestamp) {
        // Same last timestamp - might be value update or new points
        // In real-time, we handle this internally, don't re-render
        // Only check if other props changed
        if (
          prevProps.height !== nextProps.height ||
          prevProps.color !== nextProps.color ||
          prevProps.showGrid !== nextProps.showGrid
        ) {
          return false;
        }
        // Data update will be handled by internal updateChartDOM()
        // Don't trigger React re-render
        return true;
      }
      
      // Last timestamp changed - might be new data appended
      // Check if it's just extension (new data after last point)
      if (prevLast?.timestamp && nextLast?.timestamp) {
        const prevLastTime = new Date(prevLast.timestamp).getTime();
        const nextLastTime = new Date(nextLast.timestamp).getTime();
        
        // If new last time is after old last time, it's just extension
        // Handle internally, don't re-render
        if (nextLastTime > prevLastTime) {
          // Check other props
          if (
            prevProps.height !== nextProps.height ||
            prevProps.color !== nextProps.color ||
            prevProps.showGrid !== nextProps.showGrid
          ) {
            return false;
          }
          return true; // Just extension, handle internally
        }
      }
    }
    
    // Check other props
    if (
      prevProps.height !== nextProps.height ||
      prevProps.color !== nextProps.color ||
      prevProps.showGrid !== nextProps.showGrid
    ) {
      return false;
    }
    
    // In real-time mode, data updates are handled internally
    // Don't trigger React re-render for data changes
    return true;
  }
  
  // For non-real-time mode, use stricter comparison
  const lengthDiff = Math.abs(prevProps.data.length - nextProps.data.length);
  const maxLength = Math.max(prevProps.data.length, nextProps.data.length);
  if (maxLength > 0 && lengthDiff / maxLength > 0.1) {
    return false;
  }
  
  // If both have data, compare first and last points
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
  
  // Check other props
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

