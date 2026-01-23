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
      <label className="text-sm text-gray-400">{label}:</label>
      <input
        type="date"
        value={startDate}
        onChange={(e) => setStartDate(e.target.value)}
        className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm"
      />
      <span className="text-gray-400">to</span>
      <input
        type="date"
        value={endDate}
        onChange={(e) => setEndDate(e.target.value)}
        className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm"
      />
      <div className="flex items-center gap-2">
        <Button variant="primary" size="sm" onClick={handleApply}>
          Apply
        </Button>
        <Button variant="ghost" size="sm" onClick={handleClear}>
          Clear
        </Button>
      </div>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" onClick={() => handleQuickSelect(1)}>
          1D
        </Button>
        <Button variant="ghost" size="sm" onClick={() => handleQuickSelect(7)}>
          7D
        </Button>
        <Button variant="ghost" size="sm" onClick={() => handleQuickSelect(30)}>
          30D
        </Button>
      </div>
    </div>
  );
};









