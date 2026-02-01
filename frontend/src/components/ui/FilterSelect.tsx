/**
 * Filter Select Component
 * Consistent label + select for filter bars
 */

interface FilterSelectProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
  className?: string;
}

const selectClass =
  'px-2.5 py-1.5 bg-gray-800/80 border border-gray-600/60 rounded text-white text-sm min-w-0 focus:outline-none focus:ring-1 focus:ring-blue-500/60 focus:border-gray-500';

export const FilterSelect = ({
  label,
  value,
  onChange,
  options,
  placeholder = 'All',
  className = '',
}: FilterSelectProps) => (
  <div className={`flex items-center gap-2 shrink-0 ${className}`}>
    <label className="text-xs text-gray-500 whitespace-nowrap">{label}</label>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={selectClass}
    >
      <option value="">{placeholder}</option>
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  </div>
);
