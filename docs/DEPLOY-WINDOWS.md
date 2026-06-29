# AiStock Windows Server 2019 原生部署指南（方案A，不用 Docker）

> 适用环境：**Windows Server 2019 / Windows 10 1809（Build 17763）**，无法安装 Docker Desktop（要求 Win10 22H2 / Build 19045+ 与 WSL2）。
> 本指南在 Windows 上**原生安装**全部中间件与应用进程，用 **NSSM** 把进程注册成 Windows 服务（等价于 Linux 的 systemd）。
> Linux + Docker 方案见 [DEPLOY.md](./DEPLOY.md)。

---

## 0. 为什么不用 Docker

| 要求 | Docker Desktop 最低要求 | 本机 Build 17763 |
|------|------------------------|------------------|
| Windows 10 | 22H2 / Build 19045 | ❌ |
| WSL2 后端 | Build 18362+ | ❌（17763 不支持 WSL2）|
| Windows Server | **完全不支持 Docker Desktop** | ❌ |

Server 2019 原生 Docker Engine 默认只能跑 **Windows 容器**，而项目镜像全是 Linux（postgres/neo4j/redis…），跑不起来。因此本机走**原生安装**。

---

## 1. 组件与 Windows 原生对应方案

| 组件 | 必须性 | Windows 安装方式 | 缺失时降级行为 |
|------|--------|------------------|----------------|
| **Python 3.11+** | 必须 | python.org 官方安装包 | — |
| **Node.js 18+** | 必须（构建前端）| nodejs.org LTS | — |
| **PostgreSQL 15** | **生产必须** | EDB 官方 Windows 安装包 | 回退内存种子 / SQLite（仅演示）|
| **Redis** | **必须**（Celery 定时采集）| Memurai 或 redis-windows 移植版 | API 同步降级，**Beat 无法运行**（定时七层采集失效）|
| **Neo4j 5** | 强烈推荐 | Community zip + JDK 17 | 内存图遍历，无多跳加速 |
| **Qdrant** | 可选 | GitHub release Windows 二进制 | 关键词检索降级 |
| **MinIO** | 可选 | minio.exe Windows 二进制 | 研报无法对象存储 |
| **NSSM** | 生产推荐 | choco install nssm | — |
| **Nginx/Caddy** | 生产推荐 | 托管前端 dist + 反代 /api | 开发可用 vite dev |

> **最小可用生产组合** = Python + Node + PostgreSQL + Redis + Neo4j。Qdrant/MinIO 可后补。

---

## 2. 安装基础运行时

### 2.1 Python 3.11+

下载：<https://www.python.org/downloads/windows/>（选 *Windows installer 64-bit*）。
安装时**务必勾选** “Add python.exe to PATH”，并勾选 py launcher。

```powershell
py -3.11 --version    # 验证
```

### 2.2 Node.js 18+ LTS

下载：<https://nodejs.org/en/download>（Windows Installer .msi）。

```powershell
node -v ; npm -v      # 验证
```

### 2.3 NSSM（生产服务托管，可选但推荐）

推荐先装 Chocolatey 包管理器（<https://chocolatey.org/install>），再装 nssm：

```powershell
# 管理员 PowerShell
choco install nssm -y
nssm version
```

或手动下载 <https://nssm.cc/download> 解压，把 `win64\nssm.exe` 放进 PATH。

---

## 3. 安装中间件

### 3.1 PostgreSQL 15（生产必须）

1. 下载 EDB 安装包：<https://www.enterprisedb.com/downloads/postgres-postgresql-downloads>（选 15.x Windows x86-64）。
2. 安装时设置 `postgres` 超级用户密码，端口默认 5432。安装后自动注册为 Windows 服务 `postgresql-x64-15`。
3. 创建项目库与账号（用安装自带的 SQL Shell `psql` 或 pgAdmin）：

```sql
CREATE USER aistock WITH PASSWORD '改成强密码';
CREATE DATABASE aistock OWNER aistock;
GRANT ALL PRIVILEGES ON DATABASE aistock TO aistock;
```

对应 env：`DATABASE_URL=postgresql://aistock:改成强密码@127.0.0.1:5432/aistock`

> 应用首次启动会自动建表、灌种子、投影图（见 `app/main.py` lifespan），无需手动建表。

### 3.2 Redis（Celery 定时采集必须）

