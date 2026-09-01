# NJU LMS 课件下载器

复用你**已登录的浏览器会话**，从南京大学「智汇南雍」LMS 下载课程附件。不需要重新登录、不需要提取 cookie、不绕过任何签名/鉴权。

## 原理

1. 你用一个**登录过 LMS 的 Chrome/Edge**，以 `--remote-debugging-port` 启动（登录一次即可，会话有效期内都不用再登录）。
2. 本脚本用 playwright `connect_over_cdp` 连上它，在**登录态**下请求后端 API：
   - `GET /api/activities/<id>` → 枚举附件（`cc_license_references[].upload_id`）
   - `GET /api/uploads/<id>/preview` → 拿到**服务器签名直链**（短时效、自包含、无需 cookie）
3. 用标准库 `urllib` 下载；若直链过期(403)会自动重取签名再试。

## 依赖

- Python 3.8+
- `playwright`（仅用于连已登录浏览器；`connect_over_cdp` 复用现成浏览器，**不需要**额外 `playwright install chromium`）
- 下载走标准库 `urllib`，无 requests。

```bash
pip install -r requirements.txt
```

## 前置：启动一个已登录 LMS 的浏览器(带远程调试)

用你**登录过 LMS 的 Chrome profile** 起一个调试端口（命令行示例，改成你自己的路径/profile）：

```bash
# Chrome：把 <你的Chrome> 和 <你的profile目录> 换成实际路径；profile 选已登录 LMS 的那个
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9224 --user-data-dir="C:\Users\<你>\nju_chrome_profile"
```

> 关键是：这个 profile **必须在浏览器里登录过智汇南雍**，且启动参数带 `--remote-debugging-port`。启动后保持这个浏览器窗口开着。

## 用法

```bash
# 下载 1 个活动的全部附件
python crawler.py 41445

# 多个活动
python crawler.py 41445 38895

# 指定输出目录(默认 ./downloads)
python crawler.py 41445 --out B:/deeptutor/downloads

# 只列出附件、不下载
python crawler.py 41445 --no-download

# 指定 CDP 端点(默认依次尝试 9224、9223)
python crawler.py 41445 --cdp http://127.0.0.1:9224
```

## 说明 / 局限

- **必须已登录**：脚本会探测接口是否返回 JSON；若未登录会明确报错，提示先启动一个登录过的浏览器。
- **签名直链短时效**：批量下载若某文件 403，会自动对单个文件重取签名后重试。
- **活动 id** 指 LMS 活动链接 `.../learning-activity#/41445` 里的数字。
- **不绕过鉴权**：只在你自己的登录态里访问你的课程，不做签名伪造 / SSO 绕过。
