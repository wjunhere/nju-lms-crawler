#!/usr/bin/env python3
"""
NJU 智汇南雍 LMS 课件下载器 —— 复用你已登录的浏览器会话。

原理：你只需让一个"登录过 LMS 的 Chrome/Edge"以 --remote-debugging-port 启动，
本脚本用 playwright 连上它(connect_over_cdp)，在登录态下 fetch 后端 API 拿到
服务器签名直链(短时效、自包含、无需 cookie)，再用 urllib 下载。

依赖：仅 playwright（用于连已登录浏览器）。下载用标准库 urllib，无需 requests。

用法：
    python crawler.py 41445 38895                 # 按活动 id 下载全部附件
    python crawler.py 41445 --out B:/deeptutor    # 指定输出目录(默认 ./downloads)
    python crawler.py 41445 --cdp http://127.0.0.1:9224       # 指定 CDP 端点
    python crawler.py 38895 --no-download         # 只列出文件、不下载
"""
import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

LMS = "https://lms.nju.edu.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"

# 常见已登录 CDP 端点（Chrome=9224、Edge=9223），可按需用 --cdp 覆盖
DEFAULT_CDP = ["http://127.0.0.1:9224", "http://127.0.0.1:9223"]


def log(msg):
    """统一走 stderr，避免污染 stdout 的结构化输出。"""
    print(msg, file=sys.stderr, flush=True)


# ---- 在页面上下文里执行的 JS：枚举附件 + 取签名直链 ----
def _build_js(activity_id):
    return """
(async()=>{
  const ID = %s;
  const r = await fetch('/api/activities/'+ID, {headers:{Accept:'application/json'}});
  const ct = (r.headers.get('content-type')||'');
  if(!r.ok || !ct.includes('json')){
    return {auth:false, status:r.status, ct:ct};   // 未登录/被重定向到登录页
  }
  const act = await r.json();
  const ids=[]; const c=(o)=>{if(Array.isArray(o))o.forEach(c); else if(o&&typeof o==='object'){if(o.upload_id)ids.push(o.upload_id); Object.values(o).forEach(c);}}; c(act);
  const files=[];
  for(const id of [...new Set(ids)]){
    try{
      const p = await (await fetch('/api/uploads/'+id+'/preview',{headers:{Accept:'application/json'}})).json();
      let name = p.name;
      try{ const m = await (await fetch('/api/uploads/'+id)).json(); if(m && m.name) name = m.name; }catch(_){}
      files.push({id, name, url: p.url});
    }catch(e){ files.push({id, err:String(e)}); }
  }
  return {auth:true, files};
})()
""" % activity_id


def _preview_id_js(upload_id):
    """重新取某个 upload 的签名直链（用于签名过期后的重取）。"""
    return """
(async()=>{
  try{
    const p = await (await fetch('/api/uploads/%s/preview',{headers:{Accept:'application/json'}})).json();
    return {url:p.url};
  }catch(e){ return {err:String(e)}; }
})()
""" % upload_id


# ---- 浏览器连接：逐个 CDP 端点尝试，直到连上并且已登录 LMS ----
def connect(page, cdp_list):
    last = None
    for cdp in cdp_list:
        try:
            page.goto(LMS, wait_until="domcontentloaded", timeout=20000)
            probe = page.evaluate(
                "(async()=>{const r=await fetch('/api/activities/38895',{headers:{Accept:'application/json'}});"
                "const ct=(r.headers.get('content-type')||'');return {ok:r.ok, ct};})()"
            )
            if probe.get("ok") and "json" in (probe.get("ct") or ""):
                log(f"[连接] 已连上并登录: {cdp}")
                return True
            log(f"[跳过] {cdp}: 已连接但似乎未登录 LMS")
        except Exception as e:  # 连接失败 / 页面加载失败
            log(f"[跳过] {cdp}: {e}")
        last = cdp
    log("❌ 没有可用的已登录浏览器。请先启动一个登录过 LMS 的 Chrome/Edge：")
    log("   chrome.exe --remote-debugging-port=9224 ...   （然后重新运行本脚本）")
    sys.exit(1)


def safe_name(name):
    return "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in (name or "file"))


def _http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=180)


def download(url, dest, name):
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / safe_name(name)
    with _http_get(url) as r, open(path, "wb") as f:
        shutil.copyfileobj(r, f)
    return path.stat().st_size


def fetch_files(page, activity_id):
    res = page.evaluate(_build_js(activity_id))
    if res.get("auth") is False:
        log(f"[警告] 活动 {activity_id}: 未登录或接口被拒(status={res.get('status')})，跳过")
        return None
    files = res.get("files") or []
    return [f for f in files if f.get("url")]


def main():
    ap = argparse.ArgumentParser(description="NJU 智汇南雍 LMS 课件下载器")
    ap.add_argument("activities", nargs="+", help="活动 id，可多个")
    ap.add_argument("--cdp", help="CDP 端点，逗号分隔（默认 9224,9223）")
    ap.add_argument("--out", default="downloads", help="输出目录（默认 ./downloads）")
    ap.add_argument("--no-download", action="store_true", help="只列出文件，不下载")
    args = ap.parse_args()

    cdp_list = [u.strip() for u in args.cdp.split(",") if u.strip()] if args.cdp else DEFAULT_CDP
    out = Path(args.out)
    download_ok = download_fail = listed = 0

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("❌ 未安装 playwright。请运行: pip install -r requirements.txt")
        sys.exit(1)
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(cdp_list[0])
        except Exception:
            # connect_over_cdp 失败时逐点尝试
            browser = None
            for cdp in cdp_list:
                try:
                    browser = p.chromium.connect_over_cdp(cdp)
                    break
                except Exception:
                    continue
            if browser is None:
                log("❌ 无法连接任何 CDP 浏览器。请先启动已登录 LMS 的 Chrome/Edge（--remote-debugging-port）再试。")
                sys.exit(1)
        page = browser.contexts[0].new_page()

        if not connect(page, cdp_list):
            sys.exit(1)

        for activity in args.activities:
            files = fetch_files(page, activity)
            if files is None:
                continue
            if not files:
                log(f"[信息] 活动 {activity}: 未发现可下载附件")
                continue
            log(f"[活动 {activity}] 发现 {len(files)} 个附件:")
            for f in files:
                log(f"   - [{f['id']}] {f['name']}")
            if args.no_download:
                listed += len(files)
                continue
            for f in files:
                full = f.get("url")
                name = f.get("name", f"upload_{f['id']}")
                for attempt in (1, 2):
                    try:
                        size = download(full, out, name)
                        log(f"  ✅ {name}  {size} 字节 -> {out / safe_name(name)}")
                        download_ok += 1
                        break
                    except urllib.error.HTTPError as e:
                        if e.code == 403 and attempt == 1:  # 签名可能过期，重取
                            log(f"  ↻ {name}: 直链失效(403)，重取签名...")
                            fresh = page.evaluate(_preview_id_js(f["id"]))
                            if fresh.get("url"):
                                full = fresh["url"]
                                continue
                        log(f"  ❌ {name}: HTTP {e.code}")
                        download_fail += 1
                        break
                    except Exception as e:
                        log(f"  ❌ {name}: {e}")
                        download_fail += 1
                        break
        page.close()

    log("")
    log(f"完成：下载 {download_ok} 个，失败 {download_fail} 个，仅列出 {listed} 个。输出目录={out.resolve()}")
    sys.exit(1 if download_fail else 0)


if __name__ == "__main__":
    main()