Redis 官方不发布 Windows 版，二选一：

**方案① Memurai（推荐，Windows 原生 Redis 兼容，含免费 Developer 版）**
下载 <https://www.memurai.com/get-memurai>，安装后自动注册为服务，监听 6379。

**方案② redis-windows 移植版（免费开源）**
下载 <https://github.com/redis-windows/redis-windows/releases> 的 zip，解压后：

```powershell
# 前台测试
.\redis-server.exe redis.windows.conf
# 注册成服务（该 fork 自带）
.\redis-server.exe --service-install redis.windows.conf
.\redis-server.exe --service-start
```

验证：`redis-cli ping` 返回 `PONG`。
对应 env：`REDIS_URL=redis://127.0.0.1:6379/0`

### 3.3 Neo4j 5 Community（强烈推荐）

1. 装 JDK 17（Neo4j 5 需要）：Temurin <https://adoptium.net/temurin/releases/?version=17>，安装后设置 `JAVA_HOME`。
2. 下载 Neo4j Community zip：<https://neo4j.com/deployment-center/>（Community Server，*.zip Windows）。
3. 解压到例如 `C:\neo4j`，注册并启动服务：

```powershell
cd C:\neo4j\bin
.\neo4j.bat windows-service install
.\neo4j.bat windows-service start
```

4. 首次访问 <http://127.0.0.1:7474> 用默认 `neo4j/neo4j` 登录并改密码（与 env 一致）。
5. （可选）安装 APOC 插件：把对应版本 `apoc-*.jar` 放入 `C:\neo4j\plugins` 后重启服务。

对应 env：`NEO4J_URI=bolt://127.0.0.1:7687`、`NEO4J_PASSWORD=你设置的密码`

### 3.4 Qdrant（可选，向量检索）

下载 <https://github.com/qdrant/qdrant/releases> 的 `qdrant-x86_64-pc-windows-msvc.zip`，解压后 `qdrant.exe` 直接运行（默认 6333）。生产可用 NSSM 注册为服务：

```powershell
nssm install aistock-qdrant C:\qdrant\qdrant.exe
nssm set aistock-qdrant AppDirectory C:\qdrant
nssm start aistock-qdrant
```

### 3.5 MinIO（可选，研报对象存储）

下载 `minio.exe`：<https://min.io/download#/windows>。

```powershell
$env:MINIO_ROOT_USER="aistock"
$env:MINIO_ROOT_PASSWORD="改成强密码"
.\minio.exe server C:\minio-data --console-address ":9001"
```

生产同样可用 NSSM 注册为服务。对应 env：`MINIO_ENDPOINT=127.0.0.1:9000` 等。

---

## 4. 部署应用

假设代码已克隆到 `D:\codebase\github\aistock`。

### 4.1 配置环境变量

```powershell
cd D:\codebase\github\aistock
Copy-Item deploy\aistock.env.example deploy\aistock.env
notepad deploy\aistock.env
```

至少修改：`DATABASE_URL` 密码、`NEO4J_PASSWORD`、（如需 LLM）`LLM_API_KEY`，以及打开生产数据源：

```ini
DATA_ADAPTER_MARKET=tencent
DATA_ADAPTER_FINANCIAL=sina
DATA_ADAPTER_RESEARCH=eastmoney
DATA_ADAPTER_CONSTITUENT=akshare
```

### 4.2 安装后端依赖

```powershell
# 在仓库根目录
powershell -ExecutionPolicy Bypass -File deploy\windows\setup-backend.ps1
```

脚本会创建 `backend\.venv`、安装 `requirements.txt`，并额外装 `eventlet`（Celery 在 Windows 上的并发池）。

### 4.3 构建前端

```powershell
cd frontend
npm ci
npm run build      # 产出 frontend\dist
cd ..
```

---

## 5. 启动

### 5.1 开发 / 验证（前台多窗口）

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\start-dev.ps1
```

会分别弹出 4 个窗口：API(:8000)、Celery worker、Celery beat、前端 dev(:5173)。
跳过前端：加 `-NoFrontend`；改用单任务池：加 `-WorkerPool solo`。

验收：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health | ConvertTo-Json -Depth 5
```

### 5.2 生产（NSSM Windows 服务）

在**管理员** PowerShell：

