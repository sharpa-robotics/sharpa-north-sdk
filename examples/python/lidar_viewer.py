#!/usr/bin/env python3
"""Read-only Lidar preview in a local browser; Python standard library + NorthSDK.

The SDK decodes every incoming frame. Display throttling/decimation only reduces
Python conversion and browser rendering work, not network or SDK decode work.
"""
import argparse
import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PAGE = r'''<!doctype html><html lang="zh"><meta charset="utf-8">
<title>NorthSDK 点云预览</title><style>
body{margin:0;background:#101924;color:#dbe6f3;font:14px system-ui}header{padding:14px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}canvas{display:block;width:100vw;height:calc(100vh - 110px);touch-action:none}button,input,select{accent-color:#58c4ed}#status{padding:0 14px 8px;color:#95b1cb}small{color:#95b1cb}
</style><header><b>NorthSDK 点云预览</b><button id="pause">暂停显示</button>
<label>视野半径 <input id="range" type="range" min="1" max="50" value="15"> <span id="radius">15</span> m</label>
<label>着色 <select id="color"><option value="height">高度 Z</option><option value="reflectivity">反射强度</option></select></label>
<button id="reset">重置视角</button><small>拖动旋转 · 滚轮缩放 · 坐标单位 m · 红X / 绿Y / 蓝Z</small></header><div id="status">等待点云…</div><canvas id="view"></canvas><script>
const canvas=document.querySelector('#view'),ctx=canvas.getContext('2d'),status=document.querySelector('#status');
let points=[],yaw=.65,pitch=.8,paused=false,drag=false,lx=0,ly=0,meta=null;
function project(x,y,z){let u=x*Math.cos(yaw)-y*Math.sin(yaw),v=x*Math.sin(yaw)+y*Math.cos(yaw);let scale=Math.min(canvas.width,canvas.height)/2.25/Number(document.querySelector('#range').value);return[canvas.width/2+u*scale,canvas.height/2+(v*Math.sin(pitch)-z*Math.cos(pitch))*scale];}
function line(a,b,color){let p=project(...a),q=project(...b);ctx.strokeStyle=color;ctx.beginPath();ctx.moveTo(...p);ctx.lineTo(...q);ctx.stroke();}
function render(){const dpr=window.devicePixelRatio||1,w=Math.round(canvas.clientWidth*dpr),h=Math.round(canvas.clientHeight*dpr);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}ctx.fillStyle='#101924';ctx.fillRect(0,0,w,h);let radius=Number(document.querySelector('#range').value);document.querySelector('#radius').textContent=radius;for(let i=-10;i<=10;i++){line([i,-10,0],[i,10,0],'#233242');line([-10,i,0],[10,i,0],'#233242');}line([0,0,0],[2,0,0],'#ff6666');line([0,0,0],[0,2,0],'#78e59b');line([0,0,0],[0,0,2],'#66aaff');for(const p of points){if(Math.hypot(p[0],p[1])>radius*1.5)continue;let q=project(p[0],p[1],p[2]);let t=document.querySelector('#color').value==='height'?Math.max(0,Math.min(1,(p[2]+2)/5)):p[3]/255;ctx.fillStyle=`hsl(${240-t*240},90%,65%)`;ctx.fillRect(q[0],q[1],2*dpr,2*dpr);}}
canvas.onpointerdown=e=>{drag=true;lx=e.clientX;ly=e.clientY;canvas.setPointerCapture(e.pointerId)};canvas.onpointermove=e=>{if(!drag)return;yaw+=(e.clientX-lx)*.008;pitch=Math.max(-1.5,Math.min(1.5,pitch+(e.clientY-ly)*.008));lx=e.clientX;ly=e.clientY;render()};canvas.onpointerup=()=>drag=false;
canvas.onwheel=e=>{e.preventDefault();let r=document.querySelector('#range');r.value=Math.max(1,Math.min(50,Number(r.value)*(e.deltaY>0?1.1:.9)));render()};
document.querySelector('#pause').onclick=()=>{paused=!paused;document.querySelector('#pause').textContent=paused?'继续显示':'暂停显示（订阅仍继续）';};document.querySelector('#reset').onclick=()=>{yaw=.65;pitch=.8;render()};document.querySelector('#range').oninput=render;document.querySelector('#color').onchange=render;window.onresize=render;
async function poll(){let delay=500;try{if(!paused){let response=await fetch('/frame',{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);meta=await response.json();delay=meta.refresh_ms;points=meta.points;status.textContent=`${meta.source} | ${meta.kind} | 接收 ${meta.received} 帧 | 原始 ${meta.total_points} 点 / 显示 ${points.length} 点 | 数据年龄 ${meta.age_ms===null?'等待':meta.age_ms.toFixed(0)+' ms'} | ${meta.error||''}`;render();}}catch(e){status.textContent='连接失败：'+e.message;}setTimeout(poll,delay);}render();poll();
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='udp/192.168.100.100:7449')
    parser.add_argument('--source', choices=('chassis', 'chest-front', 'chest-rear'), default='chassis')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--fps', type=float, default=2)
    parser.add_argument('--max-points', type=int, default=6000)
    parser.add_argument('--demo', action='store_true', help='Synthetic data; no SDK import or robot connection')
    args = parser.parse_args()
    if not 0 < args.fps <= 10 or not 1 <= args.max_points <= 100000:
        parser.error('fps must be in (0,10], max-points in [1,100000]')
    lock = threading.Lock()
    state = dict(frame=None, received=0, received_at=None)
    sdk = subscription = None
    # Bind locally before subscribing so a busy port never starts extra robot traffic.
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/':
                data, content_type = PAGE.encode(), 'text/html; charset=utf-8'
            elif path == '/frame':
                with lock:
                    frame, received, at = state['frame'], state['received'], state['received_at']
                points, total, kind, error = [], 0, 'waiting', ''
                if args.demo:
                    kind = 'DEMO（合成数据）'
                    points = [[math.cos(i/40)*5, math.sin(i/40)*5, math.sin(i/19), i%256] for i in range(min(2000,args.max_points))]
                    total = len(points)
                elif frame is not None:
                    kind = str(frame.kind).rsplit('.', 1)[-1]
                    groups = frame.laser_shots if kind == 'LASER_SHOTS' else frame.sub_areas
                    total = frame.packed_point_count
                    # All supported platform inputs have a packed point count. For plain
                    # frames, infer it from group data. Never retain unbounded history.
                    if not total:
                        total = sum(len(group.points) for group in groups)
                    step = max(1, math.ceil(total / args.max_points))
                    offset = 0
                    for group in groups:
                        values = group.points
                        first = (-offset) % step
                        for point in values[first::step]:
                            if all(math.isfinite(v) for v in (point.x, point.y, point.z)):
                                points.append([point.x, point.y, point.z, point.reflectivity])
                        offset += len(values)
                    points = points[:args.max_points]
                    if not points and total:
                        error = '没有可显示坐标，请检查SDK解码版本'
                if sdk:
                    error = sdk.callback_diagnostics().last_decode_error.message or error
                payload = dict(source=args.source, kind=kind, received=received,
                               total_points=total, points=points, error=error,
                               age_ms=None if at is None else (time.monotonic()-at)*1000,
                               refresh_ms=round(1000/args.fps))
                data = json.dumps(payload, separators=(',', ':'), allow_nan=False).encode()
                content_type = 'application/json'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.daemon_threads = True
    try:
        if not args.demo:
            import north_sdk as n
            config = n.SdkConfig()
            config.connect_endpoints = [args.endpoint]
            sdk = n.NorthSDK(config)
            sdk.connect()
            source = {'chassis': n.LidarSource.CHASSIS_FRONT,
                      'chest-front': n.LidarSource.CHEST_FRONT,
                      'chest-rear': n.LidarSource.CHEST_REAR}[args.source]
            def on_frame(frame):
                with lock:
                    state.update(frame=frame, received=state['received']+1, received_at=time.monotonic())
            subscription = sdk.sensors().on_lidar(source, on_frame)
        print(f'Open http://127.0.0.1:{args.port} in your browser; Ctrl+C stops subscription.', flush=True)
        print('Read-only; adds network/CPU/GPU rendering load. Do not use during formal resource measurements.', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if subscription:
            subscription.close()
        if sdk:
            sdk.close()
        server.server_close()


if __name__ == '__main__':
    main()
