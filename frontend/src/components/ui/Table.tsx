import { PropsWithChildren } from 'react'
import clsx from 'clsx'

interface Column<T> {
  key: string
  header: string
  width?: string
  render?: (row: T) => React.ReactNode
}

export function Table<T extends Record<string, unknown>>({
  columns,
  data,
  emptyMessage = '暂无数据',
  className,
}: {
  columns: Column<T>[]
  data: T[]
  emptyMessage?: string
  className?: string
}) {
  return (
    <div className={clsx('w-full overflow-x-auto rounded-field border border-border glass-light', className)}>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-bg-elevated/60">
            {columns.map((col) => (
              <th
                key={col.key}
                className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-text-muted whitespace-nowrap"
                style={{ width: col.width }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-8 text-center text-sm text-text-muted"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, i) => (
              <tr
                key={i}
                className="border-b border-border/50 last:border-0 hover:bg-white/[0.02] transition-colors duration-100"
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3 text-text-secondary">
                    {col.render ? col.render(row) : String(row[col.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