```powershell
# 安装并启动 3 个服务（api / worker / beat）
powershell -ExecutionPolicy Bypass -File deploy\windows\install-services.ps1 -Action install

# 常用管理
.\deploy\windows\install-services.ps1 -Action status
.\deploy\windows\install-services.ps1 -Action restart
.\deploy\windows\install-services.ps1 -Action uninstall
```

服务会自动开机启动，读取 `deploy\aistock.env` 全部变量，日志写到 `deploy\windows\logs\`。

> **Celery on Windows 注意**：worker 默认用 `-P eventlet`（已在 setup 中安装）。若遇到兼容问题可改 `-WorkerPool solo`（单并发，最稳）。

---

## 6. 前端托管（生产）

构建出的 `frontend\dist` 是静态文件，需要一个 Web 服务器托管并把 `/api` 反代到 `:8000`。Windows 上推荐 **Caddy**（单 exe，配置简单）或 **Nginx for Windows**。

### Caddy 示例（`Caddyfile`）

```caddyfile
:80 {
    root * D:\codebase\github\aistock\frontend\dist
    encode gzip
    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }
    handle {
        try_files {path} /index.html
        file_server
    }
}
```

```powershell
# 下载 caddy.exe 后
caddy run            # 前台
# 或用 NSSM 注册成服务：nssm install aistock-web C:\caddy\caddy.exe run
```

### Nginx for Windows

下载 <https://nginx.org/en/download.html>，在 `conf\nginx.conf` 的 `server` 块配置：

```nginx
location / {
    root   D:/codebase/github/aistock/frontend/dist;
    try_files $uri $uri/ /index.html;
}
location /api/ {
    proxy_pass http://127.0.0.1:8000;
}
```

---

## 7. 定时数据采集（Celery Beat）

`aistock-celery-beat` 服务启动后，内置调度自动运行（见 `app/celery_app.py`）：

| 任务 | 频率 | 作用 |
|------|------|------|
| `data.sync_watchlist_metrics` | 每日 | 观察清单赛道产业指标 |
| `data.sync_watchlist_seven_layer` | 每日 | 观察清单赛道七层 ODS（行情/研报/财报/公告）|
| `agents.monitor_watch` | 每小时 | 动态监控告警 |
| `agents.refresh_watchlist` | 每日 | 刷新动态观察清单 |

**前提**：Redis 可达 + worker 与 beat 两个服务都在运行。

---

## 8. 防火墙与端口

| 端口 | 服务 | 公网开放 |
|------|------|----------|
| 80 / 443 | Web（Caddy/Nginx）| **是** |
| 8000 | FastAPI | 否（仅本机）|
| 5432 / 6379 / 7687 / 6333 / 9000 | 中间件 | **否** |

```powershell
# 仅放行 Web 入口（示例）
New-NetFirewallRule -DisplayName "AiStock Web" -Direction Inbound -LocalPort 80,443 -Protocol TCP -Action Allow
```

---

## 9. 常见问题

**Q: `setup-backend.ps1` 报找不到 Python？**
确认安装时勾选了 “Add to PATH”，或用 `-Python "py -3.11"` 显式指定。

**Q: Celery worker 起来但任务不执行 / 报 fork 错误？**
Windows 必须用 `-P eventlet` 或 `-P solo`，prefork 池不支持 Windows。

**Q: 服务启动失败，怎么排查？**
看 `deploy\windows\logs\<service>.log`；或 `nssm edit aistock-api` 检查路径/环境。

**Q: `health` 里 `postgresql=false`？**
确认 `postgresql-x64-15` 服务在跑，且 `DATABASE_URL` 的账号/密码/库名与第 3.1 步一致。

**Q: 定时采集没动静？**
确认 `aistock-celery-beat` 与 `aistock-celery-worker` 均 running，且 Redis `ping` 通。

**Q: 脚本中文输出乱码？**
脚本逻辑用英文，不影响运行；如控制台乱码可执行 `chcp 65001` 切到 UTF-8。

---

## 10. 升级

```powershell
cd D:\codebase\github\aistock
git pull
powershell -File deploy\windows\setup-backend.ps1
cd frontend; npm ci; npm run build; cd ..
.\deploy\windows\install-services.ps1 -Action restart
```

备份：PostgreSQL 用 `pg_dump`；Neo4j 用 `neo4j-admin database dump`；`deploy\aistock.env` 单独保管（勿提交 Git）。
