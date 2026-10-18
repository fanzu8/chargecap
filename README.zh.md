# chargecap（中文名：电电）

<img src="icons/org.postmarketos.Chargecap.svg" width="88" alt="chargecap">

[English](README.md) | **中文**

把插着 USB 的手机电量维持在一个区间内：**一个 root 守护进程 + 一个不需要
任何特权的 GTK4/libadwaita 界面**，为 **OnePlus 6/6T**（postmarketOS）编写。

**核心功能**
- 限制充电电量
- 限制充电电流
- 状态面板（电压、功率、电流、电流极 / 最大值、温度、充满 / 设计容量、容量百分比、USB 类型、充电状态、连接状态、电量）
- 叠加曲线：电压 / 电流 / 功率 / 温度 / 电量（窗口可选）
- 禁止休眠


<img src="docs/demo-en.gif" width="49%" alt="chargecap"> <img src="docs/demo-zh.gif" width="49%" alt="chargecap">

## 支持机型

| 机型 | 状态 |
|---|---|
| OnePlus 6（enchilada） | 已实测 —— 本项目就是为它写的 |
| OnePlus 6T（fajita） | 预期原样可用：mainline 里两者共用 `sdm845-oneplus-common.dtsi`，电量计同为 `ti,bq27411`、充电器同为 `pmi8998_charger`；而这两个节点是按属性识别的 |

其它 mainline 高通机型：只要充电器暴露 `online` / `status` / `usb_type` / `current_max`，
大概率也能用，详见 `TODO.md`。

## 功能

- **滞回**：电量到**上限**停止充电，降到**下限**恢复；区间内保持现状。默认 70 / 68（%）。
- **总开关**：关掉后完全不干预充电（电流限制不为 0 时除外）。
- **USB 输入限流**：`限制` 可写，`最大` 是它不能超过的额定值；`0` 表示不限制。
- **禁止休眠**：只要这个开关是开的，就一直持有 logind 的 sleep 抑制锁，
  **网络保持在线**（系统挂起会断网）。它与是否插电无关；关掉只是让 chargecap
  不再阻止挂起，之后是否挂起由系统自身的策略决定。
- **状态面板**：`电源`（已连接 / 未连接、充电中 / 未充电、电量 %）、**USB 类型**
  （SDP / DCP / CDP / 未知，旁边 ⓘ 有各值说明）、**温度**、**电压**、**功率**、
  **电流**（实时值、本次会话的**极值**范围 `min | max`、额定**最大**、可写的
  `限制`）、**充满 / 设计容量**与由此得到的容量百分比 —— 名称与数值的颜色和对应
  曲线一致，每 500 ms 刷新。
- **曲线**：**指标**（电压 / 电流 / 功率 / 温度 / 电量）可任意多选叠加，**窗口**
  可选 30 秒～48 小时；数据只存在内存里，只记录界面打开期间。
- **默认暗色**，标题栏里语言开关前面还有一个"背景"开关（暗色 / 亮色 / 跟随系统）。
- **跟随系统语言**（中文 / English），标题栏右上角可手动切换。

## 工作原理

界面不需要任何权限：它写一个请求文件，守护进程应用后写出状态文件。

| | |
|---|---|
| 电量计 | `bq27411-0/{capacity,voltage_now,current_now,temp,constant_charge_current_max}` |
| 充电器 | `pmi8998-charger/{online,usb_type}` |
| 停 / 恢复充电 | 写 `pmi8998-charger/status` |
| USB 输入限流 | 写 `pmi8998-charger/current_max` |

守护进程每 3 秒一轮，界面每 500 ms 刷新。

## Android

`android/` 里是同一个 App 的**只监控那一半**，用 Kotlin + Jetpack Compose 重写，
面板、曲线、窗口、配色和文案都保持一致。

Android 的 SELinux 不让 App 读写充电器的 sysfs，也没有守护进程可问，所以控制那
半仍留在 GTK 版的 root 守护进程里：充电限制那几行照原样显示但被禁用，并注明原因。
**禁止休眠**在这里是真能用的 —— 它是 partial wake lock，相当于 Android 版的
`systemd-inhibit`。平台能读出什么、读不出什么，以及 `current_now` 不可信时电流
怎么测，见 [`android/README.md`](android/README.md)。

```sh
cd android && ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## 安装

```sh
doas apk add py3-cairo     # 另外需要 python3、GTK4 + libadwaita、systemd
git clone <仓库> && cd chargecap
sudo ./install.sh          # 必须在仓库目录里执行
```

界面装到 `/usr/local/bin/chargecap`，守护进程到 `/usr/local/lib/chargecap/`，
服务到 `/etc/systemd/system/chargecap.service`，应用入口到
`/usr/share/applications/`。全新安装不干预系统：限制关、禁止休眠关、输入限流 0。

```sh
sudo ./uninstall.sh        # 全部清掉，并把充电器恢复成"允许 + 额定限流"
```

## 开发

标准库 Python，没有 pip 依赖；测试不需要手机、不需要 GTK，也不需要 Android SDK：

```sh
python3 -m unittest        # 113 个用例
```

测试用假 sysfs 驱动真实控制循环、读界面源码校验各表与布局不变量、检查打包契约，
并把 Android 版和 GTK 版钉在一起 —— 指标、窗口、刻度格式、译文两边必须一致
（`tests/test_android.py`）。CI 在 Python 3.10–3.13 上跑。

## 许可

[General Pleasure League (GPL) 1.0](https://github.com/fanzu8/General-Pleasure-League)

电量计与充电器节点按**属性自动识别**（找不到时回落到 OnePlus 6 的名字），所以 **6T** 等其它 mainline 高通机型应该同样可用；移植计划见 `TODO.md`。
