/**
 * Time Series Chart Types
 */

export interface TimeSeriesDataPoint {
  timestamp: string;
  value: number;
  label?: string;
  device_id?: string;
}

export interface TimeSeriesChartProps {
  data: TimeSeriesDataPoint[];
  height?: number;
  color?: string;
  showGrid?: boolean;
  showLegend?: boolean;
  realTime?: boolean;
  onHover?: (point: TimeSeriesDataPoint | null) => void;
}

export interface ChartDimensions {
  width: number;
  height: number;
  padding: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
  innerWidth: number;
  innerHeight: number;
}

export interface ScaleFunctions {
  xScale: (time: number) => number;
  yScale: (value: number) => number;
  minValue: number;
  maxValue: number;
}

export interface HoverPosition {
  x: number;
  y: number;
  pixelX?: number;
  pixelY?: number;
}

export interface Tick {
  value: number;
  y: number;
}

export interface XTick {
  x: number;
  timestamp: string;
}

export interface YRange {
  min: number;
  max: number;
}










