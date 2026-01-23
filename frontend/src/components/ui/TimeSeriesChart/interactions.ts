/**
 * Time Series Chart Interactions
 * Handles mouse hover and interaction events
 */

import { TimeSeriesDataPoint, ScaleFunctions, HoverPosition } from './types';
import { parseTimestamp } from './utils';

/**
 * Find closest data point to mouse position
 */
export const findClosestPoint = (
  mouseX: number,
  visibleData: TimeSeriesDataPoint[],
  scales: ScaleFunctions,
  paddingLeft: number,
  threshold: number = 30
): TimeSeriesDataPoint | null => {
  let closestPoint: TimeSeriesDataPoint | null = null;
  let minDistance = Infinity;

  visibleData.forEach(point => {
    const timestamp = parseTimestamp(point.timestamp);
    if (timestamp === null) return;

    const pointX = scales.xScale(timestamp);
    const distance = Math.abs(mouseX - pointX);

    if (distance < minDistance && distance < threshold) {
      minDistance = distance;
      closestPoint = point;
    }
  });

  return closestPoint;
};

/**
 * Calculate hover position for tooltip
 */
export const calculateHoverPosition = (
  point: TimeSeriesDataPoint,
  scales: ScaleFunctions,
  padding: { top: number; left: number },
  svg: SVGSVGElement,
  containerRect: DOMRect | null
): HoverPosition => {
  const timestamp = parseTimestamp(point.timestamp);
  if (timestamp === null) {
    return { x: 0, y: 0 };
  }

  const pointX = scales.xScale(timestamp);
  const pointY = scales.yScale(point.value);

  // SVG coordinates (viewBox space) for drawing
  const svgX = pointX + padding.left;
  const svgY = pointY + padding.top;

  // Convert to screen coordinates for tooltip
  const svgMatrix = svg.getScreenCTM();
  if (svgMatrix && containerRect) {
    const screenPt = svg.createSVGPoint();
    screenPt.x = svgX;
    screenPt.y = svgY;
    const screenPoint = screenPt.matrixTransform(svgMatrix);

    return {
      x: svgX,
      y: svgY,
      pixelX: screenPoint.x - containerRect.left,
      pixelY: screenPoint.y - containerRect.top,
    };
  }

  return { x: svgX, y: svgY };
};

/**
 * Handle mouse move event
 */
export const handleMouseMove = (
  event: React.MouseEvent<SVGSVGElement>,
  svg: SVGSVGElement | null,
  visibleData: TimeSeriesDataPoint[],
  scales: ScaleFunctions | null,
  padding: { top: number; left: number },
  containerRect: DOMRect | null,
  onHover?: (point: TimeSeriesDataPoint | null) => void
): {
  hoveredPoint: TimeSeriesDataPoint | null;
  hoverPosition: HoverPosition | null;
} => {
  if (!svg || !scales || visibleData.length === 0) {
    return { hoveredPoint: null, hoverPosition: null };
  }

  // Transform mouse coordinates to SVG space
  const pt = svg.createSVGPoint();
  pt.x = event.clientX;
  pt.y = event.clientY;

  const svgMatrix = svg.getScreenCTM();
  if (!svgMatrix) {
    return { hoveredPoint: null, hoverPosition: null };
  }

  const svgPoint = pt.matrixTransform(svgMatrix.inverse());
  const mouseX = svgPoint.x - padding.left;

  // Find closest point
  const closestPoint = findClosestPoint(
    mouseX,
    visibleData,
    scales,
    padding.left
  );

  if (closestPoint) {
    const hoverPosition = calculateHoverPosition(
      closestPoint,
      scales,
      padding,
      svg,
      containerRect
    );

    if (onHover) {
      onHover(closestPoint);
    }

    return { hoveredPoint: closestPoint, hoverPosition };
  }

  if (onHover) {
    onHover(null);
  }

  return { hoveredPoint: null, hoverPosition: null };
};








