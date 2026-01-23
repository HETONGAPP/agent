/**
 * Time Series Chart Scales
 * Handles X and Y axis scaling calculations with smooth transitions
 */

import { TimeSeriesDataPoint, ScaleFunctions, YRange, ChartDimensions } from './types';
import { parseTimestamp, isValidDataPoint } from './utils';

export interface ScaleState {
  previousYRange: YRange | null;
  stableYRange: YRange | null;
  yRangeUpdateCounter: number;
  previousYTicks: Array<{ value: number; y: number }>;
  // Add time window state to prevent X-axis jumping
  stableTimeWindow: { minTime: number; maxTime: number } | null;
}

/**
 * Calculate X and Y scales with smooth transitions
 */
export const calculateScales = (
  visibleData: TimeSeriesDataPoint[],
  dimensions: ChartDimensions,
  realTime: boolean,
  state: ScaleState
): {
  scales: ScaleFunctions | null;
  updatedState: ScaleState;
} => {
  if (visibleData.length === 0) {
    return {
      scales: null,
      updatedState: state,
    };
  }

  // Validate dimensions
  if (dimensions.innerWidth <= 0 || dimensions.innerHeight <= 0) {
    return {
      scales: null,
      updatedState: state,
    };
  }

  // Extract and validate timestamps
  const timestamps = visibleData
    .map(d => parseTimestamp(d.timestamp))
    .filter((t): t is number => t !== null);

  if (timestamps.length === 0) {
    return {
      scales: null,
      updatedState: state,
    };
  }

  // In real-time mode, use fixed-width sliding time window for smooth panning
  let minTime: number;
  let maxTime: number;
  
  if (realTime && state.stableTimeWindow) {
    const currentMinTime = Math.min(...timestamps);
    const currentMaxTime = Math.max(...timestamps);
    const stableTimeRange = state.stableTimeWindow.maxTime - state.stableTimeWindow.minTime;
    
    // Use fixed time window width for smooth panning
    // Window slides forward gradually as new data arrives, maintaining constant width
    if (currentMaxTime > state.stableTimeWindow.maxTime) {
      // New data extends beyond current window - slide window forward gradually
      // Use smooth interpolation to prevent jumping
      const timeShift = currentMaxTime - state.stableTimeWindow.maxTime;
      // Smooth sliding: move 30% towards new position each update
      const smoothingFactor = 0.3;
      const targetMinTime = state.stableTimeWindow.minTime + timeShift;
      const targetMaxTime = state.stableTimeWindow.maxTime + timeShift;
      
      minTime = state.stableTimeWindow.minTime + (targetMinTime - state.stableTimeWindow.minTime) * smoothingFactor;
      maxTime = state.stableTimeWindow.maxTime + (targetMaxTime - state.stableTimeWindow.maxTime) * smoothingFactor;
      
      // Ensure we don't go before the actual data
      if (minTime < currentMinTime) {
        minTime = currentMinTime;
        maxTime = minTime + stableTimeRange;
      }
      
      // Ensure window width is maintained
      const actualRange = maxTime - minTime;
      if (Math.abs(actualRange - stableTimeRange) > stableTimeRange * 0.1) {
        // Adjust to maintain width
        maxTime = minTime + stableTimeRange;
      }
    } else {
      // No new data beyond window - keep current window (no sliding)
      minTime = state.stableTimeWindow.minTime;
      maxTime = state.stableTimeWindow.maxTime;
    }
    
    // Update stable time window (preserve width, update position)
    updatedState.stableTimeWindow = { minTime, maxTime };
  } else {
    // First time or non-real-time: use actual data range
    minTime = Math.min(...timestamps);
    maxTime = Math.max(...timestamps);
    
    // Set initial stable time window
    if (realTime) {
      updatedState.stableTimeWindow = { minTime, maxTime };
    }
  }
  
  const timeRange = maxTime - minTime || 1;

  // Extract and validate values
  const values = visibleData
    .filter(isValidDataPoint)
    .map(d => d.value)
    .filter(v => isFinite(v));

  if (values.length === 0) {
    return {
      scales: null,
      updatedState: state,
    };
  }

  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const valueRange = maxVal - minVal || 1;
  const yPadding = valueRange * 0.05; // 5% padding

  // Calculate ideal range
  let idealMin = minVal - yPadding;
  let idealMax = maxVal + yPadding;
  
  // In real-time mode, ensure we never shrink the range
  // Use the maximum of current ideal range and stable range
  if (realTime && state.stableYRange) {
    const stableMin = state.stableYRange.min;
    const stableMax = state.stableYRange.max;
    // Only expand, never shrink - use the maximum range
    idealMin = Math.min(idealMin, stableMin);
    idealMax = Math.max(idealMax, stableMax);
  }

  // Apply smooth transitions based on mode
  let finalMin = idealMin;
  let finalMax = idealMax;
  const updatedState = { ...state };

  if (realTime) {
    // Real-time mode: use stable Y-axis range to prevent jumping
    if (state.stableYRange) {
      const stableMin = state.stableYRange.min;
      const stableMax = state.stableYRange.max;
      const stableRange = stableMax - stableMin;

      // Use larger margin (20%) to prevent temporary shrinking
      const margin = stableRange * 0.2; // 20% margin
      const withinRange =
        idealMin >= stableMin - margin && idealMax <= stableMax + margin;

      // Always use the maximum range to prevent shrinking
      // Compare with ideal range (which already accounts for stable range)
      const needsExpand = idealMax > stableMax + margin || idealMin < stableMin - margin;
      
      if (!needsExpand) {
        // Data is within range, keep stable range (no shrinking)
        finalMin = stableMin;
        finalMax = stableMax;
        updatedState.yRangeUpdateCounter = 0;
      } else {
        // Data is outside range - expand immediately to prevent shrinking
        // Use immediate expansion for smoother UX
        const expansionMargin = stableRange * 0.1; // 10% expansion margin
        finalMin = Math.min(idealMin, stableMin - expansionMargin);
        finalMax = Math.max(idealMax, stableMax + expansionMargin);
        
        // Update stable range immediately to prevent shrinking on next update
        updatedState.stableYRange = { min: finalMin, max: finalMax };
        updatedState.yRangeUpdateCounter = 0;
      }
    } else {
      // First time, set stable range
      updatedState.stableYRange = { min: idealMin, max: idealMax };
      finalMin = idealMin;
      finalMax = idealMax;
    }
  } else {
    // Non-real-time mode: use smooth transitions
    if (state.previousYRange) {
      const prevMin = state.previousYRange.min;
      const prevMax = state.previousYRange.max;
      const prevRange = prevMax - prevMin;
      const newRange = idealMax - idealMin;

      if (prevRange > 0 && Math.abs(newRange - prevRange) / prevRange > 0.1) {
        const smoothingFactor = 0.3; // 30% towards new range
        finalMin = prevMin + (idealMin - prevMin) * smoothingFactor;
        finalMax = prevMax + (idealMax - prevMax) * smoothingFactor;
      }
    }
    updatedState.previousYRange = { min: finalMin, max: finalMax };
  }

  const adjustedValueRange = finalMax - finalMin || 1;

  const xScale = (time: number): number => {
    if (isNaN(time)) return 0;
    return ((time - minTime) / timeRange) * dimensions.innerWidth;
  };

  const yScale = (value: number): number => {
    if (isNaN(value) || !isFinite(value)) return 0;
    return (
      dimensions.innerHeight -
      ((value - finalMin) / adjustedValueRange) * dimensions.innerHeight
    );
  };

  return {
    scales: {
      xScale,
      yScale,
      minValue: finalMin,
      maxValue: finalMax,
    },
    updatedState,
  };
};

