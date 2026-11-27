import { Table2, Database } from 'lucide-react';
import { DataTableData } from '../../types';

interface DataTableCardProps {
  title?: string;
  table?: DataTableData | null;
}

export function DataTableCard({ title, table }: DataTableCardProps) {
  if (!table) {
    return null;
  }

  const columns = Array.isArray(table.columns) ? table.columns : [];
  const rows = Array.isArray(table.rows) ? table.rows : [];

  return (
    <div className="rounded-lg border border-[#1E293B] bg-[#0E1420] p-5 shadow-xl space-y-4">
      {/* Header strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#1E293B] pb-3">
        <div className="flex items-center space-x-3">
          <div className="rounded-md bg-[#1E293B] p-2 text-[#38BDF8]">
            <Table2 className="h-4 w-4" />
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#38BDF8] block">
              OFFICIAL HISTORICAL DATA • CLASSIFICATION TABLE
            </span>
            <h2 className="text-base font-bold text-white tracking-wide">
              {title || table.subtitle || 'Historical Records'}
            </h2>
            {table.subtitle && (
              <p className="text-[11px] font-mono text-[#94A3B8]">{table.subtitle}</p>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-1.5 rounded-full border border-[#38BDF8]/30 bg-[#0B0F17] px-3 py-1 text-[11px] font-mono text-[#38BDF8] self-start sm:self-auto">
          <Database className="h-3 w-3" />
          <span>{rows.length} rows</span>
        </div>
      </div>

      {/* Scrollable dark HUD table */}
      {columns.length > 0 && rows.length > 0 ? (
        <div className="overflow-x-auto max-h-[460px] rounded border border-[#1E293B] bg-[#0B0F17]">
          <table className="min-w-full divide-y divide-[#1E293B] text-xs">
            <thead className="bg-[#121824] sticky top-0 z-10">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col}
                    className="px-3.5 py-2.5 text-left font-mono text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8] whitespace-nowrap"
                  >
                    {col.replace(/_/g, ' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E293B]/60">
              {rows.map((row, rowIdx) => (
                <tr
                  key={rowIdx}
                  className={rowIdx % 2 === 0 ? 'bg-[#0B0F17]' : 'bg-[#121824]/60'}
                >
                  {columns.map((col) => {
                    const rawVal = row?.[col];
                    const displayVal =
                      rawVal === null || rawVal === undefined || rawVal === '' ? '—' : String(rawVal);
                    const isNumeric = typeof rawVal === 'number';
                    return (
                      <td
                        key={col}
                        className={`px-3.5 py-2 whitespace-nowrap text-[#E2E8F0] ${
                          isNumeric ? 'font-mono text-[#F8FAFC]' : 'font-sans'
                        }`}
                      >
                        {displayVal}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-6 text-center text-xs font-mono text-[#94A3B8]">
          No table rows available to display.
        </div>
      )}
    </div>
  );
}
