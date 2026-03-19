import sys
import os
import argparse
import traceback
import math
import random
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox, QProgressBar, QGraphicsOpacityEffect, QDialog, QScrollArea
from PySide6.QtCore import QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve, Qt, QPoint, QRect, QPointF, QRectF
from PySide6.QtGui import QFont, QCursor, QPixmap, QPainter, QColor, QPen, QBrush, QPolygon, QIcon, QRadialGradient, QPainterPath
import pyqtgraph as pg
import time
import csv
pg.setConfigOptions(useOpenGL=False, antialias=True, enableExperimental=False)

class RecordingReviewDialog(QDialog):
    def __init__(self, parent, data):
        super().__init__(parent)
        self.setWindowTitle('EEG Recording Review & Crop')
        self.setMinimumSize(900, 600)
        self.data = data  # List of tuples
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Adjust crop region to select the data you want to save. Drag the vertical lines.")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Plot
        self.plot = pg.PlotWidget()
        self.plot.setBackground('#ffffff')
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel('bottom', "Time", units='s')
        self.plot.setLabel('left', "Signal Amplitude")
        layout.addWidget(self.plot)
        
        # Extract timestamp array and raw signal array for visualization
        self.t_data = [row[0] for row in data]
        self.raw_data = [row[1] for row in data]
        
        self.curve = self.plot.plot(self.t_data, self.raw_data, pen=pg.mkPen('#3b82f6', width=1))
        
        if len(self.t_data) > 0:
            self.region = pg.LinearRegionItem([self.t_data[0], self.t_data[-1]])
            self.region.setZValue(10)
            self.plot.addItem(self.region)
        
        # Controls
        c_layout = QHBoxLayout()
        self.infoLabel = QLabel(f"Total recorded: {len(data)} samples")
        c_layout.addWidget(self.infoLabel)
        
        c_layout.addStretch()
        
        self.saveBtn = QPushButton("Save Cropped to CSV")
        self.saveBtn.setStyleSheet("background: #10b981; color: white; font-weight: bold; border-radius: 8px; padding: 10px 20px;")
        self.saveBtn.clicked.connect(self.save_csv)
        c_layout.addWidget(self.saveBtn)
        
        layout.addLayout(c_layout)
        
    def save_csv(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Save EEG Data", "aether_recording.csv", "CSV Files (*.csv)")
        if not path: return
        
        minX, maxX = self.region.getRegion()
        
        # Filter data by region
        cropped = [row for row in self.data if minX <= row[0] <= maxX]
        
        try:
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp(s)", "Raw", "Attention", "Meditation", "Delta", "Theta", "LowAlpha", "HighAlpha", "LowBeta", "HighBeta", "LowGamma", "MidGamma"])
                writer.writerows(cropped)
            self.infoLabel.setText(f"Successfully saved {len(cropped)} samples!")
            self.infoLabel.setStyleSheet("color: #10b981; font-weight: bold;")
        except Exception as e:
            self.infoLabel.setText(f"Error saving: {e}")
            self.infoLabel.setStyleSheet("color: #ef4444; font-weight: bold;")

try:
    from .serial_reader import SerialWorker, list_ports, detect_port_baud
except Exception:
    try:
        from src.serial_reader import SerialWorker, list_ports, detect_port_baud
    except Exception:
        from serial_reader import SerialWorker, list_ports, detect_port_baud
try:
    from .mouse_control import MouseController
except Exception:
    try:
        from src.mouse_control import MouseController
    except Exception:
        from mouse_control import MouseController

from PySide6.QtGui import QPainterPath, QRadialGradient
from PySide6.QtCore import QRectF

class CircularRingGauge(QWidget):
    def __init__(self, color, title=''):
        super().__init__()
        self.color = QColor(color)
        self.bg_color = QColor('#e2e8f0') 
        self.val = 0
        self.setMinimumSize(100, 100)
        self.title = title
        
    def setValue(self, v):
        self.val = max(0, min(100, v))
        self.update()
    
    def value(self):
        return self.val
        
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 20 or h <= 20: 
            p.end()
            return
            
        s = min(w, h)
        r = QRectF((w - s) / 2 + 10, (h - s) / 2 + 10, s-20, s-20)
        
        pen_bg = QPen(self.bg_color, 8)
        pen_bg.setCapStyle(Qt.RoundCap)
        p.setPen(pen_bg)
        p.drawArc(r, 0, 360*16)
        
        pen_fg = QPen(self.color, 8)
        pen_fg.setCapStyle(Qt.RoundCap)
        p.setPen(pen_fg)
        span = int(-self.val * 3.6 * 16)
        p.drawArc(r, 90*16, span)
        
        p.setPen(QColor('#1e293b'))
        font = p.font()
        font.setPointSize(16)
        font.setBold(True)
        p.setFont(font)
        p.drawText(r, Qt.AlignCenter, f"{int(self.val)}%")
        
        if self.title:
            font.setPointSize(8)
            font.setBold(False)
            p.setFont(font)
            tr = QRectF(r.x(), r.y() + r.height() - 25, r.width(), 30)
            p.setPen(QColor('#64748b'))
            p.drawText(tr, Qt.AlignHCenter | Qt.AlignBottom, self.title)
        
        p.end()

class BrainSpatialView(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(180, 200)
        self.bands = {'Alpha':0, 'Beta':0, 'Delta':0, 'Theta':0}
        self.att = 50
        self.med = 50
        
    def set_data(self, att, med, bands):
        self.att = att
        self.med = med
        self.bands = bands
        self.update()
        
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w/2.0, h/2.0
        bw, bh = 100, 140
        
        # Draw brain container outline
        path = QPainterPath()
        r = QRectF(cx-bw/2, cy-bh/2, bw, bh)
        path.addRoundedRect(r, 45, 55)
        
        p.setPen(QPen(QColor('#cbd5e1'), 2))
        p.setBrush(QColor('#f8fafc'))
        p.drawPath(path)
        
        p.drawLine(cx, cy-bh/2+10, cx, cy+bh/2-10) # Longitudinal fissure
        
        colors = {
            'Alpha': QColor('#2980b9'), # Occipital
            'Beta':  QColor('#c0392b'), # Frontal
            'Delta': QColor('#27ae60'), # Central
            'Theta': QColor('#d35400')  # Temporal
        }
        
        total = sum(self.bands.values()) if self.bands else 1
        if total == 0: total = 1
        
        def draw_glow(lx, ly, band_name, scale):
            val = self.bands.get(band_name, 0)
            ratio = val / total
            intensity = min(1.0, ratio * 3.0 * scale) 
            c = QColor(colors[band_name])
            c.setAlphaF(intensity * 0.8)
            rad = 30 + (intensity * 25)
            grad = QRadialGradient(lx, ly, rad)
            grad.setColorAt(0, c)
            c_trans = QColor(c)
            c_trans.setAlpha(0)
            grad.setColorAt(1, c_trans)
            p.setPen(Qt.NoPen)
            p.setBrush(grad)
            p.drawEllipse(QPointF(lx, ly), rad, rad)
            
        # Draw glowing nodes
        draw_glow(cx, cy-bh*0.3, 'Beta', 1.0 + self.att/100.0) # Frontal
        draw_glow(cx, cy+bh*0.3, 'Alpha', 1.0 + self.med/100.0) # Occipital
        draw_glow(cx, cy, 'Delta', 1.0) # Central
        draw_glow(cx-bw*0.3, cy-bh*0.1, 'Theta', 1.0) # Temporal L
        draw_glow(cx+bw*0.3, cy-bh*0.1, 'Theta', 1.0) # Temporal R
        
        p.end()

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('AetherEEG')
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'logo.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumSize(800, 600)  # Prevent pyqtgraph crashing on extremely small window resize
        self.setStyleSheet('background-color: #f8fafc; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;')
        
        self.is_recording = False
        self.recorded_data = []
        self.record_start_time = 0
        
        # Make the native Windows title bar blend with our color scheme
        try:
            import ctypes
            hwnd = int(self.winId())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_CAPTION_COLOR = 35
            # 1. Light mode
            policy = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(policy), ctypes.sizeof(policy))
            # 2. Match #f1f5f9 EXACTLY for Win11 title bar (Format: 0x00bbggrr)
            # R=241(f1) G=245(f5) B=249(f9) -> 0x00F9F5F1
            caption_color = ctypes.c_uint(0x00F9F5F1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption_color), ctypes.sizeof(caption_color))
        except Exception:
            pass
        
        # Window-filling intro overlay
        self.introBox=QWidget(self)
        self.introBox.setGeometry(0, 0, 1000, 600)
        self.introBox.setStyleSheet('background:#f1f5f9;')
        ibox=QVBoxLayout()
        ibox.setContentsMargins(0,0,0,0)
        
        # Centered container for intro content
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)
        
        l1=QLabel('<span style="font-size:28pt; font-weight:bold; color:#0f172a; letter-spacing:1px;">AetherNeuro</span><br><span style="font-size:12pt; color:#64748b; font-weight:500;">SCIENTIFIC ACQUISITION SUITE</span>')
        l1.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(l1)
        
        ifooter=QLabel('by Jcarl Juson')
        ff=QFont('Segoe UI')
        ff.setPointSize(14)
        ff.setWeight(QFont.Medium)
        ifooter.setFont(ff)
        ifooter.setAlignment(Qt.AlignCenter)
        ifooter.setStyleSheet('color:#94a3b8; background:transparent;')
        center_layout.addWidget(ifooter)
        
        ibox.addStretch(1)
        ibox.addWidget(center_widget)
        ibox.addStretch(1)
        self.introBox.setLayout(ibox)
        self.introEffect=QGraphicsOpacityEffect(self.introBox)
        self.introBox.setGraphicsEffect(self.introEffect)
        self.introIn=QPropertyAnimation(self.introEffect,b'opacity',self)
        self.introIn.setDuration(400)
        self.introIn.setStartValue(0.0)
        self.introIn.setEndValue(1.0)
        self.introOut=QPropertyAnimation(self.introEffect,b'opacity',self)
        self.introOut.setDuration(800)
        self.introOut.setStartValue(1.0)
        self.introOut.setEndValue(0.0)
        self.portBox=QComboBox()
        self.baudBox=QComboBox()
        self.baudBox.addItems([str(x) for x in [57600,115200,9600]])
        self.refreshBtn=QPushButton('Refresh')
        self.autoBtn=QPushButton('Auto Detect')
        self.connectBtn=QPushButton('Connect')
        self.disconnectBtn=QPushButton('Disconnect')
        self.simBox=QCheckBox('Simulation')
        self.simBox.setToolTip("<span style='color: white;'>Check this box and click 'Connect' to generate synthetic brainwaves without a headset.</span>")
        self.mouseBox=QCheckBox('Mouse Control')
        self.mouseAdvBtn=QPushButton('Advanced')
        self.gameBtn=QPushButton('Minigame')
        self.droneBtn=QPushButton('Drone Sim')
        self.graphsAdvBtn=QPushButton('Advanced Graphs')
        
        self.recordBtn=QPushButton('⏺ Record EEG')
        self.recordBtn.setObjectName("recordBtn")
        self.recordBtn.setStyleSheet("""
            QPushButton#recordBtn {
                background: #ffffff; color: #ef4444; font-weight: 800; border: 1px solid #fca5a5; padding: 6px 14px;
            }
            QPushButton#recordBtn:hover { background: #fee2e2; border-color: #ef4444; }
            QPushButton#recordBtn[recording="true"] { background: #ef4444; color: #ffffff; border: none; }
        """)
        self.recordBtn.clicked.connect(self.toggle_recording)
        
        self.helpBtn=QPushButton('?')
        self.helpBtn.setFixedWidth(28)
        self.helpBtn.setStyleSheet("""
            QPushButton {
                background: #007aff;
                color: #ffffff;
                font-weight: 800;
                font-size: 16px;
                border-radius: 14px;
                border: none;
                padding: 0;
            }
            QPushButton:hover { background: #006ce6; }
        """)
        self.helpBtn.setToolTip("Mouse Control Tutorial")
        top=QHBoxLayout()
        top.addWidget(QLabel('Port'))
        top.addWidget(self.portBox)
        top.addWidget(QLabel('Baud'))
        top.addWidget(self.baudBox)
        top.addWidget(self.refreshBtn)
        top.addWidget(self.autoBtn)
        top.addWidget(self.connectBtn)
        top.addWidget(self.disconnectBtn)
        top.addWidget(self.simBox)
        top.addWidget(self.mouseBox)
        top.addWidget(self.mouseAdvBtn)
        top.addWidget(self.gameBtn)
        top.addWidget(self.droneBtn)
        top.addWidget(self.graphsAdvBtn)
        top.addWidget(self.recordBtn)
        top.addWidget(self.helpBtn)
        self.rawPlot=pg.PlotWidget()
        self.rawPlot.setBackground('#ffffff')
        self.rawPlot.setStyleSheet("border-radius: 16px; border: 1px solid #e2e8f0;")
        self.rawPlot.showGrid(x=True,y=True, alpha=0.15)
        self.rawPlot.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        self.rawPlot.getAxis('left').setPen('#cbd5e1')
        self.rawPlot.getAxis('left').setTextPen('#64748b')
        self.rawPlot.getAxis('bottom').setPen('#cbd5e1')
        self.rawPlot.getAxis('bottom').setTextPen('#64748b')
        self.rawPlot.setMinimumHeight(140)
        self.rawCurve=self.rawPlot.plot(pen=pg.mkPen('#38bdf8',width=1.8))
        self.rawCurve.setFillLevel(0)
        self.rawCurve.setBrush(pg.mkBrush(QColor(56, 189, 248, 20)))
        self.rawBuf=[0]*1024
        
        self.bandPlot=pg.PlotWidget()
        self.bandPlot.setBackground('#ffffff')
        self.bandPlot.setStyleSheet("border-radius: 16px; border: 1px solid #e2e8f0;")
        self.bandPlot.showGrid(x=True,y=True, alpha=0.15)
        self.bandPlot.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        self.bandPlot.getAxis('left').setPen('#cbd5e1')
        self.bandPlot.getAxis('left').setTextPen('#64748b')
        self.bandPlot.getAxis('bottom').setPen('#cbd5e1')
        self.bandPlot.getAxis('bottom').setTextPen('#64748b')
        self.bandPlot.setMinimumHeight(200)
        
        from PySide6.QtWidgets import QGridLayout
        gbox=QGridLayout()
        self.plots={}
        self.pw_dict={}
        
        clinical_colors = {
            'Alpha': QColor('#2980b9'),  # Medical Blue
            'Beta':  QColor('#c0392b'),  # Clinical Red
            'Delta': QColor('#27ae60'),  # Emerald Green
            'Theta': QColor('#d35400')   # Deep Orange
        }
        
        positions = [(0,0), (0,1), (1,0), (1,1)]
        band_names = ['Alpha','Beta','Delta','Theta']
        
        for idx, b in enumerate(band_names):
            pw = pg.PlotWidget(title=f'<span style="color: #475569; font-size: 11pt; font-weight: bold;">{b} Waves</span>')
            pw.setBackground('#ffffff')
            pw.setStyleSheet("border-radius: 16px; border: 1px solid #e2e8f0;")
            pw.getViewBox().setMouseMode(pg.ViewBox.RectMode)
            pw.getViewBox().autoRange()
            pw.setMenuEnabled(False)
            
            # Allow plots to cleanly compress down up to 120px to allow OS window scaling
            pw.setMinimumHeight(120)
            
            # Distinct grid for data reading
            pw.showGrid(x=True, y=True, alpha=0.15)
            pw.getAxis('left').setPen('#cbd5e1')
            pw.getAxis('left').setTextPen('#64748b')
            pw.getAxis('bottom').setPen('#cbd5e1')
            pw.getAxis('bottom').setTextPen('#64748b')

            c = clinical_colors[b]
            pen = pg.mkPen(c, width=1.8)
            
            # Sharp minimal fill for scientific aesthetics
            brush = QBrush(QColor(c.red(), c.green(), c.blue(), 20))
            
            curve = pw.plot(pen=pen, brush=brush, fillLevel=0)
            self.plots[b] = curve
            self.pw_dict[b] = pw
            
            row, col = positions[idx]
            gbox.addWidget(pw, row, col)
        
        self.bandNames=['delta','theta','low_alpha','high_alpha','low_beta','high_beta','low_gamma','mid_gamma']
        self.bandLegend=self.bandPlot.addLegend(offset=(10, 10))
        # Make legend items larger, bandPlot height prevents cutoff
        self.bandLegend.setLabelTextSize("8pt")
        self.bandLegend.setScale(0.8)
        self.bandColors={
            'delta':'#0ea5e9',
            'theta':'#14b8a6',
            'low_alpha':'#10b981',
            'high_alpha':'#6ee7b7',
            'low_beta':'#f59e0b',
            'high_beta':'#fbbf24',
            'low_gamma':'#a78bfa',
            'mid_gamma':'#c4b5fd'
        }
        self.bandCurves={}
        self.bandSeries={}
        for n in self.bandNames:
            pen=pg.mkPen(self.bandColors[n], width=2)
            curve=self.bandPlot.plot(pen=pen)
            curve.setFillLevel(0)
            c_fill = QColor(self.bandColors[n])
            c_fill.setAlpha(60)
            curve.setBrush(pg.mkBrush(c_fill))
            self.bandCurves[n]=curve
            self.bandSeries[n]=[]
            self.bandLegend.addItem(curve, n)
        self.attBar=CircularRingGauge('#3b82f6', 'ATTENTION')
        self.medBar=CircularRingGauge('#8b5cf6', 'MEDITATION')
        self.brainView=BrainSpatialView()
        
        mbox=QHBoxLayout()
        
        # -- Scrollable plot area so fullscreen doesn't crush plots --
        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setFrameShape(QScrollArea.NoFrame)
        scrollArea.setStyleSheet('QScrollArea { background: transparent; border: none; } QScrollBar:vertical { width: 8px; background: #f1f5f9; } QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; } QScrollBar::handle:vertical:hover { background: #94a3b8; }')
        
        scrollContent = QWidget()
        scrollContent.setStyleSheet('background: transparent;')
        v=QVBoxLayout(scrollContent)
        v.setContentsMargins(0, 0, 4, 0)
        v.addLayout(top)
        v.addWidget(QLabel('Raw EEG'))
        v.addWidget(self.rawPlot, 1)
        v.addWidget(QLabel('Waveforms'))
        v.addLayout(gbox, 2)
        v.addWidget(QLabel('Spectral Power'))
        v.addWidget(self.bandPlot, 1)
        scrollArea.setWidget(scrollContent)
        mbox.addWidget(scrollArea)
        
        side=QVBoxLayout()
        self.sigLabel = QLabel('Signal: Waiting...')
        self.sigLabel.setStyleSheet('color:#94a3b8; font-weight:bold; font-size:12px;')
        self.sigLabel.setAlignment(Qt.AlignCenter)
        side.addWidget(self.sigLabel)
        
        brainLabel = QLabel('Spatial Brain Mapping')
        brainLabel.setStyleSheet('color:#64748b; font-weight:bold;')
        brainLabel.setAlignment(Qt.AlignCenter)
        side.addWidget(brainLabel)
        side.addWidget(self.brainView)
        
        dialLayout = QHBoxLayout()
        
        # Attention container
        att_v = QVBoxLayout()
        self.attChip=QLabel('Neutral')
        self.attChip.setAlignment(Qt.AlignCenter)
        self.attChip.setFixedHeight(20)
        self.attChip.setStyleSheet('color:#2563eb; background:#eff6ff; border:1px solid #bfdbfe; border-radius:10px; padding:2px 8px; font-size:11px;')
        att_v.addWidget(self.attBar)
        att_v.addWidget(self.attChip)
        dialLayout.addLayout(att_v)
        
        # Meditation container
        med_v = QVBoxLayout()
        self.medChip=QLabel('Neutral')
        self.medChip.setAlignment(Qt.AlignCenter)
        self.medChip.setFixedHeight(20)
        self.medChip.setStyleSheet('color:#7c3aed; background:#f5f3ff; border:1px solid #ddd6fe; border-radius:10px; padding:2px 8px; font-size:11px;')
        med_v.addWidget(self.medBar)
        med_v.addWidget(self.medChip)
        dialLayout.addLayout(med_v)
        
        side.addLayout(dialLayout)
        
        self.metricCard=QWidget()
        self.metricCard.setObjectName("glassCard")
        self.metricCard.setStyleSheet("""
            QWidget#glassCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 16px;
            }
        """)
        
        # Add a subtle Apple-like drop shadow to the sidebar card
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(self.metricCard)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 4)
        self.metricCard.setGraphicsEffect(shadow)
        self.metricCard.setMinimumWidth(260)
        self.metricCard.setMaximumWidth(320)
        self.metricCard.setLayout(side)
        mbox.addWidget(self.metricCard)
        self.setLayout(mbox)
        self.worker=None
        self.thread=None
        self.timer=QTimer()
        self.timer.timeout.connect(self.tick)
        self.refreshBtn.clicked.connect(self.refresh_ports)
        self.autoBtn.clicked.connect(self.auto_detect)
        self.connectBtn.clicked.connect(self.connect)
        self.disconnectBtn.clicked.connect(self.disconnect)
        self.simBox.stateChanged.connect(self.on_sim)
        self.mouseBox.stateChanged.connect(self.on_mouse_box)
        self.mouseAdvBtn.clicked.connect(self.open_mouse_settings)
        self.helpBtn.clicked.connect(self.open_help)
        self.gameBtn.clicked.connect(self.open_game)
        self.droneBtn.clicked.connect(self.open_drone_sim)
        self.graphsAdvBtn.clicked.connect(self.open_graphs_adv)
        self.mouse=MouseController()
        try:
            self.mouse.tripleBlink.connect(self._toggle_mouse_box)
        except Exception:
            pass
        self.lastBands={}
        self.refresh_ports()
        self.introBox.raise_()
        QTimer.singleShot(1200, self._intro_fade)
    def refresh_ports(self):
        self.portBox.clear()
        self.portBox.addItems(list_ports())
    def auto_detect(self):
        p,b=detect_port_baud()
        if p:
            i=self.portBox.findText(p)
            if i==-1:
                self.portBox.addItem(p)
                i=self.portBox.findText(p)
            self.portBox.setCurrentIndex(i)
            bi=self.baudBox.findText(str(b))
            if bi==-1:
                self.baudBox.addItem(str(b))
                bi=self.baudBox.findText(str(b))
            self.baudBox.setCurrentIndex(bi)
        else:
            self.baudBox.setCurrentIndex(0)
    def connect(self):
        if self.simBox.isChecked():
            self.timer.start(33)
            return
        p=self.portBox.currentText()
        b=int(self.baudBox.currentText())
        if not p:
            return
        # Guard against overlapping connections destroying QThread prematurely
        if self.thread and self.thread.isRunning():
            self.disconnect()
            
        self.thread=QThread()
        self.worker=SerialWorker(p,b)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start)
        self.thread.started.connect(self.worker.loop)
        self.worker.status.connect(self.on_status)
        self.worker.data.connect(self.on_data)
        self.thread.start()
    def disconnect(self):
        self.timer.stop()
        if self.worker:
            self.worker.stop()
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.worker=None
        self.thread=None
        self.mouse.stop()
    def on_status(self,s):
        pass
        
    def toggle_recording(self):
        if not self.is_recording:
            # Start recording
            self.is_recording = True
            self.recorded_data = []
            self.record_start_time = time.time()
            self.recordBtn.setText("⏹ Stop Recording")
            self.recordBtn.setProperty("recording", "true")
            self.recordBtn.style().unpolish(self.recordBtn)
            self.recordBtn.style().polish(self.recordBtn)
        else:
            # Stop recording
            self.is_recording = False
            self.recordBtn.setText("⏺ Record EEG")
            self.recordBtn.setProperty("recording", "false")
            self.recordBtn.style().unpolish(self.recordBtn)
            self.recordBtn.style().polish(self.recordBtn)
            
            # Open Review Dialog
            if len(self.recorded_data) > 0:
                dlg = RecordingReviewDialog(self, self.recorded_data)
                dlg.exec()
            
    def on_data(self,d):
        if self.is_recording:
            t = time.time() - self.record_start_time
            raw = d.get('raw_wave', 0)
            b = d.get('bands', {})
            att = d.get('attention', 0)
            med = d.get('meditation', 0)
            row = (t, raw, att, med, b.get('delta',0), b.get('theta',0), b.get('low_alpha',0), b.get('high_alpha',0), b.get('low_beta',0), b.get('high_beta',0), b.get('low_gamma',0), b.get('mid_gamma',0))
            self.recorded_data.append(row)
            
        if 'poor_signal' in d:
            sig = d['poor_signal']
            if sig == 0:
                self.sigLabel.setText("Signal: Excellent")
                self.sigLabel.setStyleSheet("color: #10b981; font-weight: bold; font-size:12px;")
            elif sig < 50:
                self.sigLabel.setText(f"Signal: Good ({sig})")
                self.sigLabel.setStyleSheet("color: #f59e0b; font-weight: bold; font-size:12px;")
            else:
                self.sigLabel.setText(f"Signal: Poor - Adjust Headset ({sig})")
                self.sigLabel.setStyleSheet("color: #ef4444; font-weight: bold; font-size:12px;")
                
        if 'raw_wave' in d:
            self.rawBuf=self.rawBuf[1:]+[d['raw_wave']]
            self.rawCurve.setData(self.rawBuf)
        if 'bands' in d:
            b=d['bands']
            total=sum(b.values()) if b else 0
            for i,n in enumerate(self.bandNames):
                v=b.get(n,0)
                r=(v/total) if total>0 else 0
                s=self.bandSeries.get(n,[])
                if len(s)>300:
                    s=s[1:]+[r]
                else:
                    s=s+[r]
                self.bandSeries[n]=s
                self.bandCurves[n].setData(s)
            self.lastBands=b
            
            # Sub-waveform and BrainView Data Aggregation
            clinical_mapping = {
                'Alpha': ['low_alpha', 'high_alpha'],
                'Beta': ['low_beta', 'high_beta'],
                'Delta': ['delta'],
                'Theta': ['theta']
            }
            if not hasattr(self, 'subBandSeries'):
                self.subBandSeries = {'Alpha': [], 'Beta': [], 'Delta': [], 'Theta': []}
            self.lastClinicalBands = {}
            for cb, sub_keys in clinical_mapping.items():
                val = sum(b.get(k, 0) for k in sub_keys)
                self.lastClinicalBands[cb] = val
                r = (val/total) if total>0 else 0
                s = self.subBandSeries[cb]
                if len(s)>300:
                    s = s[1:] + [r]
                else:
                    s = s + [r]
                self.subBandSeries[cb] = s
            # update plots
            if hasattr(self, 'plots'):
                for cb in self.plots:
                    self.plots[cb].setData(self.subBandSeries.get(cb, []))
        if 'attention' in d:
            self.attBar.setValue(d['attention'])
        if 'meditation' in d:
            self.medBar.setValue(d['meditation'])
        self._update_metric_chips()
        if getattr(self,'mouseBox',None) and self.mouseBox.isChecked():
            self.mouse.feed(d)
    def on_sim(self):
        if self.simBox.isChecked():
            self.disconnect()
    def on_mouse_box(self):
        if self.mouseBox.isChecked():
            self.mouse.start()
        else:
            self.mouse.stop()
    def _toggle_mouse_box(self):
        self.mouseBox.setChecked(not self.mouseBox.isChecked())
    def open_mouse_settings(self):
        self.mouse.settings(self)
    def open_help(self):
        d=QDialog(self)
        d.setWindowTitle('Mouse Control — Tutorial')
        v=QVBoxLayout()
        t1=QLabel('Attention/Meditation Axes')
        t1.setStyleSheet('font-size:16px; font-weight:600;')
        v.addWidget(t1)
        p1=QLabel('Up: increase Attention (focus on a target, mental arithmetic)\nDown: decrease Attention (relax, defocus eyes)\nRight: increase Meditation (slow breathing, calm body)\nLeft: decrease Meditation (engage, disrupt calm)')
        p1.setWordWrap(True)
        v.addWidget(p1)
        t2=QLabel('Bands Axes')
        t2.setStyleSheet('font-size:16px; font-weight:600;')
        v.addWidget(t2)
        p2=QLabel('Up: raise High Beta (intense focus, fast mental math)\nDown: raise Low Alpha (eyes closed relaxation)\nRight: raise Low Gamma (problem solving, multi-step tasks)\nLeft: raise Theta (memory recall, drowsy states)')
        p2.setWordWrap(True)
        v.addWidget(p2)
        t3=QLabel('Clicks and Blink Control')
        t3.setStyleSheet('font-size:16px; font-weight:600;')
        v.addWidget(t3)
        p3=QLabel('Blink: if Click Mode is "Blink", a blink above threshold clicks.\nBlink Switch+Triple: single blink toggles movement on/off; triple blink clicks.\nTune in Advanced: set Blink Threshold and Blink Window for your signal.')
        p3.setWordWrap(True)
        v.addWidget(p3)
        t4=QLabel('Tips')
        t4.setStyleSheet('font-size:16px; font-weight:600;')
        v.addWidget(t4)
        p4=QLabel('Start with Simulation enabled to learn mappings.\nUse Smoothing and Deadzone in Advanced to stabilize motion.\nFind your baseline (around 50) for Attention/Meditation; small changes nudge direction.')
        p4.setWordWrap(True)
        v.addWidget(p4)
        d.setLayout(v)
        d.resize(520, 420)
        d.exec()
    def open_game(self):
        d=MouseMinigame(self)
        d.exec()
    def open_drone_sim(self):
        d=DroneSim(self)
        d.exec()
    def open_graphs_adv(self):
        d=AdvancedGraphsDialog(self)
        d.exec()
    def tick(self):
        t=len(self.rawBuf)
        v=int(2000*math.sin(random.random()*math.pi))
        self.rawBuf=self.rawBuf[1:]+[v]
        self.rawCurve.setData(self.rawBuf)
        h=[random.randint(1000,800000) for _ in self.bandNames]
        b={n: h[i] for i,n in enumerate(self.bandNames)}
        total=sum(b.values())
        for i,n in enumerate(self.bandNames):
            v=b[n]
            r=(v/total) if total>0 else 0
            s=self.bandSeries.get(n,[])
            if len(s)>300:
                s=s[1:]+[r]
            else:
                s=s+[r]
            self.bandSeries[n]=s
            self.bandCurves[n].setData(s)
        self.lastBands=b
        
        # Sub-waveform and BrainView Data Aggregation
        clinical_mapping = {
            'Alpha': ['low_alpha', 'high_alpha'],
            'Beta': ['low_beta', 'high_beta'],
            'Delta': ['delta'],
            'Theta': ['theta']
        }
        if not hasattr(self, 'subBandSeries'):
            self.subBandSeries = {'Alpha': [], 'Beta': [], 'Delta': [], 'Theta': []}
        self.lastClinicalBands = {}
        for cb, sub_keys in clinical_mapping.items():
            val = sum(b.get(k, 0) for k in sub_keys)
            self.lastClinicalBands[cb] = val
            r = (val/total) if total>0 else 0
            s = self.subBandSeries[cb]
            if len(s)>300:
                s = s[1:] + [r]
            else:
                s = s + [r]
            self.subBandSeries[cb] = s
        if hasattr(self, 'plots'):
            for cb in self.plots:
                self.plots[cb].setData(self.subBandSeries.get(cb, []))
                
        self.attBar.setValue(random.randint(0,100))
        self.medBar.setValue(random.randint(0,100))
        self.sigLabel.setText("Signal: Simulated")
        self.sigLabel.setStyleSheet("color: #8b5cf6; font-weight: bold; font-size:12px;")
        self._update_metric_chips()
        if self.mouseBox.isChecked():
            self.mouse.feed({
                'attention': self.attBar.value(),
                'meditation': self.medBar.value(),
                'bands': {n: h[i] for i,n in enumerate(self.bandNames)},
                'raw_wave': self.rawBuf[-1] if len(self.rawBuf)>0 else 0
            })
    def _intro_fade(self):
        self.introBox.raise_()
        self.introIn.finished.connect(lambda: QTimer.singleShot(700,self.introOut.start))
        self.introOut.finished.connect(self._intro_done)
        self.introIn.start()
    def _intro_done(self):
        self.introBox.hide()
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, 'introBox') and self.introBox.isVisible():
            self.introBox.setGeometry(0, 0, self.width(), self.height())

    def _update_metric_chips(self):
        a=self.attBar.value()
        m=self.medBar.value()
        
        # Drive the Brain View!
        self.brainView.set_data(a, m, getattr(self, 'lastClinicalBands', {}))
        
        def classify(v):
            if v<45: return ('Low', '#3b82f6', '#eff6ff', '#bfdbfe')
            if v>55: return ('High', '#3b82f6', '#eff6ff', '#bfdbfe')
            return ('Neutral', '#3b82f6', '#eff6ff', '#bfdbfe')
        t,c,bg,bd = classify(a)
        self.attChip.setText(t)
        self.attChip.setStyleSheet(f'color:{c}; background:{bg}; border:1px solid {bd}; border-radius:10px; padding:2px 8px; font-size:11px;')
        
        def classify2(v):
            if v<45: return ('Low', '#8b5cf6', '#f5f3ff', '#ddd6fe')
            if v>55: return ('High', '#8b5cf6', '#f5f3ff', '#ddd6fe')
            return ('Neutral', '#8b5cf6', '#f5f3ff', '#ddd6fe')
        t2,c2,bg2,bd2=classify2(m)
        self.medChip.setText(t2)
        self.medChip.setStyleSheet(f'color:{c2}; background:{bg2}; border:1px solid {bd2}; border-radius:10px; padding:2px 8px; font-size:11px;')

