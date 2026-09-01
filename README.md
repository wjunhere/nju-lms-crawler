# NJU 智汇南雍 LMS 课件下载器

复用你**已登录的浏览器会话**，从南京大学「智汇南雍」LMS 自动下载课程附件。

- **不用重新登录**：登录态在你的浏览器 profile 里，脚本连上去直接继承。
- **不提取 cookie、不绕过 SSO**：只在你自己登录态下访问你自己的课程。
- **依赖少**：仅 `playwright`；下载用标准库 `urllib`。

---

## 快速开始

三步就能用。

**1. 装依赖**

```bash
cd B:/nju-lms-crawler
pip install -r requirements.txt
```

**2. 起一个「登录过 LMS 并开了调试端口」的浏览器**

```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9224 ^
  --user-data-dir="C:/Users/wjun/nju_chrome_profile"
```

弹出的窗口里登录一次 `https://lms.nju.edu.cn`，然后**保持它开着**。✔️ 理解细节看[一次性设置](#一次性设置)。

**3. 跑脚本**

```bash
python crawler.py 41445
```

`/course/12287/learning-activity#/41445` 里的 `41445` 就是活动 ID。默认下载到 `./downloads`。

---

## 它怎么工作

LMS 的文件下载被 webview 隐藏（`note-bene/aliyun-office-viewer`、`hidecmb=1`），页面上"下载"按钮常点不进去。但后端有**普通 REST 接口**，在**登录态**下就能拿到真正的签名直链：

| 接口 | 作用 |
|---|---|
| `GET /api/activities/<活动ID>` | 活动详情，附件 `upload_id` 藏在 `cc_license_references[].upload_id` |
| `GET /api/uploads/<upload_id>` | 附件元数据（文件名/大小） |
| `GET /api/uploads/<upload_id>/preview` | **关键**：返回服务器签名的 `url` 直链 |

签名直链是**自包含**的（`…/download/file/<sha1>?timestamp=…&token=…&name=…`），本身**不需要 cookie**，但**有时效**（几分钟）。

```
已登录浏览器(--remote-debugging-port)
        │ playwright.connect_over_cdp() 附着
        ▼
在登录态下 /api/activities/<id>  → 枚举所有 upload_id
        ▼
逐个 /api/uploads/<id>/preview → 拿到签名直链
        ▼
urllib 下载（直链自包含，普通 HTTP 即可）
```

所有请求都在**你已登录的同一个浏览器上下文**里发，后端就知道你是谁，接口正常返回。

---

## 一次性设置

**目标**：准备一个「登录过 LMS、且开了调试端口」的浏览器，之后每次都连它。

### 方案 A：专属 profile（推荐）

单独开一个 Chrome profile，避开「Chrome 151+ 默认 profile 禁远程调试」，也不打扰日常使用。

```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9224 ^
  --user-data-dir="C:/Users/wjun/nju_chrome_profile"
```

- 弹出的窗口里登录**一次** `https://lms.nju.edu.cn`。
- **保持它开着**；会话有效期内不用再登。
- LMS 登录在 Edge 就换成 `msedge.exe`（端口 9223，脚本默认也尝试 9223）。

### 方案 B：连你正在用的默认浏览器

可以，但两个坑（不建议）：① Chrome/Edge 151+ 默认 profile 禁远程调试，会弹 **"Allow remote debugging?"**；② 会在你真实浏览器里开新标签。

### `--user-data-dir` 要点（用方案 A 必看）

- 指向**新的、专属的、每次固定不变**的目录；**别指向你日常默认 profile**（profile 锁冲突 + 默认目录禁远程调试）。
- 目录可不存在，Chrome 首启自动建；用**正斜杠**防 bash 转义。
- **目录和端口每次一致**，否则等于换新浏览器、要重新登录。
- 同一目录只能开**一个实例**；端口别被占用（换端口记得 `--cdp`）。
- 登录态会过期（SSO），过期后在该窗口重登一次；**别删**目录里的 `Cookies` / `Login Data`。

### 登录态是怎么被读取的

- **目录是给 Chrome 用的**：启动时 Chrome 把登录态载入「运行中的浏览器」。
- **爬虫不读目录、不解 cookie**：它用 `connect_over_cdp` 附着到那个已运行、已登录的浏览器，登录态经 CDP 连接继承。
- 所以只要浏览器开着且登录过，就自动带登录态；**不必把目录路径告诉脚本**，脚本只认 CDP 端口（默认 9224）。

---

## 安装

```bash
pip install -r requirements.txt   # 只装 playwright
```

> `connect_over_cdp` 附着到**已跑着的浏览器**，所以**不需要** `playwright install chromium`。

---

## 日常用法

```bash
cd B:/nju-lms-crawler
python crawler.py 41445                       # 下载一个活动的全部附件
python crawler.py 41445 38895                 # 多个活动
python crawler.py 41445 --out B:/deeptutor/downloads   # 指定输出目录
python crawler.py 41445 --no-download         # 只列出附件、不下载
python crawler.py 41445 --cdp http://127.0.0.1:9224    # 指定 CDP 端点
```

### 命令行参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `activities`（位置参数） | 一个或多个活动 ID | 必填 |
| `--out` / `-o` | 输出目录 | `./downloads` |
| `--cdp` | CDP 端点，多个用逗号分隔 | `http://127.0.0.1:9224,http://127.0.0.1:9223` |
| `--no-download` | 只列出附件、不下载 | 关闭 |

### 运行输出

```text
[连接] 已连上并登录: http://127.0.0.1:9224
[活动 41445] 发现 1 个附件:
   - [598229] Experiments_on_Loongson.pdf
  ✅ Experiments_on_Loongson.pdf  5476072 字节 -> downloads\Experiments_on_Loongson.pdf

完成：下载 1 个，失败 0 个，仅列出 0 个。输出目录=B:\nju-lms-crawler\downloads
```

---

## 参考：怎么找 ID 和端口

### 活动 ID

`https://lms.nju.edu.cn/course/12287/learning-activity#/41445` 里 `#/` **后面的数字**（`41445`）。

### CDP 端口是否可用

```bash
curl.exe -s http://127.0.0.1:9224/json/version
```

返回浏览器版本 JSON（如 `"Browser": "Chrome/151..."`）即可连；连接被拒说明浏览器没带 `--remote-debugging-port` 启动。

---

## 功能特性

- ✅ **复用登录态**：连上已登录的 Chrome/Edge，零重登
- ✅ **多活动批量**：一次传多个活动 ID
- ✅ **自动枚举全部附件**：递归扫描活动 JSON 里所有 `upload_id`
- ✅ **登录检测**：接口不返回 JSON 时明确报"未登录"
- ✅ **签名过期自动重取**：下载遇 `403` 为该文件重新取直链，最多重试 2 次
- ✅ **单文件失败不中断**：某个失败继续下一个，最后汇总
- ✅ **多 CDP 端点容错**：默认依次试 `9224`、`9223`
- ✅ **只列不下**：`--no-download`

---

## 常见问题

### ❌ 未安装 playwright
```
❌ 未安装 playwright。请运行: pip install -r requirements.txt
```
`pip install -r requirements.txt`，或用当前 Python 环境 `pip install playwright`。

### ❌ 无法连接任何 CDP 浏览器
```
❌ 无法连接任何 CDP 浏览器。请先启动已登录 LMS 的 Chrome/Edge（--remote-debugging-port）再试。
```
端口上没有在跑且开了远程调试的浏览器。按[一次性设置](#一次性设置)用 `--remote-debugging-port` 启动再运行。

### ❌ 似乎未登录 LMS
```
[跳过] http://127.0.0.1:9224: 已连接但似乎未登录 LMS
```
端口能连但这个浏览器里没有 LMS 会话。在它里面登录一次 `https://lms.nju.edu.cn`，或换已登录的 profile / 端口。

### ⚠️ 直链失效（403），重取签名
```
↻ xxx.pdf: 直链失效(403)，重取签名...
```
签名有时效，脚本会自动重取重试。连续失败多为登录态过期，重新登录即可。

### ⚠️ 未发现可下载附件
```
[信息] 活动 41445: 未发现可下载附件
```
该活动确实没有附件，或结构变了。用 `--no-download` 先看接口返回。

### Chrome 弹 "Allow remote debugging?"
按方案 A（专属 profile + `--user-data-dir`）通常不会弹；用默认 profile 才容易弹。点 **Allow**，或改用方案 A。

---

## 安全说明

- **只在你自己的登录态里操作**：连的是你登录过的浏览器、调你自己的接口、下你自己课程的文件。无伪造签名、无绕过 SSO、无抓取他人数据。
- **不读取/导出凭证**：不做 cookie 提取，不把登录信息写文件或上传。
- 签名直链有时效且含 `token`，属一次性凭据；脚本只在内存里处理并立即 `urllib` 下载，落地的是最终文件。

---

## 许可

个人学习/使用工具。如转让他人使用，请遵守学校相关规定，仅下载你有权访问的课程资料。
