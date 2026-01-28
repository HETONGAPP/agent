/**
 * Custom hooks for TimeSeriesChart
 * Extracted from TimeSeriesChart.tsx to reduce file size and improve maintainability
 */

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { TimeSeriesDataPoint, ChartDimensions, ScaleFunctions } from './types';
import { sampleData, parseTimestamp } from './utils';
import { processRealTimeUpdate, DataProcessorState } from './dataProcessor';
import { calculateScales, generateYTicks, generateStableYTicks, generateXTicks, ScaleState } from './scales';
import { generateLinePath, generateAreaPath, hasPathChanged } from './paths';
import { handleMouseMove } from './interactions';

/**
 * Hook for managing chart container dimensions and responsive width
 */
export function useChartDimensions(
  containerRef: React.RefObject<HTMLDivElement>,
  height: number
): { containerWidth: number; dimensions: ChartDimensions } {
  const [containerWidth, setContainerWidth] = useState(0);
  const padding = { top: 20, right: 40, bottom: 60, left: 60 };
  const chartHeight = height;
  const chartWidth = containerWidth > 0 ? containerWidth : 800;
  const innerWidth = Math.max(0, chartWidth - padding.left - padding.right);
  const innerHeight = Math.max(0, chartHeight - padding.top - padding.bottom);

  const dimensions: ChartDimensions = useMemo(
    () => ({
      width: chartWidth,
      height: chartHeight,
      padding,
      innerWidth,
      innerHeight,
    }),
    [chartWidth, chartHeight, innerWidth, innerHeight]
  );

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
  }, [containerRef]);

  // Ensure container width is up to date on mount
  useEffect(() => {
    if (containerRef.current && containerWidth === 0) {
      const containerPadding = 32;
      const actualWidth = containerRef.current.clientWidth;
      const width = Math.max(actualWidth - containerPadding, 400);
      if (width > 0) {
        setContainerWidth(width);
      }
    }
  }, [containerRef, containerWidth]);

  return { containerWidth, dimensions };
}

/**
 * Hook for creating the DOM update function
 */
export function useChartDOMUpdate(
  displayDataRef: React.MutableRefObject<TimeSeriesDataPoint[]>,
  visibleDataRef: React.MutableRefObject<TimeSeriesDataPoint[]>,
  scaleStateRef: React.MutableRefObject<ScaleState>,
  scalesRef: React.MutableRefObject<ScaleFunctions | null>,
  linePathRef: React.RefObject<SVGPathElement>,
  areaPathRef: React.RefObject<SVGPathElement>,
  previousPathRef: React.MutableRefObject<string>,
  realTime: boolean,
  containerWidth: number,
  chartHeight: number,
  padding: { top: number; right: number; bottom: number; left: number }
): () => void {
  return useCallback(() => {
    if (displayDataRef.current.length === 0) {
      return;
    }

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

    let visibleData: TimeSeriesDataPoint[];
    const maxPoints = realTime ? 1500 : 2000;

    if (realTime && visibleDataRef.current.length > 0 && displayDataRef.current.length > 0) {
      const prevLastTime = parseTimestamp(
        visibleDataRef.current[visibleDataRef.current.length - 1]?.timestamp || ''
      );
      const newFirstTime = parseTimestamp(displayDataRef.current[0]?.timestamp || '');
      const newLastTime = parseTimestamp(
        displayDataRef.current[displayDataRef.current.length - 1]?.timestamp || ''
      );

      if (
        prevLastTime &&
        newFirstTime &&
        newLastTime &&
        newFirstTime >= prevLastTime - 60000
      ) {
        visibleData = sampleData(displayDataRef.current, maxPoints);
      } else if (
        prevLastTime &&
        newFirstTime &&
        newLastTime &&
        newFirstTime < prevLastTime &&
        newLastTime > prevLastTime
      ) {
        visibleData = sampleData(displayDataRef.current, maxPoints);
      } else {
        visibleData = sampleData(displayDataRef.current, maxPoints);
      }
    } else {
      visibleData = sampleData(displayDataRef.current, maxPoints);
    }

    visibleDataRef.current = visibleData;

    const scaleResult = calculateScales(visibleData, currentDimensions, realTime, scaleStateRef.current);

    if (scaleResult.updatedState) {
      scaleStateRef.current = scaleResult.updatedState;
    }

    if (!scaleResult.scales) {
      return;
    }

    scalesRef.current = scaleResult.scales;

    const linePath = generateLinePath(visibleData, scaleResult.scales);
    const areaPath = generateAreaPath(linePath, visibleData, scaleResult.scales);

    if (linePathRef.current && linePath) {
      if (realTime && previousPathRef.current && previousPathRef.current !== linePath) {
        linePathRef.current.style.transition = 'd 0.15s linear';
        linePathRef.current.setAttribute('d', linePath);
      } else {
        linePathRef.current.style.transition = 'none';
        linePathRef.current.setAttribute('d', linePath);
      }
      previousPathRef.current = linePath;
    }

    if (areaPathRef.current && areaPath) {
      if (realTime && previousPathRef.current) {
        areaPathRef.current.style.transition = 'd 0.15s linear';
        areaPathRef.current.setAttribute('d', areaPath);
      } else {
        areaPathRef.current.style.transition = 'none';
        areaPathRef.current.setAttribute('d', areaPath);
      }
    }
  }, [
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
    padding,
  ]);
}

