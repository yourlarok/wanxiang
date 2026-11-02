#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const serverDir = path.join(root, "server");
const requirements = path.join(serverDir, "requirements.txt");
const home = process.env.WANXIANG_HOME ?? path.join(os.homedir(), ".wanxiang");
const windows = process.platform === "win32";
const python = path.join(home, ".venv", windows ? "Scripts" : "bin", windows ? "python.exe" : "python");
const command = process.argv[2] ?? "help";
const quietSetup = command === "mcp";

function runSetup(args) {
  const result = spawnSync(args.command, args.args, {
    cwd: args.cwd ?? home,
    env: process.env,
    stdio: quietSetup ? ["ignore", "ignore", "inherit"] : ["ignore", "inherit", "inherit"],
  });
  if (result.error || result.status !== 0) {
    throw new Error(`命令执行失败：${args.command} ${args.args.join(" ")}`, { cause: result.error });
  }
}

function ensurePython() {
  mkdirSync(home, { recursive: true });
  if (!existsSync(python)) {
    const candidates = process.env.WANXIANG_PYTHON ? [process.env.WANXIANG_PYTHON] : windows ? ["python", "py"] : ["python3", "python"];
    let created = false;
    for (const candidate of candidates) {
      const result = spawnSync(candidate, ["-m", "venv", path.join(home, ".venv")], {
        stdio: quietSetup ? ["ignore", "ignore", "ignore"] : ["ignore", "inherit", "inherit"],
      });
      if (!result.error && result.status === 0) {
        created = true;
        break;
      }
    }
    if (!created) throw new Error("未找到 Python 3.11+，请先安装 Python 并加入 PATH。");
  }
  const stamp = path.join(home, ".requirements-sha256");
  const digest = createHash("sha256").update(readFileSync(requirements)).digest("hex");
  if (!existsSync(stamp) || readFileSync(stamp, "utf8") !== digest) {
    runSetup({ command: python, args: ["-m", "pip", "install", "-r", requirements] });
    writeFileSync(stamp, digest);
  }
}

function launch(args) {
  ensurePython();
  const child = spawn(python, args, {
    cwd: serverDir,
    env: process.env,
    stdio: "inherit",
  });
  child.on("error", (error) => {
    console.error(`万相启动失败：${error.message}`);
    process.exitCode = 1;
  });
  child.on("exit", (code, signal) => {
    process.exitCode = code ?? (signal ? 1 : 0);
  });
  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.on(signal, () => child.kill(signal));
  }
}

function help() {
  console.log(`万相 Wanxiang · 开放式可视化 Agent 服务\n\n用法：\n  wanxiang start [--port 8765]  启动 HTTP 服务\n  wanxiang mcp                 通过 stdio MCP 由 Agent 调用\n  wanxiang doctor              检查运行环境\n\n环境变量：\n  VIS_AGENT_BASE_URL / VIS_AGENT_API_KEY / VIS_AGENT_MODEL\n  VIS_MCP_SERVERS / WANXIANG_HOME / WANXIANG_PYTHON`);
}

try {
  if (command === "start") {
    const portIndex = process.argv.indexOf("--port");
    const port = portIndex >= 0 ? process.argv[portIndex + 1] : process.env.PORT ?? "8765";
    launch(["-m", "uvicorn", "app.main:app", "--host", process.env.HOST ?? "127.0.0.1", "--port", port]);
  } else if (command === "mcp") {
    launch(["-m", "app.mcp_server"]);
  } else if (command === "doctor") {
    ensurePython();
    runSetup({ command: python, args: ["-c", "import sys; print('Python', sys.version.split()[0]); import fastapi, mcp; print('万相运行环境正常')"] });
    console.log(`数据目录：${home}`);
    console.log(`模型模式：${process.env.VIS_AGENT_API_KEY ? "已配置" : "未配置（本地降级）"}`);
  } else if (command === "help" || command === "--help" || command === "-h") {
    help();
  } else {
    console.error(`未知命令：${command}`);
    help();
    process.exitCode = 1;
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
