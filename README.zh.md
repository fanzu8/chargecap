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
- **禁止休眠**：持有一个 logind 的 sleep 抑制锁，插着线时**网络保持在线**
  （系统挂起会断网）。
- **状态面板**：`电源`（已连接 / 未连接、充电中 / 未充电、电量 %）、**USB 类型**
  （SDP / DCP / CDP / 未知，旁边 ⓘ 有各值说明）、**温度**、**电压**、**功率**、
  **电流**（实时值、本次会话的**极值**范围 `min | max`、额定**最大**、可写的
  `限制`）、**充满 / 设计容量**与由此得到的容量百分比 —— 名称与数值的颜色和对应
  曲线一致，每 500 ms 刷新。
- **曲线**：**指标**（电压 / 电流 / 功率 / 温度 / 电量）可任意多选叠加，**窗口**
  可选 30 秒～48 小时；数据只存在内存里，只记录界面打开期间。
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

标准库 Python，没有 pip 依赖；测试不需要手机、也不需要 GTK：

```sh
python3 -m unittest        # 73 个用例
```

测试用假 sysfs 驱动真实控制循环、读界面源码校验各表与布局不变量、检查打包契约。
CI 在 Python 3.10–3.13 上跑。

## 许可

[General Pleasure League (GPL) 1.0](https://github.com/fanzu8/General-Pleasure-League)

电量计与充电器节点按**属性自动识别**（找不到时回落到 OnePlus 6 的名字），所以 **6T** 等其它 mainline 高通机型应该同样可用；移植计划见 `TODO.md`。
