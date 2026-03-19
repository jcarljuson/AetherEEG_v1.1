from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider, QPushButton, QCheckBox
from pynput.mouse import Controller, Button
import time

class MouseSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Mouse Control Settings')
        self.modeBox=QComboBox()
        self.modeBox.addItems(['Attention/Meditation Axes','Bands Axes'])
        self.sensSlider=QSlider()
        self.sensSlider.setOrientation(Qt.Horizontal)
        self.sensSlider.setMinimum(1)
        self.sensSlider.setMaximum(50)
        self.sensSlider.setValue(10)
        self.smoothSlider=QSlider()
        self.smoothSlider.setOrientation(Qt.Horizontal)
        self.smoothSlider.setMinimum(0)
        self.smoothSlider.setMaximum(95)
        self.smoothSlider.setValue(50)
        self.deadSlider=QSlider()
        self.deadSlider.setOrientation(Qt.Horizontal)
        self.deadSlider.setMinimum(0)
        self.deadSlider.setMaximum(80)
        self.deadSlider.setValue(10)
        self.clickBox=QComboBox()
        self.clickBox.addItems(['Blink Switch+Triple','Blink','Dwell'])
        self.blinkSlider=QSlider()
        self.blinkSlider.setOrientation(Qt.Horizontal)
        self.blinkSlider.setMinimum(20)
        self.blinkSlider.setMaximum(100)
        self.blinkSlider.setValue(50)
        self.windowSlider=QSlider()
        self.windowSlider.setOrientation(Qt.Horizontal)
        self.windowSlider.setMinimum(300)
        self.windowSlider.setMaximum(1500)
        self.windowSlider.setValue(900)
        self.rawSlider=QSlider()
        self.rawSlider.setOrientation(Qt.Horizontal)
        self.rawSlider.setMinimum(300)
        self.rawSlider.setMaximum(2000)
        self.rawSlider.setValue(650)
        self.okBtn=QPushButton('OK')
        v=QVBoxLayout()
        r1=QHBoxLayout(); r1.addWidget(QLabel('Mode')); r1.addWidget(self.modeBox)
        r2=QHBoxLayout(); r2.addWidget(QLabel('Sensitivity')); r2.addWidget(self.sensSlider)
        r3=QHBoxLayout(); r3.addWidget(QLabel('Smoothing%')); r3.addWidget(self.smoothSlider)
        r4=QHBoxLayout(); r4.addWidget(QLabel('Deadzone%')); r4.addWidget(self.deadSlider)
        r5=QHBoxLayout(); r5.addWidget(QLabel('Click Mode')); r5.addWidget(self.clickBox)
        r6=QHBoxLayout(); r6.addWidget(QLabel('Blink Threshold')); r6.addWidget(self.blinkSlider)
        r7=QHBoxLayout(); r7.addWidget(QLabel('Blink Window ms')); r7.addWidget(self.windowSlider)
        r8=QHBoxLayout(); r8.addWidget(QLabel('Raw Blink Threshold')); r8.addWidget(self.rawSlider)
        v.addLayout(r1); v.addLayout(r2); v.addLayout(r3); v.addLayout(r4); v.addLayout(r5); v.addLayout(r6); v.addLayout(r7); v.addLayout(r8); v.addWidget(self.okBtn)
        self.setLayout(v)
        self.okBtn.clicked.connect(self.accept)

