import { api } from './api'

export type KoppenPreviewRequest = {
  csv_content: string
  colormap: string
  title: string
  colorbar_label: string
  z_min: number | null
  z_max: number | null
  add_grid?: boolean
}

export type KoppenPreviewResult = {
  data_url: string
  cache_key: string
  vmin: number
  vmax: number
  colormap: string
  colorbar_label: string
  zones_loaded: string[]
}

export const koppenMapApi = {
  /**
   * Generate a Köppen zone raster map preview.
   * The server caches results by a SHA-256 hash of all params, so identical
   * subsequent calls are served instantly from disk without calling GEE.
   */
  getPreview: async (params: KoppenPreviewRequest): Promise<KoppenPreviewResult> => {
    const res = await api.post<KoppenPreviewResult>(
      '/tools/koppen-map-preview',
      params
    )
    return res.data
  },

  /**
   * Trigger a full-resolution PNG download.
   * `cacheKey` is returned from getPreview().
   */
  getExportUrl: (cacheKey: string): string => {
    return `${api.defaults.baseURL}/tools/koppen-map-export/${cacheKey}`
  },
}
