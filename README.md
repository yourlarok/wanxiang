# 万相 Wanxiang

万相是一个由 Agent 驱动的开放式可视化后台服务。它把文本或截图转换为专业数据图、三维教学图、可交互微场景、SVG/HTML 视觉解释、关系图或公式产物。

万相不是桌面 App，也不依赖固定知识模板。通用大模型负责理解问题并生成紧凑的声明式 VizSpec，Matplotlib 等专业工具负责确定性渲染，MCP 提供扩展能力，Verifier 负责协议与安全校验。

## 核心特点

- **声明式专业图表**：通用 PlotSpec 支持折线、散点、柱状、三维柱体、体素网格、曲面和最多 16 个子图；模型只提供数据与视觉编码，不提交可执行代码。
- **开放产物**：支持 HTML、内联 SVG、CSS 和本地 JavaScript，不受固定知识领域限制。
- **Agent 工具循环**：模型可以按需获取风格指南、调用外部 MCP 工具，再创建视觉产物。
- **MCP 可扩展**：通过 `VIS_MCP_SERVERS` 动态发现其他 MCP 服务。
- **风格与语义分离**：内置 textbook、blueprint、minimal、chalk 四套视觉风格。
- **安全沙箱**：默认禁止外部资源、网络请求、存储、内联事件和动态执行。
- **两种使用方式**：HTTP 后台服务，或由 Agent 直接启动的 stdio MCP 服务。
- **跨平台**：启动器支持 macOS 和 Windows，自动准备隔离 Python 环境。

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

### 4. 速度与 JEV 配置

默认快速路径只进行一次低强度模型规划，跳过外部 MCP 发现，并使用预热的本地 Matplotlib/SVG 渲染。数据与空间图形优先生成 PlotSpec，简单示意才使用六图元 SceneSpec：

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

### 5. 调用 HTTP API

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

| 风格 | 适用场景 |
| --- | --- |
| `textbook` | 教材式卡片、嵌套框、直观例子与短句解释 |
| `blueprint` | 技术结构、坐标、构造关系与精确标注 |
| `minimal` | 留白、单一强调色和低信息噪声 |
| `chalk` | 黑板推导、圈注和分步解释 |

风格只决定视觉语言，不限制 Agent 选择什么图形。

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

- 复杂开放 HTML 的首次生成可能需要较长时间，取决于模型和工具调用次数。
- 启动器按 Windows 与 macOS 设计；不同企业安全策略仍可能影响 MCP 子进程。
- 外部 MCP 工具的质量、权限和可用性由各服务自身决定。

## License

MIT