class MouseController(QObject):
    def __init__(self):
        super().__init__()
        self.tripleBlink=Signal()
        self.mouse=Controller()
        self.enabled=False
        self.movement_active=True
        self.timer=QTimer()
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update)
        self.mode='Attention/Meditation Axes'
        self.sensitivity=10
        self.smooth=0.5
        self.deadzone=0.1
        self.click_mode='Blink Switch+Triple'
        self.blink_threshold=50
        self.blink_window_ms=900
        self.blink_refractory_s=0.3
        self.raw_threshold=650
        self._blink_timer=QTimer()
        self._blink_timer.setSingleShot(True)
        self._blink_timer.timeout.connect(self._finalize_blink_window)
        self._blink_count=0
        self._blink_window_start=None
        self._last_blink_time=0
        self._raw_prev=0
        self.last_move_time=time.time()
        self.last_click_time=0
        self.pos=(0,0)
        self.vals={'attention':None,'meditation':None,'bands':None,'blink':0}
    def start(self):
        self.enabled=True
        self.movement_active=True
        self.timer.start()
    def stop(self):
        self.enabled=False
        self.timer.stop()
    def settings(self,parent=None):
        d=MouseSettingsDialog(parent)
        d.modeBox.setCurrentText(self.mode)
        d.sensSlider.setValue(self.sensitivity)
        d.smoothSlider.setValue(int(self.smooth*100))
        d.deadSlider.setValue(int(self.deadzone*100))
        d.clickBox.setCurrentText(self.click_mode)
        d.blinkSlider.setValue(self.blink_threshold)
        d.windowSlider.setValue(self.blink_window_ms)
        d.rawSlider.setValue(self.raw_threshold)
        if d.exec():
            self.mode=d.modeBox.currentText()
            self.sensitivity=d.sensSlider.value()
            self.smooth=d.smoothSlider.value()/100.0
            self.deadzone=d.deadSlider.value()/100.0
            self.click_mode=d.clickBox.currentText()
            self.blink_threshold=d.blinkSlider.value()
            self.blink_window_ms=d.windowSlider.value()
            self.raw_threshold=d.rawSlider.value()
    def feed(self,d):
        if 'attention' in d:
            self.vals['attention']=self._ema(self.vals['attention'],d['attention'])
        if 'meditation' in d:
            self.vals['meditation']=self._ema(self.vals['meditation'],d['meditation'])
        if 'bands' in d:
            self.vals['bands']=self._ema_bands(self.vals['bands'],d['bands'])
        if 'blink' in d:
            self.vals['blink']=d['blink']
            if self.click_mode=='Blink Switch+Triple' and d['blink']>=self.blink_threshold:
                self._on_blink_event()
        if 'raw_wave' in d:
            rv=d['raw_wave']
            if abs(rv)>=self.raw_threshold and abs(self._raw_prev)<self.raw_threshold:
                if self.click_mode=='Blink':
                    if time.time()-self.last_click_time>0.5:
                        self.mouse.click(Button.left,1)
                        self.last_click_time=time.time()
                else:
                    self._on_blink_event()
            self._raw_prev=rv
    def update(self):
        if not self.enabled:
            return
        dx,dy=0,0
        if self.mode=='Attention/Meditation Axes':
            a=self._norm(self.vals['attention'])
            m=self._norm(self.vals['meditation'])
            if a is not None and abs(a)>self.deadzone:
                dy=-int(a*self.sensitivity)
            if m is not None and abs(m)>self.deadzone:
                dx=int(m*self.sensitivity)
        else:
            b=self.vals['bands'] or {}
            la=self._norm_band(b,'low_alpha')
            hb=self._norm_band(b,'high_beta')
            lg=self._norm_band(b,'low_gamma')
            th=self._norm_band(b,'theta')
            if hb is not None and abs(hb)>self.deadzone:
                dy=-int(hb*self.sensitivity)
            if la is not None and abs(la)>self.deadzone:
                dy+=int(la*self.sensitivity)
            if lg is not None and abs(lg)>self.deadzone:
                dx+=int(lg*self.sensitivity)
            if th is not None and abs(th)>self.deadzone:
                dx-=int(th*self.sensitivity)
        if not self.movement_active:
            dx,dy=0,0
        if dx!=0 or dy!=0:
            self.last_move_time=time.time()
            p=self.mouse.position
            self.mouse.position=(p[0]+dx,p[1]+dy)
        if self.click_mode=='Blink':
            if self.vals['blink']>=self.blink_threshold and time.time()-self.last_click_time>0.5:
                self.mouse.click(Button.left,1)
                self.last_click_time=time.time()
        elif self.click_mode=='Dwell':
            if time.time()-self.last_move_time>1.0 and time.time()-self.last_click_time>1.0:
                self.mouse.click(Button.left,1)
                self.last_click_time=time.time()
        # Blink Switch+Triple handled in _on_blink_event
    def _ema(self,prev,val):
        if prev is None:
            return val
        return prev*(self.smooth)+(1-self.smooth)*val
    def _ema_bands(self,prev,vals):
        if prev is None:
            return vals.copy()
        out={}
        for k in vals:
            out[k]=prev.get(k,vals[k])*self.smooth+(1-self.smooth)*vals[k]
        return out
    def _norm(self,v):
        if v is None:
            return None
        return (v-50)/50.0
    def _norm_band(self,b,k):
        v=b.get(k)
        if v is None:
            return None
        total=sum(b.values()) if b else 0
        if total<=0:
            return None
        ratio=v/total
        return (ratio-0.125)*2.0

    def _on_blink_event(self):
        now=time.time()
        if now - self._last_blink_time < self.blink_refractory_s:
            return
        self._last_blink_time=now
        if self._blink_window_start is None or (now - self._blink_window_start) > (self.blink_window_ms/1000.0):
            self._blink_window_start=now
            self._blink_count=1
            self._blink_timer.stop()
            self._blink_timer.setInterval(self.blink_window_ms)
            self._blink_timer.start()
        else:
            self._blink_count+=1
        if self._blink_count>=3:
            self.tripleBlink.emit()
            self._blink_timer.stop()
            self._blink_window_start=None
            self._blink_count=0

    def _finalize_blink_window(self):
        if self._blink_count==1:
            self.movement_active=not self.movement_active
        self._blink_window_start=None
        self._blink_count=0