/**
 * Hook for processing data updates and managing real-time data flow.
 * Accepts optional refs so the same refs can be shared with useChartDOMUpdate (single source of truth).
 */
export function useDataProcessing(
  data: TimeSeriesDataPoint[],
  realTime: boolean,
  containerWidth: number,
  updateChartDOM: () => void,
  refs?: {
    displayDataRef: React.MutableRefObject<TimeSeriesDataPoint[]>;
    visibleDataRef: React.MutableRefObject<TimeSeriesDataPoint[]>;
    onDisplayDataUpdate?: () => void;
  }
): {
  displayDataRef: React.MutableRefObject<TimeSeriesDataPoint[]>;
  visibleDataRef: React.MutableRefObject<TimeSeriesDataPoint[]>;
  dataProcessorStateRef: React.MutableRefObject<DataProcessorState>;
  forceUpdate: React.Dispatch<React.SetStateAction<number>>;
} {
  const internalDisplayRef = useRef<TimeSeriesDataPoint[]>([]);
  const internalVisibleRef = useRef<TimeSeriesDataPoint[]>([]);
  const displayDataRef = refs?.displayDataRef ?? internalDisplayRef;
  const visibleDataRef = refs?.visibleDataRef ?? internalVisibleRef;
  const onDisplayDataUpdateRef = useRef(refs?.onDisplayDataUpdate);
  onDisplayDataUpdateRef.current = refs?.onDisplayDataUpdate;
  const dataProcessorStateRef = useRef<DataProcessorState>({
    previousData: [],
    stableYRange: null,
    yRangeUpdateCounter: 0,
  });
  const rafRef = useRef<number | null>(null);
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    if (data.length === 0) {
      dataProcessorStateRef.current = {
        previousData: [],
        stableYRange: null,
        yRangeUpdateCounter: 0,
      };
      displayDataRef.current = [];
      visibleDataRef.current = [];
      if (displayDataRef.current.length > 0) {
        forceUpdate((prev) => prev + 1);
      }
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      return;
    }

    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
    }

    rafRef.current = requestAnimationFrame(() => {
      const state = dataProcessorStateRef.current;
      let processedData: TimeSeriesDataPoint[];
      let needsFullRender = false;

      if (realTime) {
        const result = processRealTimeUpdate(state.previousData, data, state);
        processedData = result.displayData;
        dataProcessorStateRef.current = result.updatedState;
        needsFullRender = false;
      } else {
        const isDifferent =
          state.previousData.length === 0 ||
          state.previousData.length !== data.length ||
          (data.length > 0 &&
            state.previousData.length > 0 &&
            (state.previousData[0]?.timestamp !== data[0]?.timestamp ||
              state.previousData[state.previousData.length - 1]?.timestamp !==
                data[data.length - 1]?.timestamp));

        if (isDifferent) {
          processedData = data;
          dataProcessorStateRef.current = {
            ...state,
            previousData: data,
          };
          needsFullRender = true;
        } else {
          processedData = state.previousData;
          needsFullRender = false;
        }
      }

      displayDataRef.current = processedData;
      onDisplayDataUpdateRef.current?.();

      if (needsFullRender) {
        forceUpdate((prev) => prev + 1);
      } else {
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
  }, [data, realTime, containerWidth, updateChartDOM]);

  return {
    displayDataRef,
    visibleDataRef,
    dataProcessorStateRef,
    forceUpdate,
  };
}

/**
 * Hook for calculating and managing chart scales
 */
