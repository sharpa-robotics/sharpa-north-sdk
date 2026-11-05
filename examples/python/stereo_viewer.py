#!/usr/bin/env python3
"""Show SDK camera JPEG callbacks in a local browser; no GUI packages needed.

From the checkout: python3 examples/python/stereo_viewer.py
The local build/sdk/python binding is used when present. No robot commands are sent.
"""

import argparse
import json
import math
import signal
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SDK 相机预览</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#10151c;color:#e8eef6;font:15px system-ui,sans-serif}
header{display:flex;justify-content:space-between;align-items:center;padding:20px 24px;border-bottom:1px solid #303b48;gap:16px}
h1{margin:0 0 6px;font-size:22px}p{margin:0;color:#aebdce}button{background:#34475b;color:white;border:1px solid #64798e;border-radius:7px;padding:10px 16px;cursor:pointer}
main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;padding:22px}
article{border:1px solid #303b48;border-radius:10px;overflow:hidden;background:#19212b}
.title{padding:14px 16px;display:flex;justify-content:space-between;gap:10px}.title strong{font-size:18px}
.state{color:#91c9a5}.state.waiting{color:#e9bb75}.picture{aspect-ratio:4/3;position:relative;background:#080b10;display:flex;align-items:center;justify-content:center}
.picture img{display:block;width:100%;height:100%;object-fit:contain;position:absolute;inset:0}.placeholder{color:#aebdce}
.metrics{display:flex;flex-wrap:wrap;gap:10px 24px;padding:15px 16px;border-top:1px solid #303b48}.metrics span{color:#aebdce}.metrics b{color:#e8eef6;font-weight:500}
.detail{padding:0 16px 15px;color:#aebdce;font-size:13px;overflow-wrap:anywhere}.error{color:#f2b5aa;margin-top:7px;min-height:18px}
footer{padding:0 24px 20px;color:#aebdce;font-size:13px}
@media(max-width:850px){main{grid-template-columns:1fr}header{align-items:flex-start}.picture{max-height:65vh}}
</style></head><body>
<header><div><h1>SDK 相机预览</h1><p id="connection">正在连接预览程序…</p></div><button id="stop">停止预览</button></header>
<main>__CAMERA_CARDS__</main><footer>各路独立刷新，不保证同步。FPS 为 SDK 交付速率，浏览器可能跳过旧图片。时延截至 C++ 回调入口，不含网络、GIL 等待与浏览器显示。Ctrl+C 或“停止预览”退出。</footer>
<script>
let stopped=false;
async function refresh(){
 try{
  const response=await fetch('/api/status',{cache:'no-store'});
  if(!response.ok)throw new Error('status');
  const data=await response.json();
  if(stopped)return;
  document.querySelector('#connection').textContent=`${data.endpoint} · ${data.decoder} · JPEG quality ${data.quality}`;
  for(const name of Object.keys(data.eyes)){
   const eye=data.eyes[name],card=document.getElementById(name),state=card.querySelector('.state');
   const fresh=eye.age_seconds!==null&&eye.age_seconds<2;
   state.textContent=!data.running?'已停止':fresh?'接收中':eye.received_au===0?'未收到 AU':eye.waiting_for_keyframe?'等待 IDR':'等待新图片';
   state.classList.toggle('waiting',!fresh);
   card.querySelector('.au').textContent=eye.au_fps.toFixed(1);
   card.querySelector('.fps').textContent=eye.jpeg_fps.toFixed(1);
   card.querySelector('.latency').textContent=eye.count?eye.sdk_latency_ms.toFixed(1):'—';
   card.querySelector('img').style.visibility=eye.count?'visible':'hidden';
   card.querySelector('.placeholder').style.visibility=eye.count?'hidden':'visible';
   card.querySelector('.info').textContent=eye.count?`${eye.width} × ${eye.height} · seq ${eye.seq} · 最近图片 ${eye.age_seconds.toFixed(1)} 秒前 · 重置 ${eye.resets} · AU 丢弃 ${eye.dropped_au} · JPEG 覆盖 ${eye.dropped_jpeg}`:'尚未收到图片';
   card.querySelector('.error').textContent=eye.error?'最近错误：'+eye.error:'';
  }
 }catch(error){if(!stopped)document.querySelector('#connection').textContent='预览程序已退出或连接中断';}
 if(!stopped)setTimeout(refresh,500);
}
document.querySelector('#stop').onclick=async()=>{
 stopped=true;
 document.querySelector('#stop').disabled=true;
 try{await fetch('/api/stop',{method:'POST'});}catch(error){}
 for(const image of document.querySelectorAll('img'))image.removeAttribute('src');
 document.querySelector('#connection').textContent='预览已停止，可以关闭此页面';
 for(const state of document.querySelectorAll('.state'))state.textContent='已停止';
};
refresh();
</script></body></html>"""


CAMERAS = {
    "left": ("左眼", "HEAD_LEFT"),
    "right": ("右眼", "HEAD_RIGHT"),
    "wrist_left": ("左腕", "WRIST_LEFT"),
    "wrist_right": ("右腕", "WRIST_RIGHT"),
}


def page_for(names):
    cards = []
    for name in names:
        label = CAMERAS[name][0]
        cards.append(f"""<article id="{name}">
<div class="title"><strong>{label}</strong><span class="state waiting">等待画面</span></div>
<div class="picture"><span class="placeholder">等待平台视频</span><img src="/stream/{name}" alt="{label}" style="visibility:hidden"></div>
<div class="metrics"><span>AU 输入 <b class="au">—</b> FPS</span><span>SDK 图片 <b class="fps">—</b> FPS</span><span>SDK 时延 <b class="latency">—</b> ms</span></div>
<div class="detail"><div class="info">尚未收到图片</div><div class="error"></div></div></article>""")
    return PAGE.replace("__CAMERA_CARDS__", "".join(cards)).encode("utf-8")


class LatestImages:
    """One immutable JPEG per camera; socket writes never hold the image lock."""

    def __init__(self, args, names=("left", "right")):
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.running = True
        self.config = {"endpoint": args.endpoint, "decoder": args.decoder,
                       "quality": args.quality}
        self.eyes = {name: {"data": b"", "count": 0, "width": 0, "height": 0,
                           "seq": 0, "updated": None, "sdk_latency_ms": 0.0,
                           "au_fps": 0.0, "jpeg_fps": 0.0, "received_au": 0,
                           "resets": 0, "dropped_au": 0, "dropped_jpeg": 0,
                           "waiting_for_keyframe": True, "error": ""}
                     for name in names}

    def callback(self, name):
        def receive(frame):
            # Python owns frame/data; copy the bytes property before taking the lock.
            data = frame.data
            received = time.monotonic()
            with self.condition:
                eye = self.eyes[name]
                eye.update(data=data, width=frame.width, height=frame.height,
                           seq=frame.header.seq, updated=received,
                           sdk_latency_ms=frame.sdk_latency_ns / 1e6)
                eye["count"] += 1
                self.condition.notify_all()
        return receive

    def status(self):
        now = time.monotonic()
        with self.condition:
            eyes = {name: {key: value for key, value in eye.items()
                           if key not in ("data", "updated")}
                    for name, eye in self.eyes.items()}
            for name, eye in self.eyes.items():
                eyes[name]["age_seconds"] = None if eye["updated"] is None else now - eye["updated"]
            return dict(self.config, running=self.running, eyes=eyes)

    def close(self):
        with self.condition:
            self.running = False
            self.condition.notify_all()


def handler_for(images):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/":
                self.reply(page_for(images.eyes), "text/html; charset=utf-8")
            elif path == "/api/status":
                self.reply(json.dumps(images.status()).encode("utf-8"), "application/json")
            elif path.startswith("/stream/") and path.rsplit("/", 1)[1] in images.eyes:
                self.stream(path.rsplit("/", 1)[1])
            else:
                self.send_error(404)

        def reply(self, body, content_type):
            try:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except (OSError, TimeoutError):
                pass

        def stream(self, name):
            self.connection.settimeout(3)
            last = 0
            try:
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                while True:
                    with images.condition:
                        images.condition.wait_for(
                            lambda: not images.running or images.eyes[name]["count"] != last)
                        if not images.running:
                            return
                        eye = images.eyes[name]
                        last, jpeg = eye["count"], eye["data"]
                    # Socket writes are outside the lock and outside the SDK worker.
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                                     str(len(jpeg)).encode("ascii") + b"\r\n\r\n" + jpeg + b"\r\n")
                    self.wfile.flush()
            except (OSError, TimeoutError):
                pass

        def do_POST(self):
            if urlsplit(self.path).path != "/api/stop":
                self.send_error(404)
                return
            self.reply(b"stopping", "text/plain")
            images.stop.set()

    return Handler


def parse_args(default_cameras="stereo"):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--endpoint", default="udp/192.168.100.100:7449?rel=1;multistream=1;mixed_rel=0")
    parser.add_argument("--decoder", choices=("software", "nvdec"), default="nvdec",
                        help="default: NVIDIA hardware decoding; software is an explicit fallback")
    parser.add_argument("--cameras", choices=("stereo", "all"), default=default_cameras)
    parser.add_argument("--wrist-size", default="960x960", help="wrist JPEG size, or source")
    parser.add_argument("--quality", type=int, default=85)
    parser.add_argument("--size", default="1280x960", metavar="WIDTHxHEIGHT",
                        help="SDK JPEG size (default 1280x960); use 'source' to preserve source size")
    parser.add_argument("--port", type=int, default=0, help="local web port; 0 chooses an available port")
    parser.add_argument("--no-browser", action="store_true", help="print the URL without opening a browser")
    parser.add_argument("--seconds", type=float, default=0, help="exit after this duration; 0 runs until stopped")
    args = parser.parse_args()
    if not 1 <= args.quality <= 100:
        parser.error("quality must be 1..100")
    if not 0 <= args.port <= 65535 or not math.isfinite(args.seconds) or args.seconds < 0:
        parser.error("port must be 0..65535; seconds must be nonnegative")
    def dimensions(value):
        if value == "source":
            return 0, 0
        try:
            width, height = map(int, value.split("x"))
            if not 1 <= width <= 8192 or not 1 <= height <= 8192:
                raise ValueError()
            return width, height
        except ValueError:
            parser.error("size must be source or WIDTHxHEIGHT, each dimension 1..8192")
    args.width, args.height = dimensions(args.size)
    args.wrist_width, args.wrist_height = dimensions(args.wrist_size)
    return args


def main(default_cameras="stereo"):
    args = parse_args(default_cameras)
    local_binding = Path(__file__).resolve().parents[2] / "build/sdk/python"
    if local_binding.is_dir():
        sys.path.insert(0, str(local_binding))
    try:
        from north_sdk import NorthSDK, SdkConfig, VideoSource, VideoOptions, VideoDecoderBackend
    except ImportError as error:
        print(f"Cannot load SDK video binding: {error}\n"
              "Build the _north_sdk target with video enabled, or set PYTHONPATH to its python directory.",
              file=sys.stderr)
        return 1

    names = list(CAMERAS) if args.cameras == "all" else ["left", "right"]
    images = LatestImages(args, names)
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: images.stop.set())
    options = VideoOptions()
    options.jpeg_quality = args.quality
    options.output_width, options.output_height = args.width, args.height
    options.decoder_backend = VideoDecoderBackend.NVDEC if args.decoder == "nvdec" else VideoDecoderBackend.SOFTWARE
    config = SdkConfig()
    config.connect_endpoints = [args.endpoint]
    sources = {name: getattr(VideoSource, CAMERAS[name][1]) for name in names}
    sdk = server = server_thread = None
    subscriptions = []
    try:
        sdk = NorthSDK(config)
        sdk.connect()
        video = sdk.video()
        for name, source in sources.items():
            options.output_width, options.output_height = (
                (args.wrist_width, args.wrist_height) if name.startswith("wrist_")
                else (args.width, args.height))
            subscriptions.append(video.on_jpeg(source, images.callback(name), options))
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(images))
        server.daemon_threads = True
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        print(f"PREVIEW_URL={url}", flush=True)
        print("Receiving " + ", ".join(names) + ". Ctrl+C or the page Stop button exits.", flush=True)
        if not args.no_browser and not webbrowser.open(url, new=1):
            print("Browser did not open automatically; open the URL above.", flush=True)
        started = previous_time = time.monotonic()
        previous = {name: (0, 0) for name in sources}
        startup_checked = set()
        while not images.stop.wait(.5):
            now = time.monotonic()
            elapsed = now - previous_time
            for name, source in sources.items():
                diagnostic = video.diagnostics(source)
                if now - started >= 5 and name not in startup_checked:
                    startup_checked.add(name)
                    if not diagnostic.jpeg_frame_count:
                        reason = ("no camera AUs received" if not diagnostic.received_au_count else
                                  "AUs received but no JPEG decoded; check keyframes and decoder")
                        print(f"Startup check {name}: {reason}; "
                              f"last_error={diagnostic.last_error.message}", file=sys.stderr)
                with images.condition:
                    eye = images.eyes[name]
                    old_au, old_jpeg = previous[name]
                    eye.update(au_fps=(diagnostic.received_au_count - old_au) / elapsed,
                               jpeg_fps=(eye["count"] - old_jpeg) / elapsed,
                               received_au=diagnostic.received_au_count,
                               resets=diagnostic.reset_count,
                               dropped_au=diagnostic.dropped_au_count,
                               dropped_jpeg=diagnostic.dropped_jpeg_count,
                               waiting_for_keyframe=diagnostic.waiting_for_keyframe,
                               error=diagnostic.last_error.message)
                    previous[name] = diagnostic.received_au_count, eye["count"]
            previous_time = now
            if args.seconds and now - started >= args.seconds:
                break
    except Exception as error:
        print(f"Preview failed: {error}", file=sys.stderr)
        return 1
    finally:
        # Close outside the image lock: SDK workers may still be invoking callbacks.
        if sdk is not None:
            sdk.close()
        images.close()
        if server is not None:
            if server_thread is not None and server_thread.ident is not None:
                server.shutdown()
            server.server_close()
        if server_thread is not None and server_thread.ident is not None:
            server_thread.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
