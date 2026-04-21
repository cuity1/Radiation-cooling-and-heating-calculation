// 将绝对路径转换为相对路径（仅用于显示）
// 用于处理任务参数中的 _file_paths 等路径信息，防止泄露服务器绝对路径

// 隐藏目录层级，只保留最后1-2段（如文件名和直接父目录）
function shortenPath(path: string): string {
  const parts = path.split('/').filter(p => p.length > 0)
  if (parts.length <= 2) return path
  // 保留最后2段
  return parts.slice(-2).join('/')
}

export function convertToRelativePaths(obj: any): any {
  if (obj === null || obj === undefined) return obj
  if (typeof obj !== 'object') return obj
  if (Array.isArray(obj)) {
    return obj.map(item => convertToRelativePaths(item))
  }

  const result: any = {}
  for (const key of Object.keys(obj)) {
    const value = obj[key]
    if (key === '_file_paths' && typeof value === 'object' && value !== null) {
      // 处理 _file_paths 对象中的所有路径
      const convertedPaths: any = {}
      for (const pathKey of Object.keys(value)) {
        const pathValue = value[pathKey]
        if (typeof pathValue === 'string') {
          // 尝试提取相对路径部分并缩短
          // 常见格式: f:\work\... 或 /home/... 或 C:\...
          const winMatch = pathValue.match(/^[A-Za-z]:\\(.+)$/)
          const unixMatch = pathValue.match(/^\/(.+)$/)
          let relativePath: string
          if (winMatch) {
            relativePath = winMatch[1].replace(/\\/g, '/')
          } else if (unixMatch) {
            relativePath = unixMatch[1]
          } else {
            relativePath = pathValue
          }
          convertedPaths[pathKey] = shortenPath(relativePath)
        } else {
          convertedPaths[pathKey] = convertToRelativePaths(pathValue)
        }
      }
      result[key] = convertedPaths
    } else if (typeof value === 'object') {
      result[key] = convertToRelativePaths(value)
    } else {
      result[key] = value
    }
  }
  return result
}
