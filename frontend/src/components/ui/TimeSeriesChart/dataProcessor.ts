/**
 * Time Series Chart Data Processor
 * Handles smooth data merging and updates for real-time mode
 */

import { TimeSeriesDataPoint, YRange } from './types';
import { parseTimestamp } from './utils';

export interface DataProcessorState {
  previousData: TimeSeriesDataPoint[];
  stableYRange: YRange | null;
  yRangeUpdateCounter: number;
}

/**
 * Check if two datasets are different (user changed selection/time range)
 * In real-time mode, we're more lenient - only treat as different if:
 * - First timestamp changed significantly (time range shifted backward)
 * - Data is completely different (not just extended)
 */
export const isDifferentDataset = (
  prevData: TimeSeriesDataPoint[],
  newData: TimeSeriesDataPoint[],
  realTime: boolean = false
): boolean => {
  if (prevData.length === 0) return true;
  if (newData.length === 0) return false; // Keep previous data if new is empty
  
  if (prevData.length > 0 && newData.length > 0) {
    const prevFirst = prevData[0];
    const newFirst = newData[0];
    const prevLast = prevData[prevData.length - 1];
    const newLast = newData[newData.length - 1];
    
    const prevFirstTime = parseTimestamp(prevFirst?.timestamp || '');
    const newFirstTime = parseTimestamp(newFirst?.timestamp || '');
    const prevLastTime = parseTimestamp(prevLast?.timestamp || '');
    const newLastTime = parseTimestamp(newLast?.timestamp || '');
    
    if (!prevFirstTime || !newFirstTime || !prevLastTime || !newLastTime) {
      return true; // Invalid data, treat as different
    }
    
    // In real-time mode, be very lenient
    if (realTime) {
      // Only treat as different if:
      // 1. First timestamp moved backward significantly (more than 5 minutes)
      //    This indicates time range was changed by user
      if (newFirstTime < prevFirstTime - 300000) { // 5 minutes in ms
        return true;
      }
      
      // 2. If new data is just an extension of previous data, it's the same dataset
      // Check if new data starts before or at previous last point
      if (newFirstTime <= prevLastTime) {
        // Same dataset, just extended - not different
        return false;
      }
      
      // 3. If new data starts after previous data, it's continuation - not different
      if (newFirstTime > prevLastTime) {
        return false;
      }
      
      // 4. If data length changed dramatically (more than 100% increase), might be different
      const lengthDiff = newData.length - prevData.length;
      if (lengthDiff > prevData.length) {
        // More than doubled - might be different dataset
        return true;
      }
      
      // Otherwise, treat as same dataset (just updated)
      return false;
    }
    
    // Non-real-time mode: strict comparison
    if (prevData.length !== newData.length) return true;
    if (prevFirst?.timestamp !== newFirst?.timestamp) return true;
    if (prevLast?.timestamp !== newLast?.timestamp) return true;
    
    return false;
  }
  
  return false;
};

/**
 * Merge new data points with existing data (sliding window approach)
 * Returns merged data and whether Y-axis range should update faster
 */
