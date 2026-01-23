/**
 * Time Series Chart Path Generation
 * Generates SVG paths for line and area charts
 */

import { TimeSeriesDataPoint, ScaleFunctions } from './types';
import { parseTimestamp, isValidDataPoint } from './utils';

/**
 * Generate SVG path for line chart
 */
export const generateLinePath = (
  visibleData: TimeSeriesDataPoint[],
  scales: ScaleFunctions
): string => {
  if (visibleData.length === 0) return '';

  const points = visibleData
    .map((point, index) => {
      if (!isValidDataPoint(point)) return null;

      const timestamp = parseTimestamp(point.timestamp);
      if (timestamp === null) return null;

      const x = scales.xScale(timestamp);
      const y = scales.yScale(point.value);

      if (isNaN(x) || isNaN(y) || !isFinite(x) || !isFinite(y)) {
        return null;
      }

      return index === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
    })
    .filter((p): p is string => p !== null);

  return points.join(' ');
};

/**
 * Generate SVG path for area chart
 */
export const generateAreaPath = (
  linePath: string,
  visibleData: TimeSeriesDataPoint[],
  scales: ScaleFunctions
): string => {
  if (!linePath || visibleData.length === 0) return '';

  const firstPoint = visibleData[0];
  const lastPoint = visibleData[visibleData.length - 1];

  if (!firstPoint || !lastPoint) return '';

  const firstTimestamp = parseTimestamp(firstPoint.timestamp);
  const lastTimestamp = parseTimestamp(lastPoint.timestamp);

  if (firstTimestamp === null || lastTimestamp === null) return '';

  const firstX = scales.xScale(firstTimestamp);
  const lastX = scales.xScale(lastTimestamp);
  const zeroY = scales.yScale(scales.minValue);

  if (
    isNaN(firstX) ||
    isNaN(lastX) ||
    isNaN(zeroY) ||
    !isFinite(firstX) ||
    !isFinite(lastX) ||
    !isFinite(zeroY)
  ) {
    return '';
  }

  return `${linePath} L ${lastX} ${zeroY} L ${firstX} ${zeroY} Z`;
};

/**
 * Check if path has changed (for transition control)
 */
export const hasPathChanged = (
  newPath: string,
  previousPath: string
): boolean => {
  return newPath !== previousPath;
};








