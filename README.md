# Brain-Controlled Digital Fly

> **🖥️ 在线 Demo（点击体验）**：<https://naturals-extremely-operation-grill.trycloudflare.com>

**部署到网页服务器：请看 [DEPLOY.md](DEPLOY.md)。包含 Docker / Compose / Nginx 配置。**

公开人类 EEG → CSP + LDA → 真实 MANC 连接组上的神经活动传播 → 运动神经元读出 → NeuroMechFly / MuJoCo 物理行为。

这是一套可运行、可交互的工程演示，不是完整果蝇脑或经过生物学验证的数字孪生。默认使用解码预测；不隐藏错误 trial。

## 启动

使用 **Python 3.12** 和支持 WebGL 的浏览器，在本目录执行：

```bash
pip install -r requirements.txt
python app.py
```

浏览器自动打开 http://localhost:8501 。Windows 可双击 `start.bat`；macOS / Linux 可运行 `sh start.sh`（当前实际验证平台为 Windows）。支持 `--no-browser` 和 `--port 8502`。首次安装需要网络及足够时间安装科学计算与物理引擎依赖。

交付包含准备好的真实 EEG 与完整阈值过滤后的 MANC 矩阵。安装依赖后可离线演示。缺少准备数据时自动从公开来源下载并构建；失败会显示真实错误，不回退到合成数据。

## 使用

- **Decoded EEG**：真实 CSP + LDA 预测驱动 DNa02；默认模式。
- **Ground Truth**：公开标签驱动同一条神经与物理链路，用于对照。
- **Cut synapses**：切断传播，移除 EEG 对运动的影响；基础 CPG 仍会行走。Restore 恢复。
- Pause / Resume、Next trial、Reset、0.5× / 1× / 2×；脑网络和身体均可拖动旋转、滚轮缩放。
- Session details 显示数据、算法、校验口径和建模假设。

左栏绘制 8 通道波形，解码使用全部 22 通道。中栏展示真实坐标的 1,800 个神经元、20,000 条连接，节点亮度随模型活动变化，边亮度由两端节点活动推导；不使用示意流动粒子。右栏展示实际物理姿态、轨迹、参考目标、接触数和航向。全部 144 个测试 trial 按原顺序循环。

## 数据与真实程度

### EEG

BNCI2014_001 / BCI Competition IV 2a，A01T 训练、A01E 测试，只选左右手，各会话 144 trials。250 Hz，cue 后 0–4 秒回放；预测只使用前 2 秒。因果 8–30 Hz Butterworth → 4 分量 CSP → shrinkage LDA。测试准确率 **74.3056%**，混淆矩阵（真实行 L/R，预测列 L/R）`[[69,3],[34,38]]`。置信度是未单独校准的 LDA 后验。预测离线预计算以保证动画流畅，不是在线采集 EEG。

来源：https://lampx.tugraz.at/~bci/database/001-2014/

### 实测连接组

**MANC v1.0 是雄性果蝇腹神经索，不是完整脑。** 使用 23,188 个 traced neurons；原始 5,243,574 条有向连接，保留至少 5 个突触的 1,360,021 条连接，共 23,999,382 个突触。没有生成或补造边。神经元 ID、连接及突触数来自 EM 重建；原文件经过发布方 MD5 验证并记录 SHA256。

EEG LEFT / RIGHT 分别刺激真实 DNa02 #10126 / #10118。腿部运动神经元使用 eLife 96084 Supplement 6 标注；264 个标注中 247 个匹配此 traced release，缺失的 17 个明确排除。显示子集不限制实际计算：全部保留节点与边参与稀疏矩阵动力学。

来源：https://www.janelia.org/project-team/flyem/manc-connectome

运动标注：https://doi.org/10.7554/eLife.96084

### 模型假设与物理身体

- 神经动力学是延迟整流率模型：神经步长 5 ms、时间常数 25 ms、传播延迟 10 ms、递归增益 0.92。按输入突触数归一化，预测 ACh 为正、GABA/Glut 为负、未知为正。这些不是逐神经元拟合的生理参数。
- MANC 左右运动群平均活动经同一标定尺度归一化。工程适配器 `clip(1 - 0.65 * gain * motor / scale, 0.25, 1)`（默认 gain=2，可选 1 / 1.5 / 2） 调节同侧 CPG 步幅；身体代码不接收 EEG 标签或左右分类。
- 身体为 FlyGym 2.1.0 / NeuroMechFly 的 micro-CT 派生雌性果蝇模型，与雄性 MANC 来自不同标本。MuJoCo 3.9 计算重力、关节和接触：42 个腿部位置执行器、6 个黏附执行器；物理步长 0.1 ms，控制步长 1 ms。
- 基础行走来自已发表的混合 CPG 与反射控制器，**MANC 调节转向，不独立生成基础步态**。没有直接编排身体平移、转角、碰壁反弹或 trial 间瞬移。
- 人类 EEG → DNa02、运动群 → CPG 都是工程接口，不是已验证的人类—果蝇生物映射。