/**
 * Generate Y-axis ticks
 */
export const generateYTicks = (
  yScale: (value: number) => number,
  minValue: number,
  maxValue: number,
  numTicks: number = 5
): Array<{ value: number; y: number }> => {
  const ticks = [];
  for (let i = 0; i <= numTicks; i++) {
    const value = minValue + (maxValue - minValue) * (i / numTicks);
    ticks.push({ value, y: yScale(value) });
  }
  return ticks;
};

/**
 * Generate smooth Y-axis ticks for real-time mode
 */
export const generateStableYTicks = (
  yTicks: Array<{ value: number; y: number }>,
  previousYTicks: Array<{ value: number; y: number }>,
  realTime: boolean
): {
  ticks: Array<{ value: number; y: number }>;
  updatedPrevious: Array<{ value: number; y: number }>;
} => {
  if (realTime && previousYTicks.length > 0 && yTicks.length > 0) {
    // Interpolate between previous and new tick positions
    const smoothed = yTicks.map((tick, i) => {
      const prevTick = previousYTicks[i];
      if (prevTick) {
        const smoothingFactor = 0.2; // 20% towards new position
        return {
          value: tick.value,
          y: prevTick.y + (tick.y - prevTick.y) * smoothingFactor,
        };
      }
      return tick;
    });
    return { ticks: smoothed, updatedPrevious: yTicks };
  }
  return { ticks: yTicks, updatedPrevious: yTicks };
};

/**
 * Generate X-axis ticks with smart spacing
 */
export const generateXTicks = (
  visibleData: TimeSeriesDataPoint[],
  xScale: (time: number) => number,
  innerWidth: number
): Array<{ x: number; timestamp: string }> => {
  if (visibleData.length === 0) return [];

  const minLabelWidth = 80;
  const maxTicks = Math.floor(innerWidth / minLabelWidth);
  const numTicks = Math.min(
    maxTicks,
    Math.max(3, Math.floor(visibleData.length / 10))
  );

  const ticks: Array<{ x: number; timestamp: string }> = [];
  const usedPositions: number[] = [];

  for (let i = 0; i <= numTicks; i++) {
    const idx = Math.floor((i / numTicks) * (visibleData.length - 1));
    const point = visibleData[idx];
    if (point) {
      const timestamp = parseTimestamp(point.timestamp);
      if (timestamp !== null) {
        const x = xScale(timestamp);
        const tooClose = usedPositions.some(
          pos => Math.abs(x - pos) < minLabelWidth
        );
        if (!tooClose) {
          ticks.push({ x, timestamp: point.timestamp });
          usedPositions.push(x);
        }
      }
    }
  }

  // Always include first and last points
  if (visibleData.length > 0) {
    const firstTimestamp = parseTimestamp(visibleData[0].timestamp);
    const lastTimestamp = parseTimestamp(
      visibleData[visibleData.length - 1].timestamp
    );

    if (firstTimestamp !== null && lastTimestamp !== null) {
      const firstX = xScale(firstTimestamp);
      const lastX = xScale(lastTimestamp);

      if (ticks.length === 0 || Math.abs(ticks[0].x - firstX) > 5) {
        ticks.unshift({ x: firstX, timestamp: visibleData[0].timestamp });
      }
      if (
        ticks.length === 0 ||
        Math.abs(ticks[ticks.length - 1].x - lastX) > 5
      ) {
        ticks.push({
          x: lastX,
          timestamp: visibleData[visibleData.length - 1].timestamp,
        });
      }
    }
  }

  return ticks;
};

