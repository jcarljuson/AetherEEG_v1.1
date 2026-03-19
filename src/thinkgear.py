import struct

SYNC=0xAA

def parse_payload(payload):
    i=0
    out={}
    L=len(payload)
    while i<L:
        code=payload[i]
        i+=1
        if code==0x55:
            while i<L and payload[i]==0x55:
                i+=1
            if i>=L:
                break
            code=payload[i]
            i+=1
        if code<0x80:
            vlen=1
            if i+vlen> L:
                break
            val=payload[i]
            i+=vlen
            if code==0x02:
                out['poor_signal']=val
            elif code==0x04:
                out['attention']=val
            elif code==0x05:
                out['meditation']=val
            elif code==0x16:
                out['blink']=val
        else:
            if i>=L:
                break
            vlen=payload[i]
            i+=1
            if i+vlen> L:
                break
            data=payload[i:i+vlen]
            i+=vlen
            if code==0x80 and vlen==2:
                raw=struct.unpack('>h',data)[0]
                out['raw_wave']=raw
            elif code==0x83 and vlen==24:
                bands=[]
                for k in range(8):
                    p=data[k*3:(k+1)*3]
                    bands.append(p[0]<<16|p[1]<<8|p[2])
                out['bands']={
                    'delta':bands[0],
                    'theta':bands[1],
                    'low_alpha':bands[2],
                    'high_alpha':bands[3],
                    'low_beta':bands[4],
                    'high_beta':bands[5],
                    'low_gamma':bands[6],
                    'mid_gamma':bands[7]
                }
    return out

def find_packets(buffer):
    i=0
    packets=[]
    while True:
        j=buffer.find(bytes([SYNC,SYNC]),i)
        if j==-1 or j+3>=len(buffer):
            break
        l=buffer[j+2]
        end=j+3+l
        if end>=len(buffer):
            break
        checksum=buffer[end]
        payload=buffer[j+3:end]
        s=sum(payload)&0xFF
        if ((~s)&0xFF)==checksum:
            packets.append(payload)
            i=end+1
        else:
            i=j+1
    return packets,i