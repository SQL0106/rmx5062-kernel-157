# RMX5062 (realme Neo7 Turbo / MT6989) 6.1.157 OKI 内核

**主体 = ace5r 的 6.1.157 MT6989 构建流程，功能项 = cctv18 的全套可开关选项。**
所有功能都在 workflow 里用 `workflow_dispatch` 输入自由勾选，同一套代码出不同内核，互不绑定。

> 工程记录（决策依据、踩坑、验证清单、风险）见 **[PROJECT.md](PROJECT.md)**；本文只讲怎么用。

## 1. 为什么 157 必须走 ace5r，而不是直接抄 cctv18

| 仓库 | 版本上限 | 说明 |
|---|---|---|
| `OnePlusOSS/android_kernel_oneplus_mt6989` | **6.1.157** | 唯一 157 天玑树（`822beed4`），AOSP GKI common，无 `drivers/oplus`、无设备树 |
| `JavSaia/ace5r-kernel-157` | **6.1.157** | 同 SoC，已验证的 157 OKI 流程（Clang20 + gki_defconfig + 只出 `Image`） |
| `cctv18/oppo_oplus_realme_sm8650` | **6.1.134**（天玑） | 补丁集/功能实现最全，但**天玑树只到 134**；141 那套是 SM8650 |

所以本仓库：**157 的源码与编译流程取 ace5r，功能实现与补丁取 cctv18 的 134 树**（SSG 源码就是从 134 树拷过来的，157 官方树没有这些文件）。

## 2. 可开关项（全部对应 workflow_dispatch 输入）

| 输入 | 默认 | 说明 | 来源 |
|---|---|---|---|
| `ksu_type` | `ksunext` | `ksunext` / `bakasu` / `ksu` / `none` | ace5r + cctv18 |
| `kpm_enable` | `true` | KPatch-Next，用 `kptools-linux` 给 Image 打 KPM 补丁，并附 `kpn.zip` | cctv18 |
| `susfs_enable` | `true` | SUSFS 全套（需 `ksu_type != none`）| ace5r + cctv18 |
| `lz4_enable` | `true` | lz4 1.10.0 + zstd 1.5.7（zram 解压性能）| ace5r + cctv18 |
| `lz4kd_enable` | `false` | lz4kd（含 `zram.zip`）。本机 zram 熔在 `oplus_bsp_hybridswap_zram.ko` 里，内核侧加了算法也选不到，详见「关于 lz4kd」 | cctv18 |
| `better_net` | `true` | ipset/xt_set 全套 + IPv6 NAT（自动带 VINTF 隐藏补丁）| cctv18 |
| `bbr_enable` | `false` | `false` / `true` / `default`（默认拥塞算法设为 bbr）| ace5r + cctv18 |
| `droidspaces` | `s` | `n` / `s` / `e`（e 额外：虚拟 HCI、`STATIC_USERMODEHELPER=n`、EVDI DRM）| cctv18 |
| `ssg_enable` | `true` | 三星 SSG IO 调度器（从 134 树移植 4 个文件 + Kconfig/Makefile）| ace5r + cctv18 |
| `bbg_enable` | `true` | 内核级基带保护 BBG（防格机）| ace5r + cctv18 |
| `cve_fix` | `true` | CVE-2026-43499 rtmutex | cctv18 |
| `kernel_suffix` | `android14-11-o-g606246250429` | **必须与 boot_a 原版一致**，否则 326 个 vendor ko 拒载 | 本机 |
| `ccache_update` | `false` | 改源码/配置后勾上，刷新缓存 | ace5r |
| `make_release` | `false` | 构建完发 Release | ace5r |

**关于 BakaSU**：ReSukiSU 已改名为 **BakaSU**，所以没有单独的 `sukisu` 选项了；cctv18 的 `y` 档本身也已重定向到 `BakaSU/BakaSU`。管理器仍兼容 SukiSU 那一套。

**未包含 Re-Kernel**：它只有 `CONFIG_REKERNEL=y` 一行配置，源码在 cctv18 自己 fork 的树里，157 官方树没有；硬加只会是个无效符号。要 Re-Kernel 得先等 157 有对应源码。

