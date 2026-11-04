# 万相 Wanxiang

万相是一个由 Agent 驱动的陪伴学习与开放式可视化后台服务。它把文本或截图转换为专业数据图、三维教学图、可交互微场景、SVG/HTML 视觉解释、关系图或公式产物。

万相没有传统桌面主窗口，也不依赖固定知识模板。通用大模型负责理解问题并生成紧凑的声明式 VizSpec，Matplotlib 等专业工具负责确定性渲染，MCP 提供扩展能力，Verifier 负责协议与安全校验。

## 核心特点

- **原地陪伴学习**：无主窗口 companion 支持全局快捷键框选、框外静态快照、按需上下文判断和毛玻璃学习浮层。
- **声明式专业图表**：通用 PlotSpec 支持折线、散点、柱状、三维柱体、体素网格、曲面和最多 16 个子图；模型只提供数据与视觉编码，不提交可执行代码。
- **互动艺术设计**：支持编辑式网格、主视觉构图、曲线与路径、图层、渐变、阴影和入场编排；开放 HTML、SVG、Canvas 与本地 JavaScript 可生成按钮、滑块和参数驱动的互动微场景。
- **Agent 工具循环**：模型可以按需获取风格指南、调用外部 MCP 工具，再创建视觉产物。
- **MCP 可扩展**：通过 `VIS_MCP_SERVERS` 动态发现其他 MCP 服务。
- **风格与语义分离**：内置动漫、报刊、水彩、像素、教材、蓝图、极简和黑板八套风格，统一作用于 HTML、SVG 与 Matplotlib。
- **安全沙箱**：默认禁止外部资源、网络请求、存储、内联事件和动态执行。
- **三种使用方式**：原地 companion、HTTP 后台服务，或由 Agent 直接启动的 stdio MCP 服务。
- **跨平台**：启动器和 companion 按 macOS/Windows 设计，自动准备隔离 Python 环境。

## 工作原理

```text
文本 / 截图
    ↓
理解问题与教学意图，选择专业工具
    ↓
生成声明式 PlotSpec / SceneSpec，或按需调用 MCP
    ↓
Matplotlib / SVG / HTML 确定性渲染
    ↓
协议、安全和完整性校验
    ↓
返回可渲染的 Artifact JSON 与分阶段耗时
```

万相不会把所有内容都转成关系图。函数图像、三维结构、几何模拟、嵌套结构、交互实验和自定义 SVG 都可以由 Agent 自然生成。

## 环境要求

- Node.js 20+
- Python 3.11+
- 可选：支持 OpenAI Chat Completions 的多模态模型

NVM 只负责管理 Node.js 版本；服务启动使用 `npx`。

## 快速启动

### 1. 配置模型

```bash
export VIS_AGENT_BASE_URL=https://api.deepseek.com/v1
export VIS_AGENT_API_KEY=你的密钥
export VIS_AGENT_MODEL=deepseek-flash
export VIS_AGENT_REASONING_EFFORT=low
```

也可以复制 `.env.example` 为 `.env` 后填写。`.env` 已被 Git 忽略。

未配置模型时，HTTP 服务会进入本地降级模式，只返回原始内容视图；截图理解需要配置多模态模型。

### 2. 启动 HTTP 服务

```bash
npx -y github:yourlarok/wanxiang start
```

默认监听 `127.0.0.1:8765`。指定端口：

```bash
npx -y github:yourlarok/wanxiang start --port 9000
```

首次启动会在 `~/.wanxiang/.venv` 创建隔离 Python 环境并安装依赖。可通过 `WANXIANG_HOME` 修改数据目录。

检查环境：

```bash
npx -y github:yourlarok/wanxiang doctor
```

### 3. 打开可视化预览

启动后访问 `http://127.0.0.1:8765/preview`。页面支持文本输入、风格选择以及模型、渲染和总耗时显示，开放 HTML 中的按钮与滑块可以直接操作。

### 4. 快捷键框选陪伴学习

保持 HTTP 服务运行，再启动无主窗口 companion：

```bash
npx -y github:yourlarok/wanxiang companion
```

