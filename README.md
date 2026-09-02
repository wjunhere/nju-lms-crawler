# 高校课程 LMS 课件下载器

> **⚠️ 使用声明（请先阅读）**
>
> 本工具仅供**本人教学内部·个人学习自用**，**仅用于下载你有合法访问权的课程资料**。
> **禁止**用于：任何传播、转售、商业用途；访问他人无权访问的数据；批量抓取造成系统负担。
> 使用本工具产生的一切后果由使用者自行承担，请遵守你所在学校及目标平台的**用户协议与相关管理规定**。
> 本工具**不存储、导出任何登录凭证**，不绕过身份认证，仅在你已登录的合法会话内工作。

复用你**已登录的浏览器**会话，从校内课程 LMS 自动下载你**有权访问的课程附件**。

- **不用重新登录**：登录态在你的浏览器 profile 里，脚本连上去直接继承。
- **不提取 cookie、不绕过 SSO**：只在你自己登录态下访问你自己的课程。
- **依赖少**：仅 `playwright`；下载用标准库 `urllib`。

---

## 快速开始

三步就能用。

**1. 装依赖**

```bash
cd <你的项目目录>
pip install -r requirements.txt
```

**2. 起一个「登录过 LMS 并开了调试端口」的浏览器**

```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9224 --user-data-dir="C:/Users/<你的用户名>/lms_chrome_profile"
```

弹出的窗口里登录一次你的课程 LMS，然后**保持它开着**。✔️ 理解细节看[一次性设置](#一次性设置)。

**3. 跑脚本**

```bash
python crawler.py --base-url https://your-lms.example 41445
```

把 `--base-url` 换成你已登录的课程 LMS 地址，数字换成你要下载的活动编号（如你课程详情页 `#/` 后看到的 `41445`）。默认下载到 `./downloads`。

---

## 它怎么工作

课程附件在页面上往往无法直接下载。本脚本复用你**已登录**的浏览器会话，在**登录态下**让后端返回**服务器签发的、带时效的临时直链**，再用标准库下载。**它不伪造签名、不提取 cookie、不绕过身份认证**——所有请求都是后端在识别出"你"之后正常返回的。

```
已登录浏览器（开启 --remote-debugging-port）
        │ playwright.connect_over_cdp() 附着
        ▼
在登录态下枚举当前课程活动下的附件
        ▼
获取后端签发的临时直链（有时效、无需 cookie）
        ▼
urllib 下载（临时直链自包含，普通 HTTP 即可）
```

关键点：**脚本对自己无权访问或未登录的内容不做任何越权尝试**，接口返回"未登录/不可访问"时会明确提示并跳过。

---

## 一次性设置

**目标**：准备一个「登录过 LMS、且开了调试端口」的浏览器，之后每次都连它。

### 方案 A：专属 profile（推荐）

单独开一个 Chrome profile，避开「Chrome 151+ 默认 profile 禁远程调试」，也不打扰日常使用。

> 下面为**单行**命令，PowerShell / cmd 可直接粘贴运行；若想分行，PowerShell 用反引号(backtick)续行，cmd 用 `^` 续行。

```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9224 --user-data-dir="C:/Users/<你的用户名>/lms_chrome_profile"
```

- 弹出的窗口里登录**一次**你的课程 LMS。
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
cd <你的项目目录>
python crawler.py --base-url https://your-lms.example 41445                       # 下载一个活动的全部附件
python crawler.py --base-url https://your-lms.example 41445 38895                 # 多个活动
python crawler.py --base-url https://your-lms.example 41445 --out <你的输出目录>   # 指定输出目录
python crawler.py --base-url https://your-lms.example 41445 --no-download         # 只列出附件、不下载
python crawler.py --base-url https://your-lms.example 41445 --cdp http://127.0.0.1:9224    # 指定 CDP 端点
```

### 命令行参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `--base-url` | 你的课程 LMS 站点地址（必需） | 无（必填） |
| `activities`（位置参数） | 一个或多个活动编号 | 必填 |
| `--out` / `-o` | 输出目录 | `./downloads` |
| `--cdp` | CDP 端点，多个用逗号分隔 | `http://127.0.0.1:9224,http://127.0.0.1:9223` |
| `--no-download` | 只列出附件、不下载 | 关闭 |

### 运行输出

```text
[连接] 已连上并登录: http://127.0.0.1:9224
[活动 41445] 发现 1 个附件:
   - [598229] Experiments_on_Loongson.pdf
  ✅ Experiments_on_Loongson.pdf  5476072 字节 -> downloads\Experiments_on_Loongson.pdf

完成：下载 1 个，失败 0 个，仅列出 0 个。输出目录=<你的输出目录>
```

---

## 参考：怎么找活动编号和端口

### 活动编号

在课程详情页地址里 `#/` **后面的数字**（例如某个活动是 `41445`）。具体站点地址请以你已登录的 LMS 页面为准。

### CDP 端口是否可用

```bash
curl.exe -s http://127.0.0.1:9224/json/version
```

返回浏览器版本 JSON（如 `"Browser": "Chrome/151..."`）即可连；连接被拒说明浏览器没带 `--remote-debugging-port` 启动。

---

## 功能特性

- ✅ **复用登录态**：连上已登录的 Chrome/Edge，零重登
- ✅ **多活动批量**：一次传多个活动编号
- ✅ **自动枚举全部附件**：递归扫描活动返回数据里的所有附件 ID
- ✅ **登录检测**：接口不返回数据时明确报"未登录"
- ✅ **临时直链失效自动重取**：下载遇 `403` 会为该文件重新获取有效直链，最多重试 2 次
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
端口能连但这个浏览器里没有 LMS 会话。在它里面登录一次你的课程 LMS，或换已登录的 profile / 端口。

### ⚠️ 直链失效（403），重取直链
```
↻ xxx.pdf: 直链失效(403)，重取签名...
```
临时直链有时效，脚本会自动重取重试。连续失败多为登录态过期，重新登录即可。

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
- **仅限个人学习自用**：下载的课程资料为受版权保护内容，请勿再转发、分享、上传或转让他人，避免侵犯著作权。
- 临时直链有时效且含一次性的 `token`；脚本只在内存里处理并立即 `urllib` 下载，落地的是最终文件。

---

## 许可

**个人学习自用工具。** 请仅在你本人有权访问的课程资料范围内使用，并遵守所在学校及相关平台的用户协议与规定。

- 本工具**不授予**任何人对他人无权访问数据的访问权，也不支持越权抓取。
- 下载的课件等受版权保护内容，请勿用于传播、转售或任何商业用途。
- 使用本工具即视为同意并接受文首的《使用声明》。
