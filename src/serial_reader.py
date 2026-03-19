from PySide6.QtCore import QObject, Signal, QThread
import serial
import serial.tools.list_ports
import time
try:
    from .thinkgear import find_packets, parse_payload
except Exception:
    try:
        from src.thinkgear import find_packets, parse_payload
    except Exception:
        from thinkgear import find_packets, parse_payload

class SerialWorker(QObject):
    data=Signal(dict)
    status=Signal(str)
    def __init__(self,port,baud):
        super().__init__()
        self.port=port
        self.baud=baud
        self._running=False
        self._ser=None
        self._buf=bytearray()
    def start(self):
        try:
            self._ser=serial.Serial(self.port,self.baud,timeout=0.1)
            self._running=True
            self.status.emit('connected')
        except Exception as e:
            self.status.emit('error')
            self._running=False
    def stop(self):
        self._running=False
        try:
            if self._ser:
                self._ser.close()
        except:
            pass
        self.status.emit('disconnected')
    def loop(self):
        while self._running:
            try:
                b=self._ser.read(256)
                if b:
                    self._buf.extend(b)
                    packets,end=find_packets(self._buf)
                    if end>0:
                        del self._buf[:end]
                    for p in packets:
                        d=parse_payload(p)
                        if d:
                            self.data.emit(d)
            except Exception as e:
                self.status.emit('error')
                time.sleep(0.2)

def list_ports():
    return [p.device for p in serial.tools.list_ports.comports()]

def detect_port_baud(timeout=2.0):
    ports=list_ports()
    bauds=[57600,115200,9600]
    for pt in ports:
        for bd in bauds:
            try:
                ser=serial.Serial(pt,bd,timeout=0.1)
                buf=bytearray()
                t0=time.time()
                ok=False
                while time.time()-t0<timeout:
                    b=ser.read(256)
                    if b:
                        buf.extend(b)
                        packets,end=find_packets(buf)
                        if end>0:
                            del buf[:end]
                        for p in packets:
                            d=parse_payload(p)
                            if 'raw_wave' in d or 'bands' in d:
                                ok=True
                                break
                    if ok:
                        break
                ser.close()
                if ok:
                    return pt,bd
            except:
                try:
                    ser.close()
                except:
                    pass
                continue
    return None,None