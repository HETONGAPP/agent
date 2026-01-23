/**
 * Time Series Chart Component
 * Professional line chart with hover, zoom, and real-time updates
 */

import { useState, useRef, useEffect, useCallback, useMemo, memo } from 'react';

export interface TimeSeriesDataPoint {
  timestamp: string;
  value: number;
  label?: string;
  device_id?: string;
}

interface TimeSeriesChartProps {
  data: TimeSeriesDataPoint[];
  height?: number;
  color?: string;
  showGrid?: boolean;
  showLegend?: boolean;
  realTime?: boolean;
  onHover?: (point: TimeSeriesDataPoint | null) => void;
}

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

  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredPoint, setHoveredPoint] = useState<TimeSeriesDataPoint | null>(null);
  const [hoverPosition, setHoverPosition] = useState<{ x: number; y: number; pixelX?: number; pixelY?: number } | null>(null);
  const [displayData, setDisplayData] = useState<TimeSeriesDataPoint[]>([]);
  const [containerWidth, setContainerWidth] = useState(0); // Start with 0 to force initial calculation
  const previousDataRef = useRef<TimeSeriesDataPoint[]>([]);
  const updateTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rafRef = useRef<number | null>(null);
  const pendingDataRef = useRef<TimeSeriesDataPoint[] | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const previousPathRef = useRef<string>(''); // Track previous path to detect actual changes

  // Calculate chart dimensions - responsive width
  const padding = { top: 20, right: 40, bottom: 60, left: 60 }; // Increased bottom padding for labels
  const chartHeight = height;
  // Ensure containerWidth is at least a reasonable minimum to prevent layout issues
  const chartWidth = containerWidth > 0 ? containerWidth : 800; // Fallback to 800 if not calculated yet
  const innerWidth = Math.max(0, chartWidth - padding.left - padding.right);
  const innerHeight = Math.max(0, chartHeight - padding.top - padding.bottom);

  // Update container width on resize - use ResizeObserver for responsive width
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        // Get actual container width
        // The container has p-4 padding (16px on each side = 32px total)
        const containerPadding = 32; // p-4 = 16px * 2
        const actualWidth = containerRef.current.clientWidth;
        // Use the full clientWidth, subtract padding because the SVG should fit inside the padded area
        const width = Math.max(actualWidth - containerPadding, 400); // Minimum 400px width
        setContainerWidth(width);
      }
    };

    // Initial update - use multiple attempts to ensure DOM is ready
    let attempts = 0;
    const tryUpdate = () => {
      if (containerRef.current && containerRef.current.clientWidth > 0) {
        updateWidth();
      } else if (attempts < 10) {
        attempts++;
        requestAnimationFrame(tryUpdate);
      }
    };
    
    // Start trying to update
    requestAnimationFrame(tryUpdate);

    // Use ResizeObserver to watch for container size changes
    const resizeObserver = new ResizeObserver((entries) => {
      // Use requestAnimationFrame to batch updates
      requestAnimationFrame(() => {
        updateWidth();
      });
    });

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    // Also listen to window resize as fallback
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
  }, []); // Empty deps - only run on mount/unmount

  // Smooth data updates with requestAnimationFrame and debouncing for performance
  useEffect(() => {
    // Ensure container width is up to date when data changes
    if (containerRef.current && containerWidth === 0) {
      const containerPadding = 32;
      const actualWidth = containerRef.current.clientWidth;
      const width = Math.max(actualWidth - containerPadding, 400);
      if (width > 0) {
        setContainerWidth(width);
      }
    }

    if (data.length === 0) {
      previousDataRef.current = [];
      setDisplayData([]);
      pendingDataRef.current = null;
      // Clear any pending updates
      if (updateTimeoutRef.current) {
        clearTimeout(updateTimeoutRef.current);
        updateTimeoutRef.current = null;
      }
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      return;
    }

    // Store pending data
    pendingDataRef.current = data;
    
    // Reduced logging - only log on first load or significant changes
    if (previousDataRef.current.length === 0 || 
        Math.abs(previousDataRef.current.length - data.length) > 100) {
    console.log('[TimeSeriesChart] Data update:', {
      dataLength: data.length,
      previousLength: previousDataRef.current.length,
    });
    }

    // Clear any pending timeout/RAF
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
    }

    // Check if it's a different dataset (new selection or time range change)
    const isDifferentDataset = 
      previousDataRef.current.length === 0 || // First load - always update
      previousDataRef.current.length !== data.length || // Different length
      (data.length > 0 && previousDataRef.current.length > 0 && (
        // Different first or last timestamp indicates different dataset
        previousDataRef.current[0]?.timestamp !== data[0]?.timestamp ||
        previousDataRef.current[previousDataRef.current.length - 1]?.timestamp !== data[data.length - 1]?.timestamp
      ));

    // For different dataset, update immediately (user changed selection)
    if (isDifferentDataset) {
      // Only log on first load
      if (previousDataRef.current.length === 0) {
        console.log('[TimeSeriesChart] Initial load, setting', data.length, 'points');
      }
      previousDataRef.current = data;
      // Set data immediately - don't wait for RAF
      // This is critical for first load
      setDisplayData(data);
      // Also schedule RAF update for smooth rendering (but data is already set)
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
      rafRef.current = requestAnimationFrame(() => {
        // Double-check data is set
        setDisplayData(data);
        rafRef.current = null;
      });
      return;
    }

    // For real-time updates with same dataset, use incremental updates for smooth Grafana-like experience
    if (realTime && !isDifferentDataset && previousDataRef.current.length > 0 && data.length > 0) {
      const lastOldTimestamp = new Date(previousDataRef.current[previousDataRef.current.length - 1].timestamp).getTime();
      const firstNewTimestamp = new Date(data[0].timestamp).getTime();
      
      // If new data starts after old data, append new points incrementally
      if (firstNewTimestamp > lastOldTimestamp) {
        const newPoints = data.filter(point => {
          const pointTime = new Date(point.timestamp).getTime();
          return pointTime > lastOldTimestamp;
        });

        if (newPoints.length > 0) {
          // Immediate incremental update for smooth real-time experience (Grafana-like)
          // Merge new points with existing data (sliding window approach)
          const merged = [...previousDataRef.current, ...newPoints];
          // Limit to last 2000 points for performance (sliding window - larger for smoother experience)
          const limited = merged.slice(-2000);
          
          // Update immediately without waiting for RAF for ultra-smooth real-time updates
          // This ensures new data appears instantly without delay
          previousDataRef.current = limited;
          setDisplayData(limited);
          pendingDataRef.current = null;
          
          // Clear any pending RAF to avoid conflicts
          if (rafRef.current !== null) {
            cancelAnimationFrame(rafRef.current);
            rafRef.current = null;
          }
          
          return;
        }
      }
      
      // If timestamps overlap, check for new points only (never replace all data)
      const firstOldTimestamp = new Date(previousDataRef.current[0].timestamp).getTime();
      const lastNewTimestamp = new Date(data[data.length - 1].timestamp).getTime();
      
      if (firstNewTimestamp <= lastOldTimestamp && lastNewTimestamp >= firstOldTimestamp) {
        // Find new points after the last known point
        const newPointsAfterLast = data.filter(point => {
          const pointTime = new Date(point.timestamp).getTime();
          return pointTime > lastOldTimestamp;
        });
        
        if (newPointsAfterLast.length > 0) {
          // Only append new points, never replace
          const merged = [...previousDataRef.current, ...newPointsAfterLast];
          const limited = merged.slice(-2000);
          
          previousDataRef.current = limited;
          setDisplayData(limited);
            pendingDataRef.current = null;
            
            if (rafRef.current !== null) {
              cancelAnimationFrame(rafRef.current);
              rafRef.current = null;
            }
          return;
        }
        
        // Check if last point value changed (update only that point)
        const prevLast = previousDataRef.current[previousDataRef.current.length - 1];
        const newLast = data[data.length - 1];
        
        if (prevLast && newLast && 
            prevLast.timestamp === newLast.timestamp &&
            Math.abs((prevLast.value || 0) - (newLast.value || 0)) > 0.001) {
          // Update only the last point
          const updated = [...previousDataRef.current];
          updated[updated.length - 1] = newLast;
          
          previousDataRef.current = updated;
          setDisplayData(updated);
              pendingDataRef.current = null;
          
          if (rafRef.current !== null) {
            cancelAnimationFrame(rafRef.current);
              rafRef.current = null;
          }
          return;
        }
        
        // No changes, skip update completely
        pendingDataRef.current = null;
        return;
      }
    }

    // Fallback: only for first load or completely different dataset
    // For real-time mode, we should never reach here if data merging works correctly
    if (previousDataRef.current.length === 0) {
      // First load - update immediately
      previousDataRef.current = data;
      setDisplayData(data);
      pendingDataRef.current = null;
      
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    } else {
      // Should not happen in real-time mode - try to merge anyway
      // Find any new points and append them
      const lastOldTimestamp = new Date(previousDataRef.current[previousDataRef.current.length - 1].timestamp).getTime();
      const newPoints = data.filter(point => {
        const pointTime = new Date(point.timestamp).getTime();
        return pointTime > lastOldTimestamp;
      });
      
      if (newPoints.length > 0) {
        const merged = [...previousDataRef.current, ...newPoints];
        const limited = merged.slice(-2000);
        previousDataRef.current = limited;
        setDisplayData(limited);
      pendingDataRef.current = null;
      
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
        }
      } else {
        // No new points, skip update
        pendingDataRef.current = null;
      }
    }

    // Cleanup
    return () => {
      if (updateTimeoutRef.current) {
        clearTimeout(updateTimeoutRef.current);
        updateTimeoutRef.current = null;
      }
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [data, realTime, containerWidth]);

  // Optimize data for rendering - limit data points for performance
  // If too many points, sample them intelligently to maintain visual quality
  const visibleData = useMemo(() => {
    if (displayData.length === 0) {
      return [];
    }
    
    if (displayData.length <= 2000) {
      return displayData; // Render all points if reasonable amount
    }
    
    // For large datasets, use intelligent sampling
    // Keep first, last, and sample middle points
    const maxPoints = 2000;
    const step = Math.ceil(displayData.length / maxPoints);
    const sampled: TimeSeriesDataPoint[] = [];
    
    // Always include first point
    sampled.push(displayData[0]);
    
    // Sample middle points
    for (let i = step; i < displayData.length - step; i += step) {
      sampled.push(displayData[i]);
    }
    
    // Always include last point
    if (displayData.length > 1) {
      sampled.push(displayData[displayData.length - 1]);
    }
    
    return sampled;
  }, [displayData]);

  // Calculate scales
  const { xScale, yScale, minValue, maxValue } = useMemo(() => {
    try {
      if (visibleData.length === 0) {
        console.warn('[TimeSeriesChart] No visible data for scales calculation');
        return { xScale: null, yScale: null, minValue: 0, maxValue: 0 };
      }

      // Check if inner dimensions are valid
      if (innerWidth <= 0 || innerHeight <= 0) {
        console.warn('[TimeSeriesChart] Invalid inner dimensions:', { innerWidth, innerHeight, containerWidth });
        return { xScale: null, yScale: null, minValue: 0, maxValue: 0 };
      }

      // X scale (time) - with validation
      const timestamps = visibleData
        .map(d => {
          try {
            if (!d || !d.timestamp) {
              console.warn('[TimeSeriesChart] Missing timestamp in data point:', d);
              return null;
            }
            const time = new Date(d.timestamp).getTime();
            if (isNaN(time)) {
              console.warn('[TimeSeriesChart] Invalid timestamp:', d.timestamp);
              return null;
            }
            return time;
          } catch (e) {
            console.warn('[TimeSeriesChart] Error parsing timestamp:', d.timestamp, e);
            return null;
          }
        })
        .filter((t): t is number => t !== null);
      
      if (timestamps.length === 0) {
        console.warn('[TimeSeriesChart] No valid timestamps found in visibleData:', visibleData);
        return { xScale: null, yScale: null, minValue: 0, maxValue: 0 };
      }

      const minTime = Math.min(...timestamps);
      const maxTime = Math.max(...timestamps);
      const timeRange = maxTime - minTime || 1;

      // Y scale (value) - with validation
      const values = visibleData
        .map(d => {
          const val = d.value;
          if (val === null || val === undefined || isNaN(val) || !isFinite(val)) {
            console.warn('[TimeSeriesChart] Invalid value:', val, d);
            return null;
          }
          return val;
        })
        .filter((v): v is number => v !== null);
      
      if (values.length === 0) {
        console.warn('[TimeSeriesChart] No valid values found');
        return { xScale: null, yScale: null, minValue: 0, maxValue: 0 };
      }

      const minVal = Math.min(...values);
      const maxVal = Math.max(...values);
      const valueRange = maxVal - minVal || 1;
      const yPadding = valueRange * 0.1; // 10% padding

      const xScale = (time: number) => {
        if (isNaN(time)) return 0;
        return ((time - minTime) / timeRange) * innerWidth;
      };

      const yScale = (value: number) => {
        if (isNaN(value) || !isFinite(value)) return 0;
        return innerHeight - ((value - minVal + yPadding) / (valueRange + yPadding * 2)) * innerHeight;
      };

      return {
        xScale,
        yScale,
        minValue: minVal - yPadding,
        maxValue: maxVal + yPadding,
      };
    } catch (error) {
      console.error('[TimeSeriesChart] Error calculating scales:', error);
      return { xScale: null, yScale: null, minValue: 0, maxValue: 0 };
    }
  }, [visibleData, innerWidth, innerHeight]);

  // Generate path for line
  const linePath = useMemo(() => {
    try {
      if (!visibleData.length || !xScale || !yScale) return '';

      const points = visibleData
        .map((point, index) => {
          try {
            const timestamp = new Date(point.timestamp).getTime();
            if (isNaN(timestamp)) {
              console.warn('[TimeSeriesChart] Invalid timestamp in point:', point);
              return null;
            }
            const value = point.value;
            if (value === null || value === undefined || isNaN(value) || !isFinite(value)) {
              console.warn('[TimeSeriesChart] Invalid value in point:', point);
              return null;
            }
            const x = xScale(timestamp);
            const y = yScale(value);
            if (isNaN(x) || isNaN(y) || !isFinite(x) || !isFinite(y)) {
              console.warn('[TimeSeriesChart] Invalid coordinates:', { x, y, point });
              return null;
            }
            return index === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
          } catch (e) {
            console.warn('[TimeSeriesChart] Error processing point:', e, point);
            return null;
          }
        })
        .filter((p): p is string => p !== null);

      return points.join(' ');
    } catch (error) {
      console.error('[TimeSeriesChart] Error generating line path:', error);
      return '';
    }
  }, [visibleData, xScale, yScale]);

  // Track if path actually changed to control transitions
  const pathChanged = useMemo(() => {
    if (!linePath) {
      if (previousPathRef.current) {
        previousPathRef.current = '';
        return false; // Path cleared, but don't animate
      }
      return false;
    }
    const changed = linePath !== previousPathRef.current;
    if (changed) {
      previousPathRef.current = linePath;
    }
    return changed;
  }, [linePath]);

  // Generate area path
  const areaPath = useMemo(() => {
    try {
      if (!linePath || !visibleData.length || !yScale || !xScale) return '';

      const firstPoint = visibleData[0];
      const lastPoint = visibleData[visibleData.length - 1];
      
      if (!firstPoint || !lastPoint) return '';

      const firstTimestamp = new Date(firstPoint.timestamp).getTime();
      const lastTimestamp = new Date(lastPoint.timestamp).getTime();
      
      if (isNaN(firstTimestamp) || isNaN(lastTimestamp)) {
        console.warn('[TimeSeriesChart] Invalid timestamps for area path');
        return '';
      }

      const firstX = xScale(firstTimestamp);
      const lastX = xScale(lastTimestamp);
      const zeroY = yScale(minValue);

      if (isNaN(firstX) || isNaN(lastX) || isNaN(zeroY) || !isFinite(firstX) || !isFinite(lastX) || !isFinite(zeroY)) {
        console.warn('[TimeSeriesChart] Invalid coordinates for area path');
        return '';
      }

      return `${linePath} L ${lastX} ${zeroY} L ${firstX} ${zeroY} Z`;
    } catch (error) {
      console.error('[TimeSeriesChart] Error generating area path:', error);
      return '';
    }
  }, [linePath, visibleData, xScale, yScale, minValue, innerWidth]);

  // Handle mouse move for hover
  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current || !xScale || !yScale || visibleData.length === 0) return;

    // Use SVG's getScreenCTM for accurate coordinate transformation
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    
    // Transform to SVG coordinate system
    const svgMatrix = svg.getScreenCTM();
    if (!svgMatrix) return;
    
    const svgPoint = pt.matrixTransform(svgMatrix.inverse());
    
    // Convert to inner chart coordinates (subtract padding)
    const x = svgPoint.x - padding.left;
    // y is used for distance calculation but not needed after that

    // Find closest point
    let closestPoint: TimeSeriesDataPoint | null = null;
    let minDistance = Infinity;

    visibleData.forEach((point) => {
      const pointX = xScale(new Date(point.timestamp).getTime());
      const distance = Math.abs(x - pointX);
      if (distance < minDistance && distance < 30) { // 30px threshold in SVG coordinates
        minDistance = distance;
        closestPoint = point;
      }
    });

    if (closestPoint) {
      const point = closestPoint as TimeSeriesDataPoint;
      setHoveredPoint(point);
      const pointX = xScale(new Date(point.timestamp).getTime());
      const pointY = yScale(point.value);
      
      // SVG coordinates (viewBox space) for drawing
      const svgX = pointX + padding.left;
      const svgY = pointY + padding.top;
      
      // Convert back to screen coordinates for tooltip
      const screenPt = svg.createSVGPoint();
      screenPt.x = svgX;
      screenPt.y = svgY;
      const screenPoint = screenPt.matrixTransform(svgMatrix);
      
      // Get container position for tooltip
      const containerRect = containerRef.current?.getBoundingClientRect();
      if (containerRect) {
        setHoverPosition({ 
          x: svgX,  // SVG viewBox coordinates for drawing
          y: svgY,  // SVG viewBox coordinates for drawing
          pixelX: screenPoint.x - containerRect.left,   // Pixel coordinates for tooltip
          pixelY: screenPoint.y - containerRect.top,   // Pixel coordinates for tooltip
        });
      } else {
        setHoverPosition({ 
          x: svgX,
          y: svgY,
        });
      }
      if (onHover) onHover(closestPoint);
    } else {
      setHoveredPoint(null);
      setHoverPosition(null);
      if (onHover) onHover(null);
    }
  }, [xScale, yScale, visibleData, padding, onHover]);

  // Handle mouse leave
  const handleMouseLeave = useCallback(() => {
    setHoveredPoint(null);
    setHoverPosition(null);
    if (onHover) onHover(null);
  }, [onHover]);


  // Format timestamp for display
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit',
    });
  };

  // Format date for display
  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  // Generate Y-axis ticks
  const yTicks = useMemo(() => {
    if (!yScale) return [];
    const ticks = [];
    const numTicks = 5;
    for (let i = 0; i <= numTicks; i++) {
      const value = minValue + (maxValue - minValue) * (i / numTicks);
      ticks.push({ value, y: yScale(value) });
    }
    return ticks;
  }, [yScale, minValue, maxValue]);

  // Generate X-axis ticks with smart spacing to avoid overlap
  const xTicks = useMemo(() => {
    if (!xScale || visibleData.length === 0) return [];
    
    // Calculate optimal number of ticks based on chart width
    const minLabelWidth = 80; // Minimum width for a label in pixels
    const maxTicks = Math.floor(innerWidth / minLabelWidth);
    const numTicks = Math.min(maxTicks, Math.max(3, Math.floor(visibleData.length / 10)));
    
    const ticks = [];
    const usedPositions: number[] = [];
    
    for (let i = 0; i <= numTicks; i++) {
      const idx = Math.floor((i / numTicks) * (visibleData.length - 1));
      const point = visibleData[idx];
      if (point) {
        const x = xScale(new Date(point.timestamp).getTime());
        
        // Check if this position is too close to existing labels
        const tooClose = usedPositions.some(pos => Math.abs(x - pos) < minLabelWidth);
        if (!tooClose) {
          ticks.push({ x, timestamp: point.timestamp });
          usedPositions.push(x);
        }
      }
    }
    
    // Always include first and last points
    if (visibleData.length > 0) {
      const firstX = xScale(new Date(visibleData[0].timestamp).getTime());
      const lastX = xScale(new Date(visibleData[visibleData.length - 1].timestamp).getTime());
      
      if (ticks.length === 0 || Math.abs(ticks[0].x - firstX) > 5) {
        ticks.unshift({ x: firstX, timestamp: visibleData[0].timestamp });
      }
      if (ticks.length === 0 || Math.abs(ticks[ticks.length - 1].x - lastX) > 5) {
        ticks.push({ x: lastX, timestamp: visibleData[visibleData.length - 1].timestamp });
      }
    }
    
    return ticks;
  }, [xScale, visibleData, innerWidth]);

  // Error boundary - if there's a render error, show error message
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

  // Validate scales before rendering
  if (!xScale || !yScale) {
    // Debug information
    console.warn('[TimeSeriesChart] Scales not available:', {
      hasData: data.length > 0,
      hasDisplayData: displayData.length > 0,
      hasVisibleData: visibleData.length > 0,
      containerWidth,
      innerWidth,
      innerHeight,
      dataSample: data.slice(0, 3),
      displayDataSample: displayData.slice(0, 3),
    });
    
    // If we have data but scales aren't ready, it might be a calculation issue
    if (data.length > 0 && containerWidth > 0) {
      // Try to render anyway with fallback scales
      console.warn('[TimeSeriesChart] Attempting to render with fallback scales');
    } else if (data.length === 0) {
      // This case is already handled above
      return null;
    }
    
    return (
      <div className="flex items-center justify-center h-full text-yellow-400 bg-gray-900/50 rounded-lg p-8">
        <div className="text-center">
          <p className="text-lg mb-2">Chart scales not ready</p>
          <p className="text-sm text-gray-500">Please wait...</p>
          <p className="text-xs text-gray-600 mt-2">
            Data: {data.length} points | Display: {displayData.length} | Visible: {visibleData.length} | Width: {containerWidth}px
          </p>
        </div>
      </div>
    );
  }

  // Ensure we have a valid width before rendering
  // But don't block rendering if we have data - use fallback width
  // The width calculation will update once container is measured

  try {
    return (
    <div ref={containerRef} className="relative w-full bg-gray-900/30 rounded-lg border border-gray-700/50 p-4">
      {/* Controls */}
      <div className="flex items-center justify-end mb-4">
        <div className="text-xs text-gray-500">
          {realTime && <span className="flex items-center gap-2"><span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>Live</span>}
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
            // Optimize for smooth rendering like Grafana
            willChange: realTime ? 'contents' : 'auto',
            // Prevent layout shifts
            minHeight: `${chartHeight}px`,
          }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
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

          {/* Grid lines */}
          {showGrid && yTicks.map((tick, i) => (
            <g key={`grid-y-${i}`}>
              <line
                x1={padding.left}
                y1={tick.y + padding.top}
                x2={chartWidth - padding.right}
                y2={tick.y + padding.top}
                stroke="#374151"
                strokeWidth="1"
                strokeDasharray="2,2"
                opacity="0.5"
              />
            </g>
          ))}
          {showGrid && xTicks.map((tick, i) => (
            <g key={`grid-x-${i}`}>
              <line
                x1={tick.x + padding.left}
                y1={padding.top}
                x2={tick.x + padding.left}
                y2={chartHeight - padding.bottom}
                stroke="#374151"
                strokeWidth="1"
                strokeDasharray="2,2"
                opacity="0.5"
              />
            </g>
          ))}

          {/* Area - smooth updates like Grafana */}
          {areaPath && (
            <g transform={`translate(${padding.left}, ${padding.top})`}>
              <path
                key={`area-${visibleData.length}-${visibleData[0]?.timestamp || ''}-${visibleData[visibleData.length - 1]?.timestamp || ''}`}
                d={areaPath}
                fill="url(#areaGradient)"
                style={{ 
                  opacity: 1,
                  // Use very fast transition for real-time updates (Grafana-like smoothness)
                  // Only apply transition if path actually changed
                  transition: (realTime && pathChanged) ? 'd 0.08s linear' : (pathChanged ? 'd 0.3s cubic-bezier(0.4, 0, 0.2, 1)' : 'none'),
                  willChange: (realTime && pathChanged) ? 'd' : 'auto',
                  // Ensure smooth rendering
                  shapeRendering: 'geometricPrecision',
                }}
              />
            </g>
          )}

          {/* Line - smooth updates like Grafana */}
          {linePath && (
            <g transform={`translate(${padding.left}, ${padding.top})`} key={`line-${visibleData.length}-${visibleData[0]?.timestamp}`}>
              <path
                d={linePath}
                fill="none"
                stroke={color}
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                filter="url(#glow)"
                style={{ 
                  opacity: 1,
                  // Use very fast transition for real-time updates (Grafana-like smoothness)
                  // Only apply transition if path actually changed
                  transition: (realTime && pathChanged) ? 'd 0.08s linear' : (pathChanged ? 'd 0.2s ease-out' : 'none'),
                  willChange: (realTime && pathChanged) ? 'd' : 'auto',
                  // Ensure smooth rendering
                  shapeRendering: 'geometricPrecision',
                }}
              />
            </g>
          )}

          {/* Data points - only render if reasonable amount for performance */}
          {visibleData.length <= 500 && visibleData.map((point, index) => {
            try {
              if (!xScale || !yScale) return null;
              
              const timestamp = new Date(point.timestamp).getTime();
              if (isNaN(timestamp)) {
                console.warn('[TimeSeriesChart] Invalid timestamp in data point:', point);
                return null;
              }
              
              const value = point.value;
              if (value === null || value === undefined || isNaN(value) || !isFinite(value)) {
                console.warn('[TimeSeriesChart] Invalid value in data point:', point);
                return null;
              }
              
              const x = xScale(timestamp);
              const y = yScale(value);
              
              if (isNaN(x) || isNaN(y) || !isFinite(x) || !isFinite(y)) {
                console.warn('[TimeSeriesChart] Invalid coordinates:', { x, y, point });
                return null;
              }
              
              const isHovered = hoveredPoint?.timestamp === point.timestamp;
              const translateX = x + padding.left;
              const translateY = y + padding.top;
              
              if (isNaN(translateX) || isNaN(translateY) || !isFinite(translateX) || !isFinite(translateY)) {
                console.warn('[TimeSeriesChart] Invalid transform coordinates:', { translateX, translateY });
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
                      filter: isHovered ? 'drop-shadow(0 0 4px rgba(59, 130, 246, 0.8))' : 'none',
                      opacity: 1
                    }}
                  />
                </g>
              );
            } catch (error) {
              console.error('[TimeSeriesChart] Error rendering data point:', error, point);
              return null;
            }
          })}

          {/* Y-axis labels */}
          <g>
            {yTicks.map((tick, i) => (
              <g key={`y-label-${i}`}>
                <text
                  x={padding.left - 10}
                  y={tick.y + padding.top + 4}
                  textAnchor="end"
                  className="text-xs fill-gray-400"
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
                  x={tick.x + padding.left}
                  y={chartHeight - padding.bottom + 15}
                  textAnchor="middle"
                  className="text-xs fill-gray-400"
                  style={{ dominantBaseline: 'hanging' }}
                >
                  {formatTime(tick.timestamp)}
                </text>
                <text
                  x={tick.x + padding.left}
                  y={chartHeight - padding.bottom + 28}
                  textAnchor="middle"
                  className="text-xs fill-gray-500"
                  style={{ dominantBaseline: 'hanging' }}
                >
                  {formatDate(tick.timestamp)}
                </text>
              </g>
            ))}
          </g>

          {/* Hover indicator line */}
          {hoveredPoint && hoverPosition && xScale !== null && yScale !== null && (
            <g>
              <line
                x1={hoverPosition.x}
                y1={padding.top}
                x2={hoverPosition.x}
                y2={chartHeight - padding.bottom}
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
          )}
        </svg>

        {/* Hover tooltip */}
        {hoveredPoint && hoverPosition && hoverPosition.pixelX !== undefined && hoverPosition.pixelY !== undefined && (
          <div
            className="absolute bg-gray-800 border border-gray-700 rounded-lg shadow-xl p-3 pointer-events-none z-10"
            style={{
              left: `${Math.min(hoverPosition.pixelX + 10, (containerRef.current?.clientWidth || chartWidth) - 200)}px`,
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

// Memoized version with custom comparison to prevent unnecessary re-renders
// For smooth Grafana-like updates, we allow more frequent updates in real-time mode
export const TimeSeriesChartMemo = memo(TimeSeriesChart, (prevProps, nextProps) => {
  // Both empty, no need to re-render
  if (prevProps.data.length === 0 && nextProps.data.length === 0) return true;
  
  // For real-time mode, check if data actually changed
  if (prevProps.realTime && nextProps.realTime) {
    // Check length first
    if (prevProps.data.length !== nextProps.data.length) {
      return false; // Length changed, need to re-render
    }
    
    // If both empty, skip re-render
    if (prevProps.data.length === 0 && nextProps.data.length === 0) {
      return true;
    }
    
    // Check if data actually changed by comparing key points
    if (prevProps.data.length > 0 && nextProps.data.length > 0) {
      // Check first point (time range change)
      const prevFirst = prevProps.data[0];
      const nextFirst = nextProps.data[0];
      if (prevFirst?.timestamp !== nextFirst?.timestamp) {
        return false; // First point changed, need to re-render
      }
      
      // Check last point (new data appended)
      const prevLast = prevProps.data[prevProps.data.length - 1];
      const nextLast = nextProps.data[nextProps.data.length - 1];
      if (prevLast?.timestamp !== nextLast?.timestamp || 
          Math.abs((prevLast?.value || 0) - (nextLast?.value || 0)) > 0.001) {
        return false; // Last point changed, need to re-render
      }
      
      // Check last 3 points for real-time updates (to catch recent changes)
      const checkPoints = Math.min(3, prevProps.data.length);
      for (let i = 0; i < checkPoints; i++) {
        const idx = prevProps.data.length - 1 - i;
        if (idx >= 0) {
          const prevPoint = prevProps.data[idx];
          const nextPoint = nextProps.data[idx];
          if (prevPoint?.timestamp !== nextPoint?.timestamp ||
              Math.abs((prevPoint?.value || 0) - (nextPoint?.value || 0)) > 0.001) {
            return false; // Data changed, need to re-render
          }
        }
      }
    }
    
    // Check other props
    if (prevProps.height !== nextProps.height ||
        prevProps.color !== nextProps.color ||
        prevProps.showGrid !== nextProps.showGrid) {
      return false; // Props changed, need to re-render
    }
    
    // Data appears unchanged, skip re-render to prevent unnecessary animations
    return true; // Skip re-render if data hasn't changed
  }
  
  // For non-real-time mode, use stricter comparison
  const lengthDiff = Math.abs(prevProps.data.length - nextProps.data.length);
  const maxLength = Math.max(prevProps.data.length, nextProps.data.length);
  if (maxLength > 0 && lengthDiff / maxLength > 0.1) {
    return false; // Significant length change, need to re-render
  }
  
  // If both have data, compare first and last points
  if (prevProps.data.length > 0 && nextProps.data.length > 0) {
    const prevFirst = prevProps.data[0];
    const nextFirst = nextProps.data[0];
    const prevLast = prevProps.data[prevProps.data.length - 1];
    const nextLast = nextProps.data[nextProps.data.length - 1];
    
    if (prevFirst?.timestamp !== nextFirst?.timestamp || 
        prevLast?.timestamp !== nextLast?.timestamp) {
      return false; // Data changed, need to re-render
    }
  }
  
  // Check other props
  if (prevProps.height !== nextProps.height ||
      prevProps.color !== nextProps.color ||
      prevProps.showGrid !== nextProps.showGrid ||
      prevProps.realTime !== nextProps.realTime) {
    return false; // Props changed, need to re-render
  }
  
  return true; // No changes, skip re-render
});

