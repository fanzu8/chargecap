# chargecap（中文名：电电）

<img src="icons/org.postmarketos.Chargecap.svg" width="88" alt="chargecap">

[English](README.md) | **中文**

充电时，维持手机电量在设定区间内，没 root 权限则退化为电源 / 电池状态监控。支持：

- **Android 7.0（API 24）及以上**：所有机型，不需要 root
- **postmarketOS**：mainline 内核、充电器接口齐备的机型（需要 root，见[支持机型](#支持机型)）

界面是 GTK4/libadwaita 写的，自己不需要任何特权；真正动充电器的是一个 root
守护进程。安卓端是同样的面板、曲线和文案，用 Kotlin + Jetpack Compose 重写。

**核心功能**
- 限制充电电量
- 限制充电电流
- 状态面板（电压、功率、电流、电流极 / 最大值、温度、充满 / 设计容量、容量百分比、USB 类型、充电状态、连接状态、电量）
- 叠加曲线：电压 / 电流 / 功率 / 温度 / 电量
- 曲线窗口可设定：15s ～ 48h
- 采样间隔可设定：0.01s ~ 20s
- 禁止休眠


<img src="docs/demo-en.gif" width="49%" alt="chargecap"> <img src="docs/demo-zh.gif" width="49%" alt="chargecap">

## 支持机型

### Android

**Android 7.0（API 24）及以上的手机全部支持**，不挑机型，也不需要 root。
没有 root 时只做监控（见[工作原理](#工作原理)）：状态面板、曲线、禁止休眠都能用，
充电限制那几行照常显示但被禁用，并注明原因。平台能读出什么、电流怎么测，
见 [`android/README.md`](android/README.md)。

### postmarketOS

支持**类型**：mainline 内核，且充电器公开 `online` / `status` / `usb_type` /
`current_max`、电量计能读出容量 / 电压 / 电流 / 温度的高通机型 —— 这一类已实测。
控制需要 root：界面本身不需要特权，动充电器的是一个 root 守护进程。
其它平台只要这些接口齐备，大概率也能用；节点是按属性找的，详见 `TODO.md`。

## 功能

- **滞回**：电量到**上限**停止充电，降到**下限**恢复；区间内保持现状。默认 50 / 45（%）。
- **总开关**：关掉后完全不干预充电（电流限制不为 0 时除外）。
- **禁止休眠**：只要这个开关是开的，就一直持有 logind 的 sleep 抑制锁，
  **网络保持在线**（系统挂起会断网）。它与是否插电无关；关掉只是让 chargecap
  不再阻止挂起，之后是否挂起由系统自身的策略决定
- **电源连接状态**：`电源` 已连接 / 未连接
- **充电状态**：`电源` 充电中 / 未充电
- **电量**：%
- **USB 类型**（SDP / DCP / CDP / 未知，旁边 ⓘ 有各值说明）
- **温度**：℃
- **电压**：V
- **功率**：W
- **电流**：mA，实时值、本次会话的**极值**范围 `min | max`、额定**最大**、可改的电流 `限制`，`最大` 是它不能超过的额定值；`0` 表示不限制
- **电量统计**：容量百分比 或 充放电电量统计
- **曲线**：同一窗口展示，电压 / 电流 / 功率 / 温度 / 电量可任意多选叠加
- **窗口** 可选 15 秒～48 小时；数据只存在内存里，只记录界面打开期间
- **采样间隔**（`电源` 行右侧的 `采样间隔` 开关）：曲线记录采样点的快慢，
  **13 档，从 0.01 秒到 20 秒** —— 0.01 / 0.03 / 0.05 / 0.1 / 0.3 / **0.5** /
  1 / 2 / 3 / 5 / 10 / 15 / 20 秒，默认 0.5 秒。它与面板自身 500 ms 的刷新
  无关，而缓存固定按 500 ms 计 48 小时的采样点：间隔越短曲线越细、能回看的
  时间越短（0.01 秒约一小时，20 秒约八十天）。两个平台的档位相同，都会记住选择。
- **默认暗色**，标题栏里语言开关前面还有一个"背景"开关（暗色 / 亮色 / 跟随系统）。
- **跟随系统语言**（中文 / English），标题栏右上角可手动切换。

## 安装

### Android

直接装 APK：从 [Releases](https://github.com/fanzu8/chargecap/releases) 下载
`chargecap-<版本>-universal.apk`，在手机上打开安装（或 `adb install -r` 它）。
只有一个 `WAKE_LOCK` 权限，第一次打开就是暗色、跟随系统语言。
想自己编译，见 [`android/README.md`](android/README.md)。

### postmarketOS

```sh
doas apk add py3-cairo     # 另外需要 python3、GTK4 + libadwaita 和 systemd
git clone <仓库> && cd chargecap
sudo ./install.sh          # 必须在仓库目录里执行
```

全新安装不干预系统：限制关、禁止休眠关、输入限流 0。

```sh
sudo ./uninstall.sh        # 全部清掉，并把充电器恢复成"允许 + 额定限流"
```

## 工作原理

界面自己不需要任何权限，真正动充电器的是一个 root 守护进程：

- **界面 → 守护进程**：界面把请求（限制开关、上下限、输入限流）交给守护进程，
  守护进程照做后回报状态；界面每 500 ms 刷新，守护进程每 3 秒读一轮电量计和充电器。
- **滞回**：电量到上限就停充，降到下限再恢复，区间内不折腾 —— 免得在阈值附近
  反复启停。
- **禁止休眠**：持有系统的 sleep 抑制锁（安卓上是 partial wake lock），
  让网络保持在线。
- **曲线**：只在内存里记录界面打开期间的采样；采样间隔和窗口都可调（见[功能](#功能)）。
- **安卓**：系统不给 App 碰充电器，也没有守护进程可问，所以安卓版只读平台公开的
  电池信息，控制那半保持禁用。

## 开发

标准库 Python，没有 pip 依赖；测试不需要手机、不需要 GTK，也不需要 Android SDK：

```sh
python3 -m unittest        # 148 个用例
```

测试用假 sysfs 驱动真实控制循环、读界面源码校验各表与布局不变量、检查打包契约，
并把 Android 版和 GTK 版钉在一起 —— 指标、窗口、刻度格式、译文两边必须一致
（`tests/test_android.py`）。CI 在 Python 3.10–3.13 上跑。

不用手机也想看 GTK 界面时，`tools/gtk-preview.py` 会把它指到一棵假 sysfs 树和一份
假守护进程状态上，整个面板就按真机的数值画出来；`--shot` 还能直接渲染成 PNG。
需要 GTK4 + libadwaita + PyGObject（Mac 上 `brew install gtk4 libadwaita pygobject3`）：

```sh
python3 tools/gtk-preview.py                  # 插着电的面板
python3 tools/gtk-preview.py --off            # 没插电、放电中
python3 tools/gtk-preview.py --scheme light --shot panel.png
```

## 许可

[General Pleasure League (GPL) 1.0](https://github.com/fanzu8/General-Pleasure-League)