## 3. Droidspaces 三档

`n` 完全不开；`s` 标准；`e` 扩展（+`BT_HCIVHCI`、`STATIC_USERMODEHELPER=n`、`CONFIG_DRM_LINDROID_EVDI` + `evdi_drm.patch`）。

`s`/`e` 都做：

- **补丁**（与 cctv18 builder 同集，**不含**它提供但自己也没用的 `fix_cgroup.patch`）：
  `fix_sysvipc_kabi_6_7_8`（把 `sysv_sem/sysv_shm` 挪进 `task_struct` 的 kABI padding，**不打必 bootloop**）、
  `fix_oplus_bsp_midas`（开 PID_NS 后 `oplus_bsp_midas.ko` 找不到 pid 会崩）、
  `ntsync_base` + `ntsync_compat_android14-6.1`。
- **defconfig**：`NAMESPACES/SYSVIPC/POSIX_MQUEUE/PID_NS/IPC_NS/USER_NS/DEVTMPFS`、
  `XT_MATCH_ADDRTYPE/XT_TARGET_LOG/XT_MATCH_RECENT`、`NTSYNC`，
  外加 `MACVLAN`（cctv18 没加，但 Droidspaces 官方文档推荐，不影响 kABI）。
- `IP6_NF_NAT` 由 `better_net` 负责；若关了 `better_net` 但仍开容器，会单独补 `IP6_NF_NAT` 并套 VINTF 隐藏补丁。

**绝不开启** `CFS_BANDWIDTH` / `CGROUP_PIDS`：会改调度器/cgroup 结构与大量导出符号 CRC，原厂模块全废且无 padding 方案；代价只是 `--cpus` / `--pids-limit` 灰显。

## 4. 校验策略（哪些会红、哪些只告警）

硬失败：
- `UTS_RELEASE == 6.1.157-<后缀>`
- 开了 Droidspaces 时，10 个 CONFIG 全 `=y` 且 `pid_namespace.o/devtmpfs.o/xt_addrtype.o/macvlan.o/ntsync.o` 真的编译出来
- 开了 `better_net` 时，`ipset/ip_set.o`、`xt_set.o` 存在
- `CFS_BANDWIDTH`/`CGROUP_PIDS` 未开、`MODULE_SIG_FORCE` 未开

只告警：KSU、SUSFS、SSG、BBG 的配置是否生效（这些依赖第三方 setup.sh，报错信息留给人看，不轻易卡死构建）。

## 5. 刷机

```bash
# 备份
adb shell su -c 'dd if=/dev/block/by-name/boot_a of=/sdcard/boot_a_stock.img'
adb pull /sdcard/boot_a_stock.img

# 刷(KernelSU 管理器 / 内核刷写 App 直接刷 zip，或 fastboot)
fastboot getvar current-slot
fastboot flash boot_a AnyKernel3_RMX5062_6.1.157_...zip
fastboot reboot
```

回退：刷回 `boot_a_stock.img`。

刷完必做：

1. **内置了 KSU** → 删掉 `/data/adb/modules/kernelsu`（或卸载 `kernelsu.ko` 的加载），否则和新内核打架。
2. **开了 Droidspaces** → 停用 `/data/adb/modules/droidspaces_lkm`（新内核原生支持 PID/IPC ns，LKM 会重复注入）。
3. 没内置 KSU（`ksu_type=none`）→ 继续用原来的 `kernelsu.ko` LKM 即可。

## 6. 失败排查（首次跑 CI 先看这里）

| 现象 | 原因 / 处理 |
|---|---|
| `01-fix_sysvipc_kabi` 打不上 | 源码 commit 不是 `822beed4`，检查 `SOURCE_COMMIT` |
| `__ksymtab`/模块加载失败、开机 vendor ko 全拒载 | 后缀不对（`uname -r` 对照），或误开了 `CFS_BANDWIDTH`/`CGROUP_PIDS` |
| `::warning::SUSFS 主补丁未完全应用` | 157 与 134 上下文差异，SUSFS 可能不完整；先能开机再修 |
| `::warning::CVE 补丁未应用` | 同上，不影响开机 |
| `check_defconfig` 报错 | 已 `sed` 掉；若仍出现说明 `build.config.gki` 变了 |
| 编译 OOM | runner 7G 内存不够时把 `-j$(nproc)` 降到 `-j8` |
| 开机卡 first stage | 先刷回备份 boot；再确认版本后缀、`CONFIG_DEVTMPFS` 是否真的编进去 |

