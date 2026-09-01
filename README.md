# NJU 智汇南雍 LMS 课件下载器

一个**复用你已登录浏览器会话**、从南京大学「智汇南雍」LMS 自动下载课程附件的小工具。

- **不用重新登录**：登录态存放在你的浏览器 profile 里，脚本连上去直接继承。
- **不提取 cookie、不伪造签名、不绕过 SSO**：只在你自己登录态下访问你自己的课程。
- **依赖少**：只有 `playwright` 一个包；下载用 Python 标准库 `urllib`。

---

## 目录

1. [它怎么工作的](#它怎么工作的)
2. [功能特性](#功能特性)
3. [项目结构](#项目结构)
4. [环境要求](#环境要求)
5. [一次性设置：起一个"已登录 LMS"的浏览器](#一次性设置)
6. [安装](#安装)
7. [日常用法](#日常用法)
8. [如何找到活动 ID](#如何找到活动-id)
9. [如何找到 CDP 调试端口](#如何找到-cdp-调试端口)
10. [常见报错与解决](#常见报错与解决)
11. [安全说明](#安全说明)

---

## 它怎么工作的

智汇南雍的文件下载被 webview 隐藏（`note-bene/aliyun-office-viewer`，`hidecmb=1`），页面上的"下载"按钮经常点不进去。但后端其实有一套**普通 REST 接口**，只要在**登录态**下就能拿到真正的、服务器签名的下载直链：

| 接口 | 作用 |
|---|---|
| `GET /api/activities/<活动ID>` | 返回活动详情，附件的 `upload_id` 藏在 `cc_license_references[].upload_id` 里 |
| `GET /api/uploads/<upload_id>` | 附件元数据（文件名、大小等） |
| `GET /api/uploads/<upload_id>/preview` | **关键**：返回一条 `url`，即服务器签名的直链 |

这条签名直链是**自包含**的（`…/download/file/<sha1>?timestamp=…&token=…&name=…`），**本身不需要 cookie**，但**有时效**（几分钟）。

所以流程是：

```
已登录浏览器(带 --remote-debugging-port)
        │  playwright.connect_over_cdp() 附着
        ▼
在登录态下 request /api/activities/<id>   → 枚举所有 upload_id
        ▼
逐个 request /api/uploads/<id>/preview   → 拿到签名直链
        ▼
用 urllib 下载（直链自包含，普通 HTTP 即可）
```

因为所有请求都发生在**你已登录的同一个浏览器上下文**里，后端就知道你是谁，接口正常返回。

---

## 功能特性

- ✅ **复用登录态**：连上你已登录的 Chrome/Edge，零重登。
- ✅ **多活动批量**：一次传多个活动 ID。
- ✅ **自动枚举全部附件**：递归扫描活动 JSON 里所有 `upload_id`。
- ✅ **登录检测**：先探测接口是否返回 JSON；未登录时明确报错并提示。
- ✅ **签名过期自动重取**：下载碰到 `403` 会为该文件重新取一条签名直链再试，最多重试 2 次。
- ✅ **单文件失败不中断**：某个附件下载失败，继续下一个，最后汇总。
- ✅ **多 CDP 端点容错**：默认依次尝试 `9224`、`9223`，也可用 `--cdp` 指定。
- ✅ **只列不下**：`--no-download` 只看有哪些文件。

---

## 项目结构

```
nju-lms-crawler/
├── crawler.py         # 主脚本（单文件，约 150 行）
├── requirements.txt   # 依赖清单：仅 playwright
├── README.md          # 本文件
└── .gitignore         # 忽略 __pycache__/ downloads/ 等
```

---

## 环境要求

- **Python 3.8+**
- **playwright**（`pip install -r requirements.txt`）
- 一个**登录过 LMS** 的 **Chrome 或 Edge**，且以 `--remote-debugging-port` 启动

> `connect_over_cdp` 是附着到**已经跑着的浏览器**，所以**不需要** `playwright install chromium`（不会额外下载 Playwright 内置的浏览器）。你连的是系统里已装的 Chrome/Edge。

---

## 一次性设置

**核心目标**：准备一个"登录过 LMS、并开了调试端口"的浏览器。之后每次都连它。

### 方案 A（推荐）：用一个"专属 profile"

给爬取单独开一个 Chrome profile，避免影响你日常使用，也避开「Chrome 151+ 默认 profile 禁远程调试」的限制。**在它里面登录一次 LMS，之后一劳永逸。**

```bash
# 把 <你的路径> 和 <专属profile目录> 换掉；--user-data-dir 要指向一个专门给爬虫用的目录
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9224 ^
  --user-data-dir="C:\Users\wjun\nju_chrome_profile"
```

- 弹出的 Chrome 里，访问 `https://lms.nju.edu.cn`，**登录一次**。
- **保持这个 Chrome 窗口开着**。会话有效期内（LMS 登录态通常持续一段时间）都不用再登录。
- 以后每次运行脚本前，先把这个 Chrome 起起来（或者让它一直开着）。

> 如果你的 LMS 登录在 **Edge** 里，同理用 `msedge.exe --remote-debugging-port=9223 --user-data-dir=<Edge专属目录>`，脚本默认也会尝试 9223。

### 方案 B：连你"正在用的默认浏览器"

可以，但有两个坑（不建议作为默认方案）：
1. **Chrome/Edge 151+ 默认 profile 禁远程调试**，连它 Chrome 会弹 **"Allow remote debugging?"** 权限窗，需要你手动点 Allow。
2. 会直接在你的真实浏览器里开新标签。

所以**推荐方案 A**（专属 profile，免弹窗、不打扰日常使用）。

### 关于 `--user-data-dir` 的要点

- 指到一个**新的、专属的、每次固定不变**的目录；**别指向你日常默认 profile**（会 profile 锁冲突 + Chrome 151 默认目录禁远程调试）。
- 目录可以不存在，Chrome 首启自动建；用**正斜杠**防 bash 转义：`--user-data-dir="C:/Users/wjun/nju_chrome_profile"`。
- **目录和端口每次要一致**，否则等于换了个新浏览器、要重新登录。
- 同一目录只能开**一个实例**；端口别被占用（换端口记得 `--cdp`）。
- 登录态会过期（SSO），过期后在该窗口重新登录一次即可；**别删目录里的 `Cookies` / `Login Data`**。

### 登录态是怎么被读取的

- **目录是给 Chrome 用的**：启动时 Chrome 把目录里的登录态载入“运行中的浏览器”。
- **爬虫不读目录、不解 cookie**：它用 `connect_over_cdp` 附着到那个已运行、已登录的浏览器，登录态经 CDP 连接继承过来。
- 所以只要浏览器开着且登录过，爬虫就自动带登录态；**不必把目录路径告诉脚本**，脚本只认 CDP 端口（默认 9224）。

---

## 安装

```bash
cd B:/nju-lms-crawler
pip install -r requirements.txt    # 只装 playwright
```

也可以手动装：

```bash
pip install playwright
```

---

## 日常用法

```bash
cd B:/nju-lms-crawler

# 1. 下载一个活动的全部附件（默认输出到 ./downloads）
python crawler.py 41445

# 2. 多个活动一次下载
python crawler.py 41445 38895

# 3. 指定输出目录
python crawler.py 41445 --out B:/deeptutor/downloads

# 4. 只列出附件，不下载
python crawler.py 41445 --no-download

# 5. 指定 CDP 端点（默认依次试 9224、9223）
python crawler.py 41445 --cdp http://127.0.0.1:9224

# 6. 完整参数示例
python crawler.py 38895 41445 --cdp "http://127.0.0.1:9224,http://127.0.0.1:9223" --out B:/deeptutor/downloads
```

### 命令行参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `activities`（位置参数） | 一个或多个活动 ID | 必填 |
| `--out` / `-o` | 输出目录 | `./downloads` |
| `--cdp` | CDP 端点，多端点多逗号分隔 | `http://127.0.0.1:9224,http://127.0.0.1:9223` |
| `--no-download` | 只列出附件、不下载 | 关闭 |

### 运行输出示例

```text
[连接] 已连上并登录: http://127.0.0.1:9224
[活动 41445] 发现 1 个附件:
   - [598229] Experiments_on_Loongson.pdf
  ✅ Experiments_on_Loongson.pdf  5476072 字节 -> downloads\Experiments_on_Loongson.pdf

完成：下载 1 个，失败 0 个，仅列出 0 个。输出目录=B:\nju-lms-crawler\downloads
```

---

## 如何找到活动 ID

打开 LMS 的课程活动页，看地址栏 URL 里的数字：

```
https://lms.nju.edu.cn/course/12287/learning-activity#/41445
                                                          ^^^^^ 这就是活动 ID
```

URL 末尾 `#/` 后面的数字就是活动 ID（如上面的 `41445`）。把这个数字传给脚本即可。

---

## 如何找到 CDP 调试端口

脚本默认尝试 `9224`、`9223`。如果你改了端口，需用 `--cdp` 指定。

快速确认某个端口是否可用：

```bash
curl.exe -s http://127.0.0.1:9224/json/version
```

如果返回了浏览器版本 JSON（如 `"Browser": "Chrome/151..."`），说明这个端口可连且远程调试已开启。若连接被拒，先确认浏览器是用 `--remote-debugging-port=<端口>` 启动的。

---

## 常见报错与解决

### ❌ "未安装 playwright"
```
❌ 未安装 playwright。请运行: pip install -r requirements.txt
```
运行 `pip install -r requirements.txt`，或用当前 Python 环境 `pip install playwright`。

### ❌ "无法连接任何 CDP 浏览器"
```
❌ 无法连接任何 CDP 浏览器。请先启动已登录 LMS 的 Chrome/Edge（--remote-debugging-port）再试。
```
说明指定/默认的端口上**没有一个在跑且开了远程调试**的浏览器。按[一次性设置](#一次性设置)用 `--remote-debugging-port` 启动 Chrome/Edge 再运行。

### ❌ "似乎未登录 LMS"
```
[跳过] http://127.0.0.1:9224: 已连接但似乎未登录 LMS
```
端口虽然能连，但该浏览器里**没有 LMS 登录会话**。在这个浏览器里访问 `https://lms.nju.edu.cn` 登录一次，或换一个已登录的 profile / 端口。

### ⚠️ "直链失效(403)，重取签名"
```
↻ xxx.pdf: 直链失效(403)，重取签名...
```
签名直链有时效（几分钟）。脚本会自动重新 fetch `preview` 接口拿一条新链接再试。若连续失败，可能是登录态过期，需重新登录。

### ⚠️ "未发现可下载附件"
```
[信息] 活动 41445: 未发现可下载附件
```
该活动确实没有附件，或附件结构变了。用 `--no-download` 先看看接口返回了什么。

### Chrome 弹 "Allow remote debugging?"
这是 Chrome 对"附着到未开远程调试的浏览器"的**安全确认**。若你按方案 A（专属 profile + `--user-data-dir`）启动，通常不会弹；若用默认 profile 才容易弹。点击 **Allow** 即可，或用专属 profile 方案避免。

---

## 安全说明

- **只在你自己的登录态里操作**：脚本连的是**你自己登录过的浏览器**，调的是**你自己的接口**，下载的也是你自己课程的文件。没有伪造签名、没有绕过 SSO、没有抓别人的数据。
- **不读取/导出凭证**：脚本不做 cookie 提取，也不把任何登录信息写进文件或上传。
- 签名直链有时效且含 `token`，属于该文件的一次性下载凭据；脚本只在内存里处理并立即用 `urllib` 下载，落地的是最终文件。

---

## 许可

个人学习/使用工具。如获他人使用，请遵守学校相关规定，仅下载你有权访问的课程资料。
