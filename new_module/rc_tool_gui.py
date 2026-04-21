#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import threading
import traceback
import tkinter as tk
from tkinter import ttk, messagebox


def _safe_float(s: str, default: float) -> float:
    try:
        return float(str(s).strip())
    except Exception:
        return float(default)


class RcToolApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('Radiative Cooling Tool ')
        self.root.geometry('900x650')

        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill='both', expand=True)

        # ---- Step 1: Download ----
        dl = ttk.LabelFrame(outer, text='1) 下载 ERA5（生成 .nc 以及可选 .csv）', padding=10)
        dl.pack(fill='x')

        r = 0
        ttk.Label(dl, text='开始日期 (YYYY-MM-DD):').grid(row=r, column=0, sticky='w')
        self.start_date = tk.StringVar(value='2025-07-12')
        ttk.Entry(dl, textvariable=self.start_date, width=14).grid(row=r, column=1, sticky='w', padx=(5, 15))

        ttk.Label(dl, text='结束日期 (YYYY-MM-DD):').grid(row=r, column=2, sticky='w')
        self.end_date = tk.StringVar(value='2025-07-13')
        ttk.Entry(dl, textvariable=self.end_date, width=14).grid(row=r, column=3, sticky='w', padx=(5, 15))

        r += 1
        ttk.Label(dl, text='经度 lon:').grid(row=r, column=0, sticky='w')
        self.lon = tk.StringVar(value='117.26956')
        ttk.Entry(dl, textvariable=self.lon, width=14).grid(row=r, column=1, sticky='w', padx=(5, 15))

        ttk.Label(dl, text='纬度 lat:').grid(row=r, column=2, sticky='w')
        self.lat = tk.StringVar(value='31.8369')
        ttk.Entry(dl, textvariable=self.lat, width=14).grid(row=r, column=3, sticky='w', padx=(5, 15))

        r += 1
        ttk.Label(dl, text='时区偏移 (hours, 例如中国=+8):').grid(row=r, column=0, sticky='w')
        self.tz_offset = tk.StringVar(value='8')
        ttk.Entry(dl, textvariable=self.tz_offset, width=14).grid(row=r, column=1, sticky='w', padx=(5, 15))

        ttk.Label(dl, text='输出目录:').grid(row=r, column=2, sticky='w')
        self.weather_dir = tk.StringVar(value=os.path.join(os.getcwd(), 'weather'))
        ttk.Entry(dl, textvariable=self.weather_dir, state='readonly').grid(row=r, column=3, sticky='we', padx=(5, 5))
        

        dl.grid_columnconfigure(3, weight=1)

        r += 1
        self.btn_init = ttk.Button(dl, text='初始化（清空weather）', command=self._on_init_weather)
        self.btn_init.grid(row=r, column=0, sticky='w')

        self.btn_download = ttk.Button(dl, text='下载天气文件', command=self._on_download)
        self.btn_download.grid(row=r, column=1, sticky='w', padx=(10, 0))

        self.merged_csv = tk.StringVar(value=os.path.join(self.weather_dir.get(), 'era5_merged.csv'))
        self.btn_merge = ttk.Button(dl, text='合并 CSV', command=self._on_merge)
        self.btn_merge.grid(row=r, column=2, sticky='w', padx=(10, 0))

        ttk.Label(dl, text='如果下载时间超过5min，请重新下载').grid(row=r, column=3, columnspan=2, sticky='w', padx=(10, 0))

        # ---- Step 3: Material params ----
        mp = ttk.LabelFrame(outer, text='3) 材料参数（反射率/发射率）', padding=10)
        mp.pack(fill='x', pady=(10, 0))

        r = 0
        ttk.Label(mp, text='太阳反射率 ρ_solar (0-1):').grid(row=r, column=0, sticky='w')
        self.rho_solar = tk.StringVar(value='0.91')
        ttk.Entry(mp, textvariable=self.rho_solar, width=10).grid(row=r, column=1, sticky='w', padx=(5, 15))

        ttk.Label(mp, text='长波发射率 ε (0-1):').grid(row=r, column=2, sticky='w')
        self.eps = tk.StringVar(value='0.98')
        ttk.Entry(mp, textvariable=self.eps, width=10).grid(row=r, column=3, sticky='w', padx=(5, 15))

        ttk.Label(mp, text='sky_view (0-1):').grid(row=r, column=4, sticky='w')
        self.sky_view = tk.StringVar(value='1.0')
        ttk.Entry(mp, textvariable=self.sky_view, width=10).grid(row=r, column=5, sticky='w')

        self.input_weather_csv = tk.StringVar(value=os.path.join(self.weather_dir.get(), 'era5_merged.csv'))
        self.output_results_csv = tk.StringVar(value=os.path.join(os.getcwd(), 'radiative_cooling_results_from_weather.csv'))
        self.export_figures = tk.BooleanVar(value=True)

        self.btn_compute = ttk.Button(mp, text='开始计算', command=self._on_compute)
        self.btn_compute.grid(row=0, column=6, rowspan=1, sticky='w', padx=(15, 0))

        self.btn_view_results = ttk.Button(mp, text='查看结果', command=self._open_results_dir)
        self.btn_view_results.grid(row=0, column=7, sticky='w', padx=(12, 0))

        # ---- Log ----
        lg = ttk.LabelFrame(outer, text='日志', padding=10)
        lg.pack(fill='both', expand=True, pady=(10, 0))

        self.log = tk.Text(lg, height=12, wrap='word')
        self.log.pack(fill='both', expand=True)

        btns = ttk.Frame(lg)
        btns.pack(fill='x', pady=(6, 0))
        ttk.Button(btns, text='清空日志', command=self._clear_log).pack(side='left')
        ttk.Button(btns, text='打开 weather 目录', command=self._open_weather_dir).pack(side='left', padx=(8, 0))

    # -------------------- Helpers --------------------
    def _log(self, msg: str):
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.root.update_idletasks()

    def _clear_log(self):
        self.log.delete('1.0', 'end')


    def _open_weather_dir(self):
        path = self.weather_dir.get()
        if not path:
            return
        try:
            if os.name == 'nt':
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                messagebox.showinfo('Info', f'请手动打开目录: {path}')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def _open_results_dir(self):
        path = os.path.join(os.getcwd(), 'figures', 'individual')
        try:
            os.makedirs(path, exist_ok=True)
            if os.name == 'nt':
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                messagebox.showinfo('Info', f'请手动打开目录: {path}')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    # -------------------- Actions (threaded) --------------------
    def _run_threaded(self, title: str, fn):
        def runner():
            try:
                self._set_busy(True)
                self._log(f'[{title}] 开始...')
                fn()
                self._log(f'[{title}] 完成')
            except Exception as e:
                self._log(f'[{title}] 失败: {e}')
                self._log(traceback.format_exc())
                messagebox.showerror('Error', f'{title} failed: {e}')
            finally:
                self._set_busy(False)

        t = threading.Thread(target=runner, daemon=True)
        t.start()

    def _set_busy(self, busy: bool):
        state = 'disabled' if busy else 'normal'
        for b in (self.btn_init, self.btn_download, self.btn_merge, self.btn_compute, self.btn_view_results):
            try:
                b.config(state=state)
            except Exception:
                pass

    def _on_init_weather(self):
        def job():
            weather_dir = self.weather_dir.get().strip() or os.path.join(os.getcwd(), 'weather')
            weather_dir = os.path.abspath(weather_dir)

            if not os.path.isdir(weather_dir):
                os.makedirs(weather_dir, exist_ok=True)

            if not messagebox.askyesno('确认', f'确定要删除该目录下所有文件吗？\n{weather_dir}'):
                self._log('初始化已取消')
                return

            removed = 0
            failed = 0
            for name in os.listdir(weather_dir):
                fp = os.path.join(weather_dir, name)
                try:
                    if os.path.isfile(fp) or os.path.islink(fp):
                        os.remove(fp)
                        removed += 1
                    elif os.path.isdir(fp):
                        # avoid recursive delete for safety
                        failed += 1
                except Exception:
                    failed += 1

            self._log(f'已删除文件数: {removed}, 跳过/失败: {failed}')

        self._run_threaded('初始化 weather', job)

    def _on_download(self):
        def job():
            from get import download_era5, area_from_point

            wd = self.weather_dir.get() or os.path.join(os.getcwd(), 'weather')
            os.makedirs(wd, exist_ok=True)

            start = self.start_date.get().strip()
            end = self.end_date.get().strip()
            lon = _safe_float(self.lon.get(), 117.26956)
            lat = _safe_float(self.lat.get(), 31.8369)
            tz = _safe_float(self.tz_offset.get(), 0.0)

            area = area_from_point(lon, lat)
            self._log(f'Weather dir: {wd}')
            self._log(f'Date: {start} -> {end}')
            self._log(f'Point: lon={lon}, lat={lat}, area={area}')

            # get.py always writes under CWD/weather; to keep behavior consistent,
            # we temporarily chdir via os.getcwd() assumption and then move if needed.
            # Here we just ensure wd == ./weather (recommended).
            # If user picked a different folder, we still pass output_path basename and then move.
            out_basename = None
            download_era5(start, end, area, out_basename, lon=lon, lat=lat, tz_offset_hours=tz)

            self._log('下载完成：请在 weather 目录检查生成的 .nc/.csv 文件')

        self._run_threaded('下载 ERA5', job)

    def _on_merge(self):
        def job():
            from merge_weather_csv import merge_weather_csvs

            weather_dir = self.weather_dir.get().strip() or os.path.join(os.getcwd(), 'weather')
            out_csv = self.merged_csv.get().strip() or os.path.join(weather_dir, 'era5_merged.csv')
            self._log(f'Merging from: {weather_dir}')
            self._log(f'Output: {out_csv}')
            out = merge_weather_csvs(weather_dir, out_csv)
            self._log(f'Merged CSV written to: {out}')
            self.input_weather_csv.set(out)

        self._run_threaded('合并 CSV', job)

    def _on_compute(self):
        def job():
            import radiative_cooling_from_weather_csv as rc

            inp = os.path.join(self.weather_dir.get(), 'era5_merged.csv')
            self.input_weather_csv.set(inp)
            if not os.path.exists(inp):
                raise FileNotFoundError(f"找不到 merged 文件: {inp}\n请先点击 '合并 CSV'。")

            eps = _safe_float(self.eps.get(), 0.98)
            rho = _safe_float(self.rho_solar.get(), 0.91)
            sky_view = _safe_float(self.sky_view.get(), 1.0)

            if not (0.0 <= eps <= 1.0):
                raise ValueError('ε 必须在 0-1 之间')
            if not (0.0 <= rho <= 1.0):
                raise ValueError('ρ_solar 必须在 0-1 之间')
            if not (0.0 <= sky_view <= 1.0):
                raise ValueError('sky_view 必须在 0-1 之间')

            # set material params for this run
            rc.MATERIAL_PARAMS['eps'] = float(eps)
            rc.MATERIAL_PARAMS['rho_solar'] = float(rho)
            rc.MATERIAL_PARAMS['sky_view'] = float(sky_view)

            self._log(f"Material params: eps={eps}, rho_solar={rho}, sky_view={sky_view}")

            df_raw = rc.load_weather_csv(inp)
            df = rc.compute_cooling(df_raw)

            out_csv = self.output_results_csv.get().strip() or 'radiative_cooling_results_from_weather.csv'
            os.makedirs(os.path.dirname(out_csv) or '.', exist_ok=True)
            df.to_csv(out_csv, index=False, encoding='utf-8-sig')
            self._log(f'Saved results: {out_csv}')

            if self.export_figures.get():
                rc.create_directories()
                out_dir = os.path.join('figures', 'individual')
                self._log(f'Exporting figures -> {out_dir}')
                rc.fig1_split(df, out_dir)
                rc.fig2_split(df, out_dir)
                rc.fig3_split(df, out_dir)
                rc.fig4_split(df, out_dir)
                rc.fig5_split(df, out_dir)
                self._log('Figures exported.')

        self._run_threaded('计算', job)


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use('clam')
    except Exception:
        pass
    app = RcToolApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