export function useChartScales(
  displayDataRef: React.MutableRefObject<TimeSeriesDataPoint[]>,
  visibleDataRef: React.MutableRefObject<TimeSeriesDataPoint[]>,
  dimensions: ChartDimensions,
  realTime: boolean,
  containerWidth: number,
  innerWidth: number,
  displayDataVersion: number = 0
): {
  scales: ScaleFunctions | null;
  scalesRef: React.MutableRefObject<ScaleFunctions | null>;
  scaleStateRef: React.MutableRefObject<ScaleState>;
  yTicks: Array<{ value: number; y: number }>;
  stableYTicks: Array<{ value: number; y: number }>;
  xTicks: Array<{ timestamp: string; x: number }>;
} {
  const scalesRef = useRef<ScaleFunctions | null>(null);
  const scaleStateRef = useRef<ScaleState>({
    previousYRange: null,
    stableYRange: null,
    yRangeUpdateCounter: 0,
    previousYTicks: [],
    stableTimeWindow: null,
  });

  const { scales } = useMemo(() => {
    const visibleData =
      visibleDataRef.current.length > 0
        ? visibleDataRef.current
        : displayDataRef.current.length > 0
          ? sampleData(displayDataRef.current, realTime ? 1500 : 2000)
          : [];

    if (visibleData.length === 0) {
      return { scales: scalesRef.current };
    }

    const result = calculateScales(visibleData, dimensions, realTime, scaleStateRef.current);

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
  }, [dimensions, realTime, containerWidth, displayDataRef, visibleDataRef, displayDataVersion]);

  const yTicks = useMemo(() => {
    const currentScales = scales || scalesRef.current;
    if (!currentScales) return [];
    return generateYTicks(currentScales.yScale, currentScales.minValue, currentScales.maxValue);
  }, [scales, containerWidth]);

  const stableYTicks = useMemo(() => {
    const result = generateStableYTicks(yTicks, scaleStateRef.current.previousYTicks, realTime);
    scaleStateRef.current.previousYTicks = result.updatedPrevious;
    return result.ticks;
  }, [yTicks, realTime]);

  const xTicks = useMemo(() => {
    const currentScales = scales || scalesRef.current;
    const currentVisibleData = visibleDataRef.current;
    if (!currentScales || currentVisibleData.length === 0) return [];
    return generateXTicks(currentVisibleData, currentScales.xScale, innerWidth);
  }, [scales, innerWidth, containerWidth, visibleDataRef]);

  return {
    scales: scales || null,
    scalesRef,
    scaleStateRef,
    yTicks,
    stableYTicks,
    xTicks,
  };
}

/**
 * Hook for managing chart paths (line and area)
 */
export function useChartPaths(
  visibleDataRef: React.MutableRefObject<TimeSeriesDataPoint[]>,
  scales: ScaleFunctions | null,
  containerWidth: number
): {
  linePath: string;
  areaPath: string;
  pathChanged: boolean;
  previousPathRef: React.MutableRefObject<string>;
} {
  const previousPathRef = useRef<string>('');

  const linePath = useMemo(() => {
    if (!scales || visibleDataRef.current.length === 0) return '';
    return generateLinePath(visibleDataRef.current, scales);
  }, [scales, containerWidth, visibleDataRef]);

  const areaPath = useMemo(() => {
    if (!scales || !linePath || visibleDataRef.current.length === 0) return '';
    return generateAreaPath(linePath, visibleDataRef.current, scales);
  }, [linePath, scales, visibleDataRef]);

  const pathChanged = useMemo(() => {
    const changed = hasPathChanged(linePath, previousPathRef.current);
    if (changed) {
      previousPathRef.current = linePath;
    }
    return changed;
  }, [linePath]);

  return {
    linePath,
    areaPath,
    pathChanged,
    previousPathRef,
  };
}

/**
 * Hook for managing mouse interactions and hover state
 */
export function useChartInteractions(
  svgRef: React.RefObject<SVGSVGElement>,
  containerRef: React.RefObject<HTMLDivElement>,
  visibleDataRef: React.MutableRefObject<TimeSeriesDataPoint[]>,
  scales: ScaleFunctions | null,
  padding: { top: number; right: number; bottom: number; left: number },
  onHover?: (point: TimeSeriesDataPoint | null) => void
): {
  hoveredPoint: TimeSeriesDataPoint | null;
  hoverPosition: { x: number; y: number; pixelX?: number; pixelY?: number } | null;
  handleMouseMoveEvent: (e: React.MouseEvent<SVGSVGElement>) => void;
  handleMouseLeaveEvent: () => void;
} {
  const [hoveredPoint, setHoveredPoint] = useState<TimeSeriesDataPoint | null>(null);
  const [hoverPosition, setHoverPosition] = useState<{
    x: number;
    y: number;
    pixelX?: number;
    pixelY?: number;
  } | null>(null);

  const handleMouseMoveEvent = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      const currentScales = scales;
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
    },
    [scales, padding, onHover, svgRef, containerRef, visibleDataRef]
  );

  const handleMouseLeaveEvent = useCallback(() => {
    setHoveredPoint(null);
    setHoverPosition(null);
    if (onHover) onHover(null);
  }, [onHover]);

  return {
    hoveredPoint,
    hoverPosition,
    handleMouseMoveEvent,
    handleMouseLeaveEvent,
  };
}