class MouseMinigame(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Mouse Minigame')
        self.resize(900, 600)
        self.setStyleSheet("background-color: #0b1220;")
        
        self.score = -1
        self.scoreLabel = QLabel(self)
        self.scoreLabel.setStyleSheet('background:transparent; color:#38bdf8; font-size: 32px; font-weight: bold;')
        self.scoreLabel.move(20, 50)
        self.scoreLabel.resize(300, 40)

        self.box=QLabel(self)
        self.box.setFixedSize(80,80)
        self.box.setStyleSheet('background:#10b981; border-radius:8px;')
        self.hint=QLabel('Press Esc to exit  •  F11 for fullscreen', self)
        self.hint.setStyleSheet('background:rgba(17,24,39,0.7); color:#ffffff; padding:4px 8px; border-radius:6px; font-size: 16px;')
        self.hint.move(20, 10)
        self.hint.resize(400, 30)
        self.timer=QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._apply_brain_cursor()
        # Defer teleport so the window geometry is valid
        QTimer.singleShot(100, self._teleport)
        self.setFocus()
    def _teleport(self):
        w=self.width()
        h=self.height()
        bw=self.box.width()
        bh=self.box.height()
        x=random.randint(20,max(20,w-bw-20))
        y=random.randint(100,max(100,h-bh-20))
        self.box.move(x,y)
        if hasattr(self, 'score'):
            self.score += 1
            self.scoreLabel.setText(f'Score: {self.score}')
    def _tick(self):
        pos=QCursor.pos()
        local=self.mapFromGlobal(pos)
        r=self.box.geometry()
        if hasattr(self, '_cursor_pm') and hasattr(self, '_hotspot'):
            cr=QRect(local.x()-self._hotspot[0], local.y()-self._hotspot[1], self._cursor_pm.width(), self._cursor_pm.height())
            inter=r.intersected(cr)
            area=inter.width()*inter.height()
            need=int(min(r.width()*r.height(), cr.width()*cr.height())*0.10)
            if area>=need:
                self._teleport()
        else:
            if r.contains(local):
                self._teleport()
    def _apply_brain_cursor(self):
        pm=QPixmap(32,32)
        pm.fill(Qt.transparent)
        p=QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        # brain base
        p.setBrush(QBrush(QColor('#f472b6')))
        p.setPen(QPen(QColor('#be185d'), 2))
        p.drawRoundedRect(4,6,24,20,8,8)
        # sulci lines
        p.setPen(QPen(QColor('#9d174d'), 2))
        p.drawArc(6,8,8,8,30*16, 120*16)
        p.drawArc(14,8,8,8,30*16, 120*16)
        p.drawArc(10,14,12,8,210*16, 120*16)
        p.end()
        self._cursor_pm=pm
        self._hotspot=(0,0)
        self.setCursor(QCursor(pm, self._hotspot[0], self._hotspot[1]))
    def closeEvent(self, e):
        self.unsetCursor()
        super().closeEvent(e)
    def keyPressEvent(self, e):
        if e.key()==Qt.Key_Escape:
            if self.isFullScreen():
                self._exit_fullscreen()
            else:
                self.close()
            return
        if e.key()==Qt.Key_F11:
            if self.isFullScreen():
                self._exit_fullscreen()
            else:
                self._enter_fullscreen()
            return
        super().keyPressEvent(e)

    def _enter_fullscreen(self):
        # On Windows, QDialog with a parent crashes on showFullScreen().
        # Detach from parent by switching to Qt.Window flags first.
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.showFullScreen()
        self.setFocus()
        # Re-teleport after resize so the box lands in valid bounds
        QTimer.singleShot(200, self._teleport)

    def _exit_fullscreen(self):
        self.showNormal()
        self.setFocus()
        QTimer.singleShot(150, self._teleport)

class AdvancedGraphsDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app=app
        self.setWindowTitle('Advanced Graphs')
        self.resize(900,600)
        self.rawPlot=pg.PlotWidget()
        self.rawPlot.setBackground('#0b1220')
        self.rawPlot.showGrid(x=True,y=True, alpha=0.3)
        self.rawPlot.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        self.filteredCurve=self.rawPlot.plot(pen=pg.mkPen('#ef4444',width=2))
        self.filteredCurve.setFillLevel(0)
        self.filteredCurve.setBrush(pg.mkBrush(QColor(239, 68, 68, 50)))
        self.filtered=[]
        self.bandsPlot=pg.PlotWidget()
        self.bandsPlot.setBackground('#0b1220')
        self.bandsPlot.showGrid(x=True,y=True, alpha=0.3)
        self.bandsPlot.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        self._curves={}
        self._series={}
        self._colors={
            'delta':'#0ea5e9',
            'theta':'#14b8a6',
            'low_alpha':'#10b981',
            'high_alpha':'#6ee7b7',
            'low_beta':'#f59e0b',
            'high_beta':'#fbbf24',
            'low_gamma':'#a78bfa',
            'mid_gamma':'#c4b5fd'
        }
        for n in self.app.bandNames:
            c=self._colors[n]
            self._curves[n]=self.bandsPlot.plot(pen=pg.mkPen(c,width=1))
            self._series[n]=[]
        v=QVBoxLayout()
        v.addWidget(QLabel('Filtered Raw'))
        v.addWidget(self.rawPlot)
        v.addWidget(QLabel('Bands (time series)'))
        v.addWidget(self.bandsPlot)
        self.setLayout(v)
        self._ema_b=0.0
        self._ema_f=0.0
        self.timer=QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
    def _tick(self):
        if len(self.app.rawBuf)>0:
            x=self.app.rawBuf[-1]
            self._ema_b=self._ema_b*0.99+0.01*x
            y=x-self._ema_b
            self._ema_f=self._ema_f*0.8+0.2*y
            if len(self.filtered)>1024:
                self.filtered=self.filtered[1:]+[self._ema_f]
            else:
                self.filtered.append(self._ema_f)
            self.filteredCurve.setData(self.filtered)
        b=self.app.lastBands or {}
        total=sum(b.values()) if b else 0
        for n in self.app.bandNames:
            v=b.get(n,0)
            r=(v/total) if total>0 else 0
            s=self._series.get(n,[])
            if len(s)>300:
                s=s[1:]+[r]
            else:
                s=s+[r]
            self._series[n]=s
            self._curves[n].setData(s)

class DroneSim(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app=app
        self.setWindowTitle('Drone Simulation')
        self.resize(800,520)
        self.posX=0.0
        self.posY=0.0
        self.posZ=0.0
        self.vx=0.0
        self.vf=0.4
        self.yaw=30.0
        self.pitch=-15.0
        self.dist=260.0
        self.drag=False
        self._last=None
        self.indicator=QLabel('Hover', self)
        self.indicator.setStyleSheet('background:rgba(17,24,39,0.85); color:#ffffff; padding:4px 10px; border-bottom-left-radius:8px; border-bottom-right-radius:8px; font-weight:600;')
        self.indicator.setAlignment(Qt.AlignCenter)
        self.indicator.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hint=QLabel('Esc to exit • Up: Attention • Left/Right: Meditation', self)
        self.hint.setStyleSheet('background:rgba(17,24,39,0.7); color:#ffffff; padding:4px 8px; border-radius:6px;')
        self.hint.move(10,10)
        self.hint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.actionLabel=QLabel('Drone Hovering', self)
        self.actionLabel.setStyleSheet('background:rgba(31,41,55,0.9); color:#ffffff; padding:6px 12px; border-radius:10px; font-weight:700;')
        self.actionLabel.setAlignment(Qt.AlignCenter)
        self.actionLabel.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.upLabel=QLabel('Level', self)
        self.lrLabel=QLabel('Center', self)
        self.fwLabel=QLabel('Stopped', self)
        for L in (self.upLabel,self.lrLabel,self.fwLabel):
            L.setStyleSheet('background:rgba(31,41,55,0.9); color:#ffffff; padding:4px 10px; border-radius:8px; font-weight:600;')
            L.setAlignment(Qt.AlignCenter)
            L.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.timer=QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.setFocus()
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        self.spin=0.0
        self.t=0.0
        self._broll=0.0
        self._bpitch=0.0
        self.heading=0.0
        self.world_x=0.0
        self.world_z=0.0
        self.floor_top=120.0
        self.floor_bottom=-20.0
        self.bound_x=0.4
        self.bound_y=0.6
    def _norm_band(self,k):
        b=self.app.lastBands or {}
        total=sum(b.values()) if b else 0
        v=b.get(k)
        if not v or total<=0:
            return 0.0
        return v/total
    def _tick(self):
        has_signal=(getattr(self.app,'simBox',None) and self.app.simBox.isChecked()) or (self.app.thread is not None)
        att=self.app.attBar.value() if has_signal else 50
        med=self.app.medBar.value() if has_signal else 50
        ascend=0.0
        
        if not has_signal:
            self.vx=0.0
            self.vf=0.0
            ascend=0.0
        else:
            if att>60:
                ascend=0.6
            elif att<40:
                ascend=-0.6
            self.vx=(med-50)/50.0
            self.vf=0.4
            
        self.posZ+=ascend
        self.posZ=max(self.floor_bottom,min(self.floor_top,self.posZ))
        self.vx=max(-1.0,min(1.0,self.vx))
        self.posX+=self.vx*2.0
        self.posY+=self.vf*2.0
        self.heading+=self.vx*2.0
        if self.heading>180.0:
            self.heading-=360.0
        if self.heading<-180.0:
            self.heading+=360.0
        hx=math.sin(self.heading*math.pi/180.0)
        hz=math.cos(self.heading*math.pi/180.0)
        self.world_x+=hx*self.vf*2.0
        self.world_z+=hz*self.vf*2.0
        w=self.width()
        h=self.height()
        self.posX=max(-w*self.bound_x,min(w*self.bound_x,self.posX))
        self.posY=max(0.0,min(h*self.bound_y,self.posY))
        self.world_x=max(-w*self.bound_x*2.0,min(w*self.bound_x*2.0,self.world_x))
        self.world_z=max(-h*self.bound_y*2.0,min(h*self.bound_y*2.0,self.world_z))
        self.spin=(self.spin + (self.vf*10.0 + abs(self.vx)*8.0 + abs(ascend)*8.0))%360.0
        self._broll=self.vx*0.3
        self._bpitch=ascend*0.25
        mv='Level'
        if ascend>0:
            mv='Up'
        elif ascend<0:
            mv='Down'
        lr='Center'
        if self.vx>0.05:
            lr='Right'
        elif self.vx<-0.05:
            lr='Left'
        self.indicator.setText(f'{mv} • {lr} • Forward')
        self.indicator.resize(self.width(), 32)
        self.indicator.move(0,0)
        phrase=[]
        if mv=='Up':
            phrase.append('Drone flying up')
        elif mv=='Down':
            phrase.append('Drone descending')
        else:
            phrase.append('Drone hovering')
        if lr=='Left':
            phrase.append('moving left')
        elif lr=='Right':
            phrase.append('moving right')
        if self.vf>0.0:
            phrase.append('forward')
        self.actionLabel.setText(', '.join(phrase))
        self.actionLabel.resize(self.width()//2, 30)
        self.actionLabel.move(self.width()//2 - self.actionLabel.width()//2, 2)
        self.upLabel.setText(mv)
        self.lrLabel.setText(lr)
        self.fwLabel.setText('Forward' if self.vf>0.0 else 'Stopped')
        c_up='#22c55e' if mv!='Level' else '#6b7280'
        c_lr='#22c55e' if lr!='Center' else '#6b7280'
        c_fw='#22c55e' if self.vf>0.0 else '#ef4444'
        self.upLabel.setStyleSheet(f'background:{c_up}; color:#0b1220; padding:4px 10px; border-radius:8px; font-weight:700;')
        self.lrLabel.setStyleSheet(f'background:{c_lr}; color:#0b1220; padding:4px 10px; border-radius:8px; font-weight:700;')
        self.fwLabel.setStyleSheet(f'background:{c_fw}; color:#0b1220; padding:4px 10px; border-radius:8px; font-weight:700;')
        tw=self.width()
        self.upLabel.resize(tw//3-8, 28)
        self.lrLabel.resize(tw//3-8, 28)
        self.fwLabel.resize(tw//3-8, 28)
        self.upLabel.move(6, 34)
        self.lrLabel.move(6+tw//3, 34)
        self.fwLabel.move(6+2*(tw//3), 34)
        self.update()
    def keyPressEvent(self,e):
        if e.key()==Qt.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
                self.setFocus()
            else:
                self.close()
            return
        if e.key()==Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
                self.setFocus()
            else:
                # Detach from parent before going fullscreen on Windows
                self.setWindowFlags(self.windowFlags() | Qt.Window)
                self.showFullScreen()
                self.setFocus()
            return
        super().keyPressEvent(e)
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:
            self.drag=True
            self._last=e.pos()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(e)
    def mouseMoveEvent(self,e):
        if self.drag and self._last is not None:
            d=e.pos()-self._last
            self._last=e.pos()
            self.yaw+=d.x()*0.4
            self.pitch+=-d.y()*0.3
            if self.pitch<-80:
                self.pitch=-80
            if self.pitch>80:
                self.pitch=80
            self.update()
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self,e):
        if e.button()==Qt.LeftButton:
            self.drag=False
            self._last=None
            self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(e)
    def paintEvent(self, e):
        p=QPainter(self)
        p.fillRect(self.rect(), QColor('#0b1220'))
        p.setPen(QPen(QColor('#13223a'),1))
        cx=self.width()//2
        cy=self.height()//2+20-int(self.posZ*0.8)
        yaw=self.yaw*math.pi/180.0
        pitch=self.pitch*math.pi/180.0
        def rot(x,y,z):
            sy=math.sin(yaw); cy_=math.cos(yaw)
            sp=math.sin(pitch); cp=math.cos(pitch)
            x1= x*cy_ + z*sy
            z1=-x*sy + z*cy_
            y2= y*cp - z1*sp
            z2= y*sp + z1*cp
            return x1,y2,z2
        br=self._broll
        bp=self._bpitch
        def tilt_local(x,y,z):
            hy=math.sin(self.heading*math.pi/180.0)
            chy=math.cos(self.heading*math.pi/180.0)
            x0= x*chy + z*hy
            z0=-x*hy + z*chy
            cbr=math.cos(br); sbr=math.sin(br)
            x1=x0*cbr + y*sbr
            y1=-x0*sbr + y*cbr
            cbp=math.cos(bp); sbp=math.sin(bp)
            y2=y1*cbp + z*sbp
            z2=-y1*sbp + z0*cbp
            return x1,y2,z2
        def proj(x,y,z):
            z+=self.dist
            if z<10: z=10
            s=self.dist/z
            return int(cx+x*s), int(cy-y*s)
        p.setPen(QPen(QColor('#1f2937'),1))
        rng=range(-360,361,60)
        y_floor=-self.posZ-40
        offx=-self.world_x
        offz=-self.world_z
        for x in rng:
            x1,y1,z1=rot(x+offx,y_floor,-360+offz)
            x2,y2,z2=rot(x+offx,y_floor, 360+offz)
            p.drawLine(*proj(x1,y1,z1), *proj(x2,y2,z2))
        for z in rng:
            x1,y1,z1=rot(-360+offx,y_floor,z+offz)
            x2,y2,z2=rot( 360+offx,y_floor,z+offz)
            p.drawLine(*proj(x1,y1,z1), *proj(x2,y2,z2))
        wx=0.0
        wy=0.0
        wz=0.0
        a=36; b=20; c=14
        verts=[(-a,-b,-c),(a,-b,-c),(a,b,-c),(-a,b,-c),(-a,-b,c),(a,-b,c),(a,b,c),(-a,b,c)]
        verts=[rot(*tilt_local(x+wx,y-wy,z+wz)) for (x,y,z) in verts]
        pts=[proj(x,y,z) for (x,y,z) in verts]
        qpts=[QPoint(px,py) for (px,py) in pts]
        p.setPen(QPen(QColor('#93c5fd'),2))
        p.setBrush(QBrush(QColor('#60a5fa')))
        p.drawPolygon(QPolygon([qpts[0],qpts[1],qpts[2],qpts[3]]))
        p.setPen(QPen(QColor('#3b82f6'),2))
        p.setBrush(QBrush(QColor('#3b82f6')))
        p.drawPolygon(QPolygon([qpts[4],qpts[5],qpts[6],qpts[7]]))
        L=90
        motors=[( L,0, L),( L,0,-L),(-L,0, L),(-L,0,-L)]
        motors=[rot(*tilt_local(x+wx, -wy, z+wz)) for (x,_,z) in [( L,0, L),( L,0,-L),(-L,0, L),(-L,0,-L)]]
        mpts=[proj(x,y,z) for (x,y,z) in motors]
        p.setPen(QPen(QColor('#10b981'),4))
        for (mx, mz) in [( L,  L),( L,-L),(-L, L),(-L,-L)]:
            x1,y1,z1=rot(*tilt_local(0.0, 0.0, 0.0))
            x2,y2,z2=rot(*tilt_local(mx, 0.0, mz))
            p.drawLine(proj(x1,y1,z1)[0], proj(x1,y1,z1)[1], proj(x2,y2,z2)[0], proj(x2,y2,z2)[1])
        p.setBrush(QBrush(QColor('#0f766e')))
        p.setPen(QPen(QColor('#064e3b'),2))
        for (px,py) in mpts:
            p.drawEllipse(QPoint(px,py),12,6)
        p.setPen(QPen(QColor('#22d3ee'),2))
        for i,(px,py) in enumerate(mpts):
            ang=(self.spin + i*30)*math.pi/180.0
            p.drawLine(px,py, int(px+math.cos(ang)*12), int(py+math.sin(ang)*6))
        nx,ny,nz=rot(*tilt_local(0.0, 0.0, L+34))
        npx,npy=proj(nx,ny,nz)
        top_mid=((qpts[0].x()+qpts[1].x())//2, (qpts[0].y()+qpts[1].y())//2)
        bot_mid=((qpts[3].x()+qpts[2].x())//2, (qpts[3].y()+qpts[2].y())//2)
        p.setPen(QPen(QColor('#f59e0b'),2))
        p.setBrush(QBrush(QColor('#f59e0b')))
        p.drawPolygon(QPolygon([QPoint(npx,npy), QPoint(*top_mid), QPoint(*bot_mid)]))
        gx,gy,gz=rot(*tilt_local(0.0, 0.0, L+20))
        gp=proj(gx,gy,gz)
        p.setBrush(QBrush(QColor('#fb923c')))
        p.drawRect(gp[0]-6, gp[1]-4, 12, 8)
        sx,sy,sz=rot(0.0,y_floor,0.0)
        spx,spy=proj(sx,sy,sz)
        p.setBrush(QBrush(QColor(0,0,0,60)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPoint(spx,spy), 40, 20)
        p.end()


class Minimal(QWidget):
    def __init__(self, on_open_full):
        super().__init__()
        self.setWindowTitle('AetherNeuro — Safe Mode')
        self.resize(600,300)
        v=QVBoxLayout()
        t=QLabel('AetherNeuro (Safe Mode)')
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet('font-size:28px; font-weight:600;')
        v.addWidget(t)
        m=QLabel('Launching minimal UI to avoid graphics issues.')
        m.setAlignment(Qt.AlignCenter)
        v.addWidget(m)
        btn=QPushButton('Open Full App')
        btn.clicked.connect(on_open_full)
        v.addWidget(btn)
        f=QLabel('by Jcarl Juson')
        f.setAlignment(Qt.AlignCenter)
        v.addWidget(f)
        self.setLayout(v)

_main_window=None
_splash=None

def main():
    parser=argparse.ArgumentParser(add_help=True)
    parser.add_argument('--nosplash',action='store_true')
    parser.add_argument('--safe',action='store_true')
    parser.add_argument('--external-splash',action='store_true')
    args,unknown=parser.parse_known_args()
    os.environ['QT_OPENGL']='software'
    QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
    
    try:
        import ctypes
        myappid = 'jcarldev.aethereeg.app.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass
        
    a=QApplication(sys.argv)
    
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'logo.png')
    if os.path.exists(icon_path):
        a.setWindowIcon(QIcon(icon_path))
        
    a.setStyleSheet("""
        QDialog { background-color: #f8fafc; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif; }
        QComboBox, QPushButton { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 12px; padding: 6px 14px; color: #0f172a; font-weight: 500; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif; }
        QComboBox:hover, QPushButton:hover { background-color: #f1f5f9; border-color: #94a3b8; }
        QComboBox:pressed, QPushButton:pressed { background-color: #e2e8f0; }
        QComboBox QAbstractItemView { background-color: #ffffff; color: #0f172a; selection-background-color: #007aff; selection-color: white; border: 1px solid #cbd5e1; outline: none; padding: 4px; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif; }
        QComboBox QAbstractItemView::item { padding: 4px 8px; color: #0f172a; }
        QComboBox QAbstractItemView::item:hover { background-color: #e2e8f0; }
        QComboBox::drop-down { border: none; width: 24px; }
        QCheckBox { spacing: 8px; color: #334155; font-weight: 500; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif; }
        QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff; }
        QCheckBox::indicator:checked { background-color: #007aff; border-color: #007aff; }
        QLabel { color: #0f172a; font-weight: 500; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif; }
        QProgressBar { border: none; border-radius: 6px; background-color: #e2e8f0; text-align: center; color: transparent; }
        QProgressBar::chunk { background-color: #007aff; border-radius: 6px; }
        QScrollArea { border: none; background: transparent; }
        QToolTip { color: #ffffff; background-color: #1e293b; border: 1px solid #475569; border-radius: 4px; padding: 6px; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif; }
    """)
    def open_main():
        global _main_window
        try:
            _main_window=App()
            _main_window.showMaximized()
        except Exception:
            traceback.print_exc()
            _main_window=App()
            _main_window.showMaximized()
    if args.safe:
        m=Minimal(open_main)
        m.show()
    else:
        open_main()
    sys.exit(a.exec())

if __name__=='__main__':
    main()
