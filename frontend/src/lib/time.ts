const CHINA_TIMEZONE_OFFSET = 8 * 60 * 60 * 1000 // UTC+8

export function formatLocalTime(iso: string): string {
  try {
    const date = new Date(iso)
    // 后端存储的是UTC时间，需要+8小时转换为中国时间
    const chinaTime = new Date(date.getTime() + CHINA_TIMEZONE_OFFSET)
    return `${chinaTime.getFullYear()}/${String(chinaTime.getMonth() + 1).padStart(2, '0')}/${String(chinaTime.getDate()).padStart(2, '0')} ${String(chinaTime.getHours()).padStart(2, '0')}:${String(chinaTime.getMinutes()).padStart(2, '0')}:${String(chinaTime.getSeconds()).padStart(2, '0')}`
  } catch {
    return iso
  }
}