export const mergeDataPoints = (
  previousData: TimeSeriesDataPoint[],
  newData: TimeSeriesDataPoint[],
  maxPoints: number = 2000
): {
  merged: TimeSeriesDataPoint[];
  shouldUpdateYRange: boolean;
} => {
  if (previousData.length === 0) {
    return { merged: newData.slice(-maxPoints), shouldUpdateYRange: false };
  }

  const lastOldTimestamp = parseTimestamp(
    previousData[previousData.length - 1].timestamp
  );
  const firstNewTimestamp = parseTimestamp(newData[0].timestamp);

  if (!lastOldTimestamp || !firstNewTimestamp) {
    return { merged: newData.slice(-maxPoints), shouldUpdateYRange: false };
  }

  // If new data starts after old data, append new points
  if (firstNewTimestamp > lastOldTimestamp) {
    const newPoints = newData.filter(point => {
      const pointTime = parseTimestamp(point.timestamp);
      return pointTime !== null && pointTime > lastOldTimestamp;
    });

    if (newPoints.length > 0) {
      // Merge and maintain sliding window
      // Keep all previous data and append new points, then slice to maxPoints
      // This ensures smooth sliding window without jumping
      const merged = [...previousData, ...newPoints];
      
      // Only slice if we exceed maxPoints - this maintains continuity
      const limited = merged.length > maxPoints 
        ? merged.slice(-maxPoints) 
        : merged;
      
      // Check if new data significantly changes value range
      const shouldUpdateYRange = checkYRangeChange(previousData, newPoints);
      
      return { merged: limited, shouldUpdateYRange };
    }
  }
  
  // If new data overlaps with old data (common case when backend returns full range)
  // Find the overlap point and merge intelligently
  if (firstNewTimestamp <= lastOldTimestamp) {
    // New data overlaps - find where it starts overlapping
    // Find the last point in previousData that matches or is before firstNewTimestamp
    let overlapStartIndex = previousData.length - 1;
    for (let i = previousData.length - 1; i >= 0; i--) {
      const pointTime = parseTimestamp(previousData[i].timestamp);
      if (pointTime !== null && pointTime <= firstNewTimestamp) {
        overlapStartIndex = i;
        break;
      }
    }
    
    // Find new points after the last old point
    const newPoints = newData.filter(point => {
      const pointTime = parseTimestamp(point.timestamp);
      return pointTime !== null && pointTime > lastOldTimestamp;
    });

    if (newPoints.length > 0) {
      // Merge: keep data up to overlap point, then add new points
      const beforeOverlap = previousData.slice(0, overlapStartIndex + 1);
      const merged = [...beforeOverlap, ...newPoints];
      const limited = merged.length > maxPoints 
        ? merged.slice(-maxPoints) 
        : merged;
      return { merged: limited, shouldUpdateYRange: false };
    }
    
    // No new points, but data might have been updated (same timestamps, different values)
    // Check if last point value changed
    const prevLast = previousData[previousData.length - 1];
    const newLast = newData[newData.length - 1];
    
    if (prevLast && newLast && 
        prevLast.timestamp === newLast.timestamp &&
        Math.abs((prevLast.value || 0) - (newLast.value || 0)) > 0.001) {
      // Only last point changed - update just that point
      const updated = [...previousData];
      updated[updated.length - 1] = newLast;
      return { merged: updated, shouldUpdateYRange: false };
    }
    
    // Data overlaps but no new points and no value changes
    // Keep previous data to avoid unnecessary updates
    return { merged: previousData, shouldUpdateYRange: false };
  }

  // Fallback: find any new points
  const fallbackNewPoints = newData.filter(point => {
    const pointTime = parseTimestamp(point.timestamp);
    return pointTime !== null && pointTime > lastOldTimestamp;
  });

  if (fallbackNewPoints.length > 0) {
    const merged = [...previousData, ...fallbackNewPoints];
    const limited = merged.length > maxPoints 
      ? merged.slice(-maxPoints) 
      : merged;
    return { merged: limited, shouldUpdateYRange: false };
  }

  // No changes - keep previous data to avoid unnecessary updates
  return { merged: previousData, shouldUpdateYRange: false };
};

/**
 * Check if new data points significantly change the Y-axis range
 */
const checkYRangeChange = (
  previousData: TimeSeriesDataPoint[],
  newPoints: TimeSeriesDataPoint[]
): boolean => {
  if (newPoints.length === 0) return false;

  const newValues = newPoints
    .map(p => p.value)
    .filter(v => v !== null && v !== undefined && isFinite(v));

  if (newValues.length === 0) return false;

  const prevValues = previousData
    .map(p => p.value)
    .filter(v => v !== null && v !== undefined && isFinite(v));

  if (prevValues.length === 0) return true;

  const prevMin = Math.min(...prevValues);
  const prevMax = Math.max(...prevValues);
  const prevRange = prevMax - prevMin;

  if (prevRange === 0) return true;

  const newMin = Math.min(...newValues);
  const newMax = Math.max(...newValues);
  const margin = prevRange * 0.15; // 15% margin

  return newMin < (prevMin - margin) || newMax > (prevMax + margin);
};

/**
 * Process data update for real-time mode
 * Returns processed data and updated state
 */
export const processRealTimeUpdate = (
  previousData: TimeSeriesDataPoint[],
  newData: TimeSeriesDataPoint[],
  state: DataProcessorState
): {
  displayData: TimeSeriesDataPoint[];
  updatedState: DataProcessorState;
} => {
  // Check if it's a different dataset (user changed selection)
  // In real-time mode, be more lenient
  if (isDifferentDataset(previousData, newData, true)) {
    return {
      displayData: newData,
      updatedState: {
        ...state,
        previousData: newData,
      },
    };
  }

  // Merge new data with existing data
  const { merged, shouldUpdateYRange } = mergeDataPoints(previousData, newData);

  const updatedState: DataProcessorState = {
    ...state,
    previousData: merged,
  };

  // Update Y-range counter if needed
  if (shouldUpdateYRange && state.stableYRange) {
    updatedState.yRangeUpdateCounter = 8; // Allow faster update
  }

  return {
    displayData: merged,
    updatedState,
  };
};

