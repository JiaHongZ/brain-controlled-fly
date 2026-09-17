# 网页服务器部署

这是 **Python 后端 + Web 前端**，需保持后端进程运行并支持 WebSocket。只上传到静态空间、GitHub Pages 或对象存储不能运行物理仿真。

推荐 Linux x86_64、Docker Engine + Compose v2；可从 4 核 CPU / 4 GB 内存配置开始评估。服务器不需要 GPU 或桌面环境，Three.js 在访问者浏览器中渲染。每个浏览器标签页独立运行一份神经/物理模拟，访客增多会增加 CPU 和内存消耗；本包没有做公网并发容量测试。

## Docker 启动

将 ZIP 上传并解压，在服务器执行：

```bash
unzip brain_controlled_fly-server.zip
cd brain_controlled_fly
cp .env.example .env
docker compose up -d --build
docker compose ps
docker compose logs -f --tail=100
```

首次构建会下载 Python 依赖。包内包含真实 EEG 缓存和完整准备后的 MANC 数据，无需启动时重新下载原始数据。启动就绪后：

```bash
curl -f http://127.0.0.1:8501/health/ready
```

准备中返回 503，完成后返回 200 与 `state: ready`。容器自带健康检查，Compose 在进程退出后自动重启；单纯 unhealthy 不会触发自动重启，应查看日志。

## 接入域名

建议使用独立子域名，例如 `fly.example.com`，DNS 指向服务器。在宿主机 Nginx 中配置：

```bash
sudo cp deploy/nginx.conf /etc/nginx/conf.d/neurofly.conf
# 将配置里的 fly.example.com 改成你的域名。
sudo nginx -t
sudo systemctl reload nginx
```

然后访问 `http://你的域名/`。如果服务器已有网站配置，把本包中的 `location /` 放入该子域名的 server 块。示例假设 Nginx 位于宿主机；若 Nginx 也在容器中，应接入同一 Docker 网络并将 upstream 改为 `http://neurofly:8501`。

HTTPS 可通过现有面板配置证书，或在已安装 Certbot 的服务器执行：

```bash
sudo certbot --nginx -d 你的域名
```

前端会随页面协议自动使用 `ws://` 或 `wss://`。代理必须保留示例中的 Upgrade / Connection 请求头；否则页面能打开但模拟无法连接。

当前资源与 API 使用根路径，**请部署在域名根目录或独立子域名**，不要直接挂在 `/fly/` 子路径。

## 直接用 IP 访问

没有域名时，将 `.env` 中 `FLY_BIND` 改为 `0.0.0.0`，然后执行：

```bash
docker compose up -d
```

在云服务器安全组/防火墙放行 8501，访问 `http://服务器IP:8501/`。使用上述宿主机 Nginx 方案时，默认绑定 127.0.0.1 即可，只需对外开放网站端口。

## 不用 Docker

使用 Python 3.12，在本目录安装依赖并启动：

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-server.txt
MUJOCO_GL=osmesa OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python app.py --host 0.0.0.0 --port 8501 --no-browser
```

Debian/Ubuntu 上先安装 Dockerfile 中列出的系统库。进程应由 systemd 或服务器面板托管，不要依赖关闭 SSH 后会退出的前台终端。也可通过 HOST / PORT 环境变量配置监听地址和端口。

## 更新、停止和验证

```bash
docker compose up -d --build
docker compose down
```

项目中的 `scripts/check_server.py` 会验证就绪接口和 WebSocket 物理状态更新：

```bash
docker compose exec neurofly python scripts/check_server.py http://127.0.0.1:8501
```

数据目录需对运行账户可写（启动时生成校准及显示子集）。Docker 已使用非 root 账户并正确设置权限。默认一个应用进程；不要自行增加多个 worker 而忽略每个 worker 的独立数据加载与内存需求。

## 验证范围

此包基于已通过神经/物理与 GUI 检查的版本。服务器监听参数、就绪接口、HTTP 和 WebSocket 冒烟检查在本机验证。当前打包环境未安装 Docker，**尚未实际执行 Linux Docker 构建或 Nginx 配置加载**；服务器上应按以上命令完成构建与健康检查。