## 7. 目录

```
.github/workflows/fastbuild-6.1.157-mt6989.yml   # 唯一入口,全开关
patches/                                        # Droidspaces 补丁(源自 cctv18,157 已 dry-run 验证)
```

补丁来源与逐条说明见 `patches/README.md`（GPL-2.0）。

## 8. 关于 lz4kd 与 zram（本机不适用，别开）

lz4kd 补丁不止加算法，它同时改三处：

1. `lib/lz4k/`、`lib/lz4kd/`（源码）+ `crypto/lz4k.c`、`crypto/lz4kd.c`（crypto 封装）
2. `drivers/block/zram/Kconfig`（新增 `ZRAM_DEF_COMP_LZ4KD` 等）
3. **`drivers/block/zram/zcomp.c` 的算法名表**（`"lz4k"`、`"lz4kd"` 是驱动里的静态表，不是 crypto 注册表）

第 3 条决定了本机用不了它：zram 的 `comp_algorithm` 列表由 **zram 驱动自己**枚举，内核里多注册一个 crypto 算法，选项不会自己冒出来。

RMX5062 的 zram 不是一个叫 `zram.ko` 的独立模块，而是熔在 OPLUS 的混合交换模块里：

```
$ strings /vendor/lib/modules/oplus_bsp_hybridswap_zram.ko | grep -E 'lz4k|zstdn'
lz4k
zstdn
zstdn_o
$ strings .../oplus_bsp_hybridswap_zram.ko | grep '^depends='
depends=mtk_disp_notify,oplus_bsp_mm_osvelte,oplus_bsp_sched_assist,oplus_bsp_zsmalloc,oplus_bsp_schedinfo
```

它自带 `lz4k`，但**没有 `lz4kd`**，而且依赖 5 个 OPLUS 模块（`zsmalloc` 也是 OPLUS 版），换不了通用 `zram.ko`；硬塞第二个 zram 驱动还会抢 `/dev/zram0`。

所以在 134 上能开 lz4kd，是因为那边的 zram 是**跟着内核源码一起编出来的**（cctv18 的 `zram.zip` 就是随那次构建生成的 `zram.ko` + `service.sh` 替换），vermagic 与当次内核一致；本机没有这个替换点。

真要在本机试，只能走“覆盖”路线：`CONFIG_ZRAM=y` + `CONFIG_ZSMALLOC=y`，再把 `oplus_bsp_hybridswap_zram`、`oplus_bsp_zsmalloc` 加进模块黑名单——代价是丢掉 OPLUS hybridswap（12G zram、`zstdn_o`、写回策略），风险高，**本项目不提供此选项**。

## 9. 关于 vendor 模块与 CRC

换 Image 后能不能开机，取决于 `/vendor/lib/modules/*.ko` 能否加载：

- **vermagic**：本 workflow 的 `kernel_suffix` 默认就是原厂 `android14-11-o-g606246250429`，完全一致。
- **CRC（`CONFIG_MODVERSIONS`）**：加 `PID_NS`/`USER_NS`/`SYSVIPC` 等配置可能改掉少数导出符号的 CRC。本项目的做法是不碰会牵动几千个符号的结构性开关（`CFS_BANDWIDTH`、`CGROUP_PIDS` 硬性禁止），并强制应用 SYSVIPC kABI 补丁（用 `ANDROID_KABI_RESERVE(6..8)` 占位，`task_struct` 布局不变）。
- 万一某个 vendor 模块仍报 `disagrees about version of symbol`，先看它是谁（`dmesg | grep -i "disagrees\|version magic"`）；`oplus_bsp_hybridswap_zram` 挂了会表现为没有 swap、整机变卡，此时刷回备份 boot 即可，不会损坏数据。
