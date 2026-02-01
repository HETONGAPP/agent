/**
 * Date Range Picker Component
 * Reusable date range picker for filtering
 */

import { useState } from 'react';
import { Button } from './Button';

interface DateRangePickerProps {
  onRangeChange: (start: string | null, end: string | null) => void;
  label?: string;
}

export const DateRangePicker = ({ onRangeChange, label = 'Date Range' }: DateRangePickerProps) => {
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  // Convert date string (YYYY-MM-DD) to ISO timestamp with time
  // Start date: set to 00:00:00 of that day in local timezone, then convert to UTC
  // End date: set to 00:00:00 of the NEXT day (exclusive) to include the entire day
  // InfluxDB's range() stop parameter is exclusive, so we need to use next day's start
  const formatDateForQuery = (dateStr: string, isEndDate: boolean = false): string => {
    if (!dateStr) return '';
    // Parse date string (YYYY-MM-DD) - this creates a date in local timezone at midnight
    const [year, month, day] = dateStr.split('-').map(Number);
    const date = new Date(year, month - 1, day); // month is 0-indexed
    
    if (isEndDate) {
      // Set to start of NEXT day (00:00:00) because InfluxDB range stop is exclusive
      // This ensures we include all data from the selected end date
      date.setDate(date.getDate() + 1);
    }
    // date is already at 00:00:00 in local timezone
    // Convert to ISO string (which will be in UTC)
    return date.toISOString();
  };

  const handleApply = () => {
    const start = startDate ? formatDateForQuery(startDate, false) : null;
    const end = endDate ? formatDateForQuery(endDate, true) : null;
    onRangeChange(start, end);
  };

  const handleClear = () => {
    setStartDate('');
    setEndDate('');
    onRangeChange(null, null);
  };

  const handleQuickSelect = (days: number) => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - days);
    
    const formatDate = (date: Date) => {
      return date.toISOString().split('T')[0];
    };
    
    const startDateStr = formatDate(start);
    const endDateStr = formatDate(end);
    
    setStartDate(startDateStr);
    setEndDate(endDateStr);
    
    // Convert to ISO timestamps with proper time
    const startISO = formatDateForQuery(startDateStr, false);
    const endISO = formatDateForQuery(endDateStr, true);
    onRangeChange(startISO, endISO);
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <label className="text-xs text-gray-500 shrink-0">{label}</label>
      <input
        type="date"
        value={startDate}
        onChange={(e) => setStartDate(e.target.value)}
        className="px-2 py-1.5 bg-gray-800/80 border border-gray-600/60 rounded text-white text-sm w-[130px] max-w-full"
      />
      <span className="text-gray-500 text-xs shrink-0">→</span>
      <input
        type="date"
        value={endDate}
        onChange={(e) => setEndDate(e.target.value)}
        className="px-2 py-1.5 bg-gray-800/80 border border-gray-600/60 rounded text-white text-sm w-[130px] max-w-full"
      />
      <div className="flex items-center gap-1">
        <Button variant="primary" size="sm" onClick={handleApply} className="text-xs px-2 py-1">
          Apply
        </Button>
        <Button variant="ghost" size="sm" onClick={handleClear} className="text-xs px-2 py-1">
          Clear
        </Button>
      </div>
      <div className="flex items-center gap-0.5">
        <button
          type="button"
          onClick={() => handleQuickSelect(1)}
          className="px-1.5 py-1 text-xs text-gray-400 hover:text-white rounded hover:bg-gray-700/50"
        >
          1D
        </button>
        <button
          type="button"
          onClick={() => handleQuickSelect(7)}
          className="px-1.5 py-1 text-xs text-gray-400 hover:text-white rounded hover:bg-gray-700/50"
        >
          7D
        </button>
        <button
          type="button"
          onClick={() => handleQuickSelect(30)}
          className="px-1.5 py-1 text-xs text-gray-400 hover:text-white rounded hover:bg-gray-700/50"
        >
          30D
        </button>
      </div>
    </div>
  );
};