身体模型：https://github.com/NeLy-EPFL/flygym/tree/v2.1.0

论文：https://doi.org/10.1038/s41592-024-02497-y

## 动画时钟

每个 trial 的 EEG 时间为 5 秒：0–2 秒采集，2 秒揭示预测，2–3.8 秒刺激 DNa02，4 秒记录运动读出，5 秒切换。神经/身体时间以 EEG 的 0.1× 推进，界面明确显示 BODY 时间。身体持续进行物理积分，转向连续发生，不在第 4 秒强制转固定角度。目标仅是参考，不是闭环导航任务。

## 复现与校验

```bash
python scripts/download_eeg.py --force
python scripts/download_manc.py
python scripts/build_manc_connectome.py
python -m unittest discover -s tests -v
python scripts/probe_real_chain.py
python scripts/audit_long_replay.py
```

ZIP 不附体积较大的原始 MAT / CSV / Feather；运行下载脚本即可重建。逐边审计需要原始连接 CSV，缺失时对应测试明确跳过。数据来源见 `data/eeg/provenance.json`、`data/manc/source_manifest.json`、`network_config.json`。依赖实测版本见 `tested-versions.json`。

`data/connectome/nodes.csv`、`edges.csv` 是**可视化子集**的统一表接口，不能通过只替换它们更改全网络仿真。全网络由 `scripts/build_manc_connectome.py` 生成 `data/manc/measured_network.npz`、`measured_edges.npz` 和 `all_neurons.json`，更换数据源需同步构建这些文件。

## 交付文件

- `app.py`、`backend/`、`frontend/`：完整服务、动力学与本地 Three.js 界面。
- `scripts/`：官方数据下载、构建、因果对照和全会话回放审计。
- `tests/`：真实数据、动力学、物理、EEG 因果滤波测试。
- `demo-preview.png` / `mobile-preview.png`：实际浏览器截图。
- `VERIFICATION.md` / `data/validation/`：验证说明与原始结果。

真实连接数据不意味着模型已解释生物行为；本 Demo 证明的是可复现的工程链路及其在该模型中的因果依赖。

### 轨迹显示修正

身体网格、轨迹端点和胸部地面投影标记使用同一物理快照，不对身体单独缓动。轨迹记录胸部中心的 XY 地面投影，不是脚印；小地图采用固定世界坐标并标出身体朝向。朝向不必等于瞬时速度方向，物理模型允许侧滑。节点亮度使用当前模型活动的逐细胞归一化值；边亮度只是端点活动的可视化，不是实测突触电流或动作电位。

### 解码与转向如何对应

左右转指相对果蝇自身朝向的转向，不是屏幕左右移动。前 2 秒只有基础步态；第 2 秒后的路段高亮，历史路径变灰。界面同时显示实际驱动类别、实时运动群偏置，以及自第 2 秒起累计的物理航向变化（逐步 unwrap，避免 180° 边界误判）。刺激在 3.8 秒停止，之后仍有神经衰减与身体响应。运动日志的 Δ 为第 4 秒读出时累计转角。EEG 分类与神经连接保持不变；转向增益是明确可调的工程参数，身体轨迹由物理积分产生。

### 更明显的实际转向

默认转向增益现为 2×，扩大运动群活动引起的左右步幅差，最低步幅信号为 0.25。默认俯视，按钮可切换侧视。俯视画面叠加解码时方向的虚线与当前方向的实线；下方大幅角度图将解码时朝向统一朝上，显示真实累计转角，不放大角度。1× 旧版验证数据保存在 `data/validation/baseline-gain1/`；新版完整验证见 `gain2-full-replay.json`。

### Cut synapses 的准确含义

切断后左右运动神经元输出归零，下一物理更新使用相同的左右步幅信号 [1, 1]。CPG 基础步态和当前身体状态继续积分，因此仍可能转动；切断不能撤销此前形成的运动、姿态和步态相位，也不是刹车或直线锁定。切断后的界面用中性轨迹和“切断后漂移”读数，不再将身体转动标作 EEG 左转/右转。中途切断的回归测试从相同物理状态出发，验证其后每一步与零神经输入分支的 qpos 完全一致，包括跨 trial 的情况。
