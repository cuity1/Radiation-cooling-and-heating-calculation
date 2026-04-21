/**
 * Plotly 统一布局配置
 * 确保所有图表在日间和夜间主题下都清晰可见：
 * - 字体颜色：黑色（#000000）
 * - 背景颜色：白色（#FFFFFF），禁止透明
 *
 * 注意：兼容两种写法
 *   xaxis: { title: 'Wind (m/s)' }
 *   xaxis: { title: { text: 'Wind (m/s)' } }
 * 如果直接把字符串展平为对象，会导致 text 丢失，从而看不到坐标轴标题。
 */
export function getPlotlyLayout(baseLayout: any = {}): any {
  const rawXAxisTitle = baseLayout.xaxis?.title
  const normXAxisTitle =
    typeof rawXAxisTitle === 'string' ? { text: rawXAxisTitle } : rawXAxisTitle || {}

  const rawYAxisTitle = baseLayout.yaxis?.title
  const normYAxisTitle =
    typeof rawYAxisTitle === 'string' ? { text: rawYAxisTitle } : rawYAxisTitle || {}

  const rawTitle = baseLayout.title
  const normTitle = typeof rawTitle === 'string' ? { text: rawTitle } : rawTitle || undefined

  return {
    ...baseLayout,
    // 白色背景，禁止透明
    paper_bgcolor: '#FFFFFF',
    plot_bgcolor: '#FFFFFF',
    // 黑色字体，确保在日间主题可见
    font: {
      color: '#000000',
      ...baseLayout.font,
    },
    // 坐标轴字体颜色
    xaxis: {
      ...baseLayout.xaxis,
      title: {
        ...normXAxisTitle,
        font: {
          color: '#000000',
          ...normXAxisTitle?.font,
        },
      },
      tickfont: {
        color: '#000000',
        ...baseLayout.xaxis?.tickfont,
      },
      gridcolor: 'rgba(0, 0, 0, 0.1)', // 浅灰色网格线
    },
    yaxis: {
      ...baseLayout.yaxis,
      title: {
        ...normYAxisTitle,
        font: {
          color: '#000000',
          ...normYAxisTitle?.font,
        },
      },
      tickfont: {
        color: '#000000',
        ...baseLayout.yaxis?.tickfont,
      },
      gridcolor: 'rgba(0, 0, 0, 0.1)', // 浅灰色网格线
    },
    // 图例字体颜色
    legend: {
      ...baseLayout.legend,
      font: {
        color: '#000000',
        ...baseLayout.legend?.font,
      },
    },
    // 标题字体颜色（如果存在）
    title: normTitle
      ? {
          ...normTitle,
          font: {
            color: '#000000',
            ...normTitle?.font,
          },
        }
      : undefined,
  }
}

/**
 * 合并后端返回的 Plotly spec，确保使用统一的布局配置
 */
export function mergePlotlyLayout(backendLayout: any): any {
  return getPlotlyLayout(backendLayout)
}