在任意页面或文档中按 `⌘⇧X`（macOS）或 `Ctrl+Shift+X`（Windows）进入框选，再**按住左键拖动**。macOS 也支持 `Ctrl+Shift+X`。松开后，浮层会在原位置附近展开，先检查框内内容，再由 Agent 判断是否需要框外上下文，最后按内容类型、解释长度和屏幕边界动态调整尺寸与布局。拖动浮层标题栏可移动位置，拖动四边或四角可缩放；再次进入框选不会自动关闭已有浮层，结果返回也不会覆盖用户手动调整的位置和尺寸。框选时按 `Esc` 取消，结果浮层可按 `Esc` 或右上角 `×` 关闭；普通右键保留系统原行为，不会打开传统应用主窗口。

companion 默认每 5 秒读取一次当前屏幕的静态快照，只保存在内存，并在框选期间暂停更新。快照不会写入磁盘；但发起学习时，框选图片和用于判断的框外快照会随请求发送给本地服务，并由服务交给所配置的多模态模型。不要把此模式用于不允许上传到模型服务的敏感内容。

macOS 首次使用需要允许屏幕录制，以及辅助功能或输入监控权限。可执行权限预检：

```bash
npx -y github:yourlarok/wanxiang companion --check
```

默认使用精致像素风：等待时显示像素小狗与动态省略号，结果浮层采用像素玻璃、阶梯边框、硬阴影和像素图表。可通过 `WANXIANG_STYLE=anime` 等环境变量切换其他浮层与图表风格。companion 使用 Qt Essentials/Addons、WebEngine 和 pynput；WebEngine 在后台预热，用于在浮层内运行互动 SVG、Canvas 与本地 JavaScript，不加载外部资源。

### 5. 速度与 JEV 配置

默认快速路径只进行一次低强度模型规划，跳过外部 MCP 发现，并使用预热的本地 Matplotlib、SVG 与互动 HTML 渲染。数据与空间图形优先生成 PlotSpec；自定义插图使用带图层、路径和动效的 SceneSpec；需要自由构图或参数交互时由 Agent 选择开放 HTML：

```bash
export VIS_AGENT_MODEL=deepseek-flash
export VIS_PLANNER_REASONING_EFFORT=low
export VIS_FAST_MODE=true
```

完整开放 Agent/MCP 模式可设置 `VIS_FAST_MODE=false`。JEV 默认不参与每次请求；启用后只对开放 HTML、证据不足或校验异常结果进行评审：

```bash
export VIS_JEV_ENABLED=true
export VIS_JEV_MODEL=deepseek-flash
export VIS_JEV_REVIEW_MODE=uncertain
export VIS_JEV_THRESHOLD=0.72
```

高置信结果直接返回，低置信结果才升级完整 Agent。缓存命中时通常毫秒级返回；首次生成的速度仍主要取决于远程规划模型。Artifact 的 `timings_ms` 分别记录 `model`、`render` 和 `total`，用于区分推理与本地渲染瓶颈。

### 6. 调用 HTTP API

```bash
curl http://127.0.0.1:8765/health

curl -X POST http://127.0.0.1:8765/v2/visualizations \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "张量形状为(2,3)，分别说明 axis=0、1、2 插入维度是什么意思",
    "preference": "interactive",
    "style": "textbook"
  }'
```

返回示例结构：

```json
{
  "version": "2.0",
  "artifact_type": "html",
  "title": "张量插入维度的三个位置",
  "explanation": "通过嵌套框理解新增长度为 1 的轴。",
  "style": "textbook",
  "html": {
    "body": "...",
    "css": "...",
    "javascript": "...",
    "document": "<!doctype html>..."
  },
  "verification": {
    "passed": true,
    "checks": ["HTML/CSS/JavaScript 安全校验通过"]
  }
}
```

`html.document` 可以在无同源权限的 iframe 沙箱中直接渲染：

```html
<iframe sandbox="allow-scripts" srcdoc="..."></iframe>
```

不要给生成的 iframe 添加 `allow-same-origin`，也不要关闭其内容安全策略。

