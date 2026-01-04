"""Main windows and plot windows."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QSizePolicy,
)

# matplotlib imports
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.text import Text


class MatplotlibCanvas(FigureCanvas):
    def __init__(self, parent=None, width: float = 5, height: float = 4, dpi: int = 100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)


class InteractivePlotWindow(QDialog):
    """交互式绘图窗口，支持轴范围调整、元素拖动和动态交互"""

    def __init__(self, fig: Figure, parent=None, title: str = 'Interactive Plot'):
        super().__init__(parent)
        self.fig = fig
        self.title = title
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)

        self.axes_list = fig.get_axes()
        self.draggable_elements = []
        self.drag_data = None

        main_layout = QVBoxLayout(self)

        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        self.canvas = FigureCanvas(fig)
        main_layout.addWidget(self.canvas)

        self.toolbar = NavigationToolbar(self.canvas, self)
        main_layout.addWidget(self.toolbar)

        self.setup_draggable_elements()

        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)

        self.canvas.draw()

    def create_control_panel(self):
        panel = QGroupBox('Axis Range Control')
        layout = QGridLayout()

        if len(self.axes_list) > 1:
            layout.addWidget(QLabel('Select Subplot:'), 0, 0)
            self.axes_combo = QComboBox()
            for i, ax in enumerate(self.axes_list):
                title = ax.get_title() or f'Subplot {i+1}'
                self.axes_combo.addItem(title)
            self.axes_combo.currentIndexChanged.connect(self.update_axis_display)
            layout.addWidget(self.axes_combo, 0, 1, 1, 2)
        else:
            self.axes_combo = None

        row_offset = 1 if len(self.axes_list) > 1 else 0

        layout.addWidget(QLabel('X-axis Range:'), row_offset, 0)
        self.xmin_input = QLineEdit(); self.xmax_input = QLineEdit()
        self.xmin_input.setPlaceholderText('Min'); self.xmax_input.setPlaceholderText('Max')
        layout.addWidget(self.xmin_input, row_offset, 1)
        layout.addWidget(QLabel('to'), row_offset, 2)
        layout.addWidget(self.xmax_input, row_offset, 3)
        x_apply_btn = QPushButton('Apply X-axis'); x_apply_btn.clicked.connect(self.apply_x_limits)
        layout.addWidget(x_apply_btn, row_offset, 4)
        x_auto_btn = QPushButton('Auto X-axis'); x_auto_btn.clicked.connect(self.auto_x_limits)
        layout.addWidget(x_auto_btn, row_offset, 5)

        layout.addWidget(QLabel('Y-axis Range:'), row_offset + 1, 0)
        self.ymin_input = QLineEdit(); self.ymax_input = QLineEdit()
        self.ymin_input.setPlaceholderText('Min'); self.ymax_input.setPlaceholderText('Max')
        layout.addWidget(self.ymin_input, row_offset + 1, 1)
        layout.addWidget(QLabel('to'), row_offset + 1, 2)
        layout.addWidget(self.ymax_input, row_offset + 1, 3)
        y_apply_btn = QPushButton('Apply Y-axis'); y_apply_btn.clicked.connect(self.apply_y_limits)
        layout.addWidget(y_apply_btn, row_offset + 1, 4)
        y_auto_btn = QPushButton('Auto Y-axis'); y_auto_btn.clicked.connect(self.auto_y_limits)
        layout.addWidget(y_auto_btn, row_offset + 1, 5)

        self.drag_mode_checkbox = QCheckBox('Enable Element Dragging')
        self.drag_mode_checkbox.setChecked(True)
        layout.addWidget(self.drag_mode_checkbox, row_offset + 2, 0, 1, 3)

        reset_btn = QPushButton('Reset View'); reset_btn.clicked.connect(self.reset_view)
        layout.addWidget(reset_btn, row_offset + 2, 3, 1, 3)

        self.update_axis_display()
        panel.setLayout(layout)
        return panel

    def get_current_axes(self):
        if self.axes_combo:
            idx = self.axes_combo.currentIndex()
            return self.axes_list[idx] if idx < len(self.axes_list) else self.axes_list[0]
        return self.axes_list[0] if self.axes_list else None

    def update_axis_display(self):
        ax = self.get_current_axes()
        if ax:
            xlim = ax.get_xlim(); ylim = ax.get_ylim()
            self.xmin_input.setText(f'{xlim[0]:.2f}')
            self.xmax_input.setText(f'{xlim[1]:.2f}')
            self.ymin_input.setText(f'{ylim[0]:.2f}')
            self.ymax_input.setText(f'{ylim[1]:.2f}')

    def apply_x_limits(self):
        try:
            xmin = float(self.xmin_input.text()); xmax = float(self.xmax_input.text())
            if xmin >= xmax:
                QMessageBox.warning(self, 'Warning', 'X-axis minimum must be less than maximum')
                return
            ax = self.get_current_axes()
            if ax:
                ax.set_xlim(xmin, xmax)
                self.canvas.draw()
        except ValueError:
            QMessageBox.warning(self, 'Warning', 'Please enter a valid number')

    def apply_y_limits(self):
        try:
            ymin = float(self.ymin_input.text()); ymax = float(self.ymax_input.text())
            if ymin >= ymax:
                QMessageBox.warning(self, 'Warning', 'Y-axis minimum must be less than maximum')
                return
            ax = self.get_current_axes()
            if ax:
                ax.set_ylim(ymin, ymax)
                self.canvas.draw()
        except ValueError:
            QMessageBox.warning(self, 'Warning', 'Please enter a valid number')

    def auto_x_limits(self):
        ax = self.get_current_axes()
        if ax:
            ax.relim(); ax.autoscale(axis='x')
            self.update_axis_display(); self.canvas.draw()

    def auto_y_limits(self):
        ax = self.get_current_axes()
        if ax:
            ax.relim(); ax.autoscale(axis='y')
            self.update_axis_display(); self.canvas.draw()

    def reset_view(self):
        ax = self.get_current_axes()
        if ax:
            ax.relim(); ax.autoscale()
            self.update_axis_display(); self.canvas.draw()

    def setup_draggable_elements(self):
        for ax in self.axes_list:
            legend = ax.get_legend()
            if legend:
                legend.set_draggable(True, update='loc')
                self.draggable_elements.append(legend)

            for text in ax.texts:
                text.set_picker(True)
                self.draggable_elements.append(text)

    def on_press(self, event):
        if not self.drag_mode_checkbox.isChecked():
            return
        if event.inaxes is None:
            return

        for element in self.draggable_elements:
            # Legend dragging is handled by matplotlib itself
            if isinstance(element, Legend):
                continue

            if isinstance(element, Text) and hasattr(element, 'contains'):
                contains, _ = element.contains(event)
                if contains:
                    trans = element.get_transform()
                    if trans == event.inaxes.transAxes:
                        pos = element.get_position()
                        self.drag_data = {
                            'element': element,
                            'x0': event.x,
                            'y0': event.y,
                            'pos0': pos,
                            'transform': 'axes',
                        }
                    else:
                        self.drag_data = {
                            'element': element,
                            'x0': event.xdata,
                            'y0': event.ydata,
                            'pos0': element.get_position(),
                            'transform': 'data',
                        }
                    break

    def on_release(self, event):
        self.drag_data = None

    def on_motion(self, event):
        if not self.drag_mode_checkbox.isChecked():
            return
        if self.drag_data is None:
            return

        element = self.drag_data['element']
        if isinstance(element, Text):
            if self.drag_data['transform'] == 'axes':
                if event.inaxes:
                    dx_pixel = event.x - self.drag_data['x0']
                    dy_pixel = event.y - self.drag_data['y0']
                    bbox = event.inaxes.bbox
                    dx_axes = dx_pixel / bbox.width
                    dy_axes = -dy_pixel / bbox.height
                    pos0 = self.drag_data['pos0']
                    element.set_position((pos0[0] + dx_axes, pos0[1] + dy_axes))
                    self.canvas.draw_idle()
            else:
                if event.inaxes and event.xdata is not None and event.ydata is not None:
                    element.set_position((event.xdata, event.ydata))
                    self.canvas.draw_idle()
