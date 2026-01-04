"""Atmospheric emissivity vs solar irradiance cloud-map dialog + generator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
)

from gui.i18n import language_manager
from gui.widgets import AnimatedButton, CardFrame, TitleLabel
from gui.windows import InteractivePlotWindow

from core.calculations import main_calculating_gui
from core.config import load_config


class EmissivitySolarCloudDialog(QDialog):
    """大气发射率-太阳光强云图对话框"""

    def __init__(self, parent, file_paths: dict):
        super().__init__(parent)
        self.file_paths = file_paths.copy()
        self.setFixedSize(600, 300)

        language_manager.language_changed.connect(self.update_language)

        self.init_ui()
        self.update_language()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        self.title_label = TitleLabel('')
        layout.addWidget(self.title_label)

        input_card = CardFrame()
        input_card.setMinimumHeight(150)
        input_layout = QVBoxLayout(input_card)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignCenter)
        input_layout.addWidget(self.info_label)

        self.execute_button = AnimatedButton('')
        self.execute_button.clicked.connect(self.run_cloud_calculation)
        input_layout.addWidget(self.execute_button, alignment=Qt.AlignCenter)

        self.status_label = QLabel('')
        self.status_label.setObjectName('status')
        self.status_label.setAlignment(Qt.AlignCenter)
        input_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        input_layout.addWidget(self.progress_bar)

        layout.addWidget(input_card)

        button_layout = QHBoxLayout()
        self.close_button = AnimatedButton('')
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def update_language(self):
        title = (
            '大气发射率-太阳光强云图'
            if language_manager.is_chinese()
            else 'Atmospheric Emissivity - Solar Irradiance Cloud Map'
        )
        self.setWindowTitle(title)
        self.title_label.setText(title)

        info = (
            '点击下方按钮生成云图\n'
            '横轴：大气发射率 (0-1)\n'
            '纵轴：太阳光强 (0-1000 W/m²)\n'
            '颜色：辐射制冷功率 (W/m²)'
            if language_manager.is_chinese()
            else 'Click button to generate cloud map\n'
            'X-axis: Atmospheric emissivity (0-1)\n'
            'Y-axis: Solar irradiance (0-1000 W/m²)\n'
            'Color: Cooling power (W/m²)'
        )
        self.info_label.setText(info)

        self.execute_button.setText(language_manager.get('generate_cloud'))
        self.close_button.setText(language_manager.get('close'))

    def run_cloud_calculation(self):
        try:
            self.execute_button.setEnabled(False)
            self.status_label.setText(language_manager.get('calculating_msg'))
            self.progress_bar.setVisible(True)
            QApplication.processEvents()

            generate_emissivity_solar_cloud(self.file_paths)

            self.status_label.setText(language_manager.get('calculation_complete'))
            self.progress_bar.setVisible(False)
            self.execute_button.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(
                self,
                language_manager.get('error'),
                f"{language_manager.get('error')}: {e}",
            )
            self.status_label.setText(language_manager.get('calculation_failed'))
            self.progress_bar.setVisible(False)
            self.execute_button.setEnabled(True)


def generate_emissivity_solar_cloud(
    file_paths: dict,
    n_emissivity: int = 101,
    n_solar: int = 101,
    solar_max: float = 1000.0,
) -> None:
    """生成大气发射率-太阳光强云图。

    Notes:
    - Restored original behavior: 2D grid over emissivity (0..1) and S_solar (0..solar_max).
    - Increased default grid resolution from 51x51 to 101x101.
    """

    config = load_config(file_paths['config'])
    T_a1 = float(config['T_a1'])
    T_a = T_a1 + 273.15
    sigma = 5.670374419e-8

    print('正在计算材料参数...')
    avg_emissivity, R_sol, _ = main_calculating_gui(file_paths)
    alpha_s = 1 - R_sol

    print(f'材料平均发射率: {avg_emissivity:.4f}')
    print(f'太阳吸收率: {alpha_s:.4f}')

    atm_emissivity_range = np.linspace(0, 1, int(n_emissivity))
    solar_irradiance_range = np.linspace(0, float(solar_max), int(n_solar))

    cooling_power_matrix = np.zeros((len(solar_irradiance_range), len(atm_emissivity_range)))

    print('开始计算云图数据...')
    for i, S_solar in enumerate(solar_irradiance_range):
        # precompute solar absorption at this irradiance
        P_solar = alpha_s * S_solar
        for j, emissivity_atm in enumerate(atm_emissivity_range):
            # ΔT=0
            T_film = T_a
            P_rad_out = avg_emissivity * sigma * T_film**4
            P_rad_in = avg_emissivity * emissivity_atm * sigma * T_a**4
            P_cooling = P_rad_out - P_rad_in - P_solar
            cooling_power_matrix[i, j] = P_cooling

        if (i + 1) % max(1, int(len(solar_irradiance_range) / 10)) == 0:
            print(f'进度: {(i+1)/len(solar_irradiance_range)*100:.0f}%')

    print('计算完成，正在绘制云图...')

    from matplotlib.colors import LinearSegmentedColormap

    try:
        plt.style.use('seaborn-v0_8-whitegrid')
    except Exception:
        try:
            plt.style.use('seaborn-whitegrid')
        except Exception:
            pass

    plt.rcParams.update(
        {
            'font.family': 'Arial',
            'font.size': 12,
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'figure.figsize': (12, 10),
            'figure.dpi': 120,
        }
    )

    colors = [(0, 'navy'), (0.3, 'blue'), (0.5, 'white'), (0.7, 'red'), (1, 'darkred')]
    cmap = LinearSegmentedColormap.from_list('cooling_power', colors, N=256)

    fig, ax = plt.subplots(figsize=(12, 9))

    X, Y = np.meshgrid(atm_emissivity_range, solar_irradiance_range)

    contourf = ax.contourf(X, Y, cooling_power_matrix, levels=80, cmap=cmap, alpha=0.95)
    contours = ax.contour(X, Y, cooling_power_matrix, levels=12, colors='black', alpha=0.35, linewidths=0.8)
    ax.clabel(contours, inline=True, fontsize=9, fmt='%.0f')

    cbar = fig.colorbar(contourf, ax=ax, pad=0.02)
    cbar.set_label('Cooling Power (W/m²)', fontsize=13, weight='bold')

    ax.set_xlabel('Atmospheric Emissivity', fontsize=13, weight='bold')
    ax.set_ylabel('Solar Irradiance (W/m²)', fontsize=13, weight='bold')
    ax.set_title(
        'Radiative Cooling Power Cloud Map\n'
        f'Material Emissivity: {avg_emissivity:.3f}, Solar Absorptance: {alpha_s:.3f}\n'
        f'Ambient Temperature: {T_a1:.1f}°C, ΔT = 0°C',
        fontsize=15,
        weight='bold',
        pad=15,
    )
    ax.grid(True, linestyle='--', alpha=0.3)

    # zero line
    try:
        zero_contour = ax.contour(X, Y, cooling_power_matrix, levels=[0], colors='lime', linewidths=2.0, linestyles='--')
        try:
            ax.clabel(zero_contour, inline=True, fontsize=10, fmt='Zero')
        except Exception:
            pass
    except Exception:
        pass

    plt.tight_layout()

    dialog = InteractivePlotWindow(fig, parent=None, title='Atmospheric Emissivity - Solar Irradiance Cloud Map')
    dialog.exec_()

    print('正在保存数据...')
    save_file_path, _ = QFileDialog.getSaveFileName(
        None,
        '保存结果文件' if language_manager.is_chinese() else 'Save Result File',
        '',
        'Excel files (*.xlsx)',
    )

    if save_file_path:
        df_matrix = pd.DataFrame(
            cooling_power_matrix,
            index=np.round(solar_irradiance_range, 2),
            columns=np.round(atm_emissivity_range, 3),
        )
        df_matrix.index.name = 'Solar_Irradiance_W/m2'
        df_matrix.columns.name = 'Atmospheric_Emissivity'

        with pd.ExcelWriter(save_file_path) as writer:
            df_matrix.to_excel(writer, sheet_name='Cooling_Power')

            params_df = pd.DataFrame(
                {
                    'Parameter': [
                        'Material Emissivity',
                        'Solar Absorptance',
                        'Ambient Temperature (°C)',
                        'Film Temperature (°C)',
                        'Delta T (°C)',
                        'Grid: emissivity points',
                        'Grid: solar points',
                        'Solar max (W/m²)',
                    ],
                    'Value': [
                        f'{avg_emissivity:.4f}',
                        f'{alpha_s:.4f}',
                        f'{T_a1:.1f}',
                        f'{T_a1:.1f}',
                        '0.0',
                        str(len(atm_emissivity_range)),
                        str(len(solar_irradiance_range)),
                        f'{solar_max:.1f}',
                    ],
                }
            )
            params_df.to_excel(writer, sheet_name='Parameters', index=False)

        print(f'结果已保存到: {save_file_path}')
        QMessageBox.information(
            None,
            language_manager.get('success'),
            f"{language_manager.get('data_saved')}: {save_file_path}",
        )