陪伴学习使用 `POST /v2/learning`。请求在普通可视化字段之外支持 `context_image_base64`、`context_text`、`context_mode` 和 `selection`；响应包含 `artifact` 与 `overlay`。Artifact 中的 `context_used`、`context_reason` 记录模型是否真正使用框外信息，`overlay` 给出动态计算的全局位置和尺寸。

## 由 Agent 通过 MCP 使用

启动 stdio MCP 服务：

```bash
npx -y github:yourlarok/wanxiang mcp
```

MCP 客户端配置示例：

```json
{
  "mcpServers": {
    "wanxiang": {
      "command": "npx",
      "args": ["-y", "github:yourlarok/wanxiang", "mcp"]
    }
  }
}
```

提供的工具：

- `visualize`：根据文本或 base64 图片生成视觉产物。
- `list_visual_styles`：获取视觉风格和设计令牌。

模型环境变量需要在启动 MCP 服务的环境中提供。

## 接入其他 MCP 工具

`VIS_MCP_SERVERS` 是 JSON 数组。以下示例接入 Generative UI MCP：

```bash
export VIS_MCP_SERVERS='[{"name":"generative-ui","command":"npx","args":["-y","generative-ui-mcp"]}]'
```

启动后，万相会动态发现外部工具，并以 `mcp__服务名__工具名` 的形式提供给 Agent。Agent 可以先获取设计规范或计算结果，再调用万相的 `create_*_artifact` 工具生成统一产物。

外部 MCP 服务应由你自行审核；万相不会默认安装未经确认的第三方服务。

## 视觉风格

| 风格 | 视觉语言 |
| --- | --- |
| `anime` | 动漫赛璐璐配色、粉蓝高光、深色描边与圆润形体 |
| `newspaper` | 暖纸色、衬线字体、黑红标题与报刊版式线 |
| `watercolor` | 水彩纸感、青绿陶土色、手写字体与柔和边界 |
| `pixel` | 街机深色底、硬边方块、等宽字体与像素式阴影 |
| `textbook` | 教材式卡片、嵌套框、直观例子与短句解释 |
| `blueprint` | 技术结构、坐标、构造关系与精确标注 |
| `minimal` | 留白、单一强调色和低信息噪声 |
| `chalk` | 黑板推导、圈注和分步解释 |

风格只决定视觉语言，不限制 Agent 选择什么图形。颜色、字体、圆角、描边、阴影、纸张纹理和 Matplotlib 图内样式会统一继承主题；不加载外部字体或图片。

## 安全边界

- HTML 不允许 `script`、`iframe`、外部资源和内联事件。
- CSS 不允许 `@import`、`url()` 和表达式。
- JavaScript 不允许网络、存储、动态执行、访问宿主页面。
- PlotSpec 只接受经过 Pydantic 校验的声明式数据，禁止额外代码字段，并限制数据量、面板数和三维网格规模；不会执行模型生成的 Python。
- 产物必须包含简明解释，关系图必须验证节点与边引用。
- 模型密钥只从环境变量或本地 `.env` 读取，不写入 Artifact。

当前 Verifier 以协议、安全和结构校验为主；视觉截图评审与教学效果评分仍需后续增强。

## 本地开发

```bash
git clone https://github.com/yourlarok/wanxiang.git
cd wanxiang
npm ci
npm run doctor
npm start
```

直接启动 Python 服务：

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8765
```

## 当前限制

- 复杂开放 HTML 与双图陪伴学习的首次生成可能需要较长时间，取决于模型、图片尺寸和工具调用次数；框外快照会在 companion 中缩放后传输。
- macOS 使用 Quartz 截图并处理 Retina 像素比；Windows 使用 Qt 截图。快捷键监听、浮层与权限流程已在 macOS 实测，Windows 仍需在目标机器验证。
- 启动器按 Windows 与 macOS 设计；不同企业安全策略仍可能影响全局输入监听和 MCP 子进程。
- 外部 MCP 工具的质量、权限和可用性由各服务自身决定。

## License

MIT
