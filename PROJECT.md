# RMX5062 · 6.1.157 OKI 内核构建项目

> 目标：在一台 **realme RMX5062（MT6989 / Android 16，原厂内核 6.1.157）** 上，跑一个自编译的 6.1.157 OKI 内核，
> **原生支持 Droidspaces 容器**（PID/IPC namespace），同时保留原厂 326 个 vendor 模块、dtb/dtbo 和 hybridswap 内存策略。
>
> 产物形态：**AnyKernel3 zip，只替换 boot 分区里的 `Image`**。

- 本地目录：`~/projects/rmx5062-kernel-157`
- 远端仓库：<https://github.com/SQL0106/rmx5062-kernel-157>
- 当前分支：`main`

---

## 1. 设备与内核事实（实机核对）

| 项 | 值 |
|---|---|
| 型号 | realme RMX5062（Neo7 Turbo），device `RE602EL1`，board `k6989v2_64` |
| SoC | MT6989（天玑 9300+/9400e 同平台），arm64-v8a |
| 系统 | Android 16 / SDK 36，`RMX5062_16.0.10.500(CN01)` |
| 原厂内核 | `6.1.157-android14-11-o-g606246250429`（aarch64，page size 4096） |
| Root | KernelSU（LKM 模式，`kernelsu.ko`）+ `droidspaces_lkm` v0.2.0 |
| 分区 | `boot_a=sdc37`、`boot_b=sdc70`（A/B 设备） |
| vendor 模块 | `/vendor/lib/modules` 共 **326 个 `.ko`**，vermagic 与内核逐字一致 |
| zram | 不是独立模块，熔在 `oplus_bsp_hybridswap_zram.ko` 里（`zram0` 12 GiB，算法 `lzo lzo-rle [lz4] zstd lz4k zstdn zstdn_o`） |

原厂 `/proc/config.gz` 中与容器相关的关键项：

- **已开**：`IPC_NS`、`UTS_NS`、`NET_NS`、`NAMESPACES`、`POSIX_MQUEUE`、`CGROUPS`、`MEMCG`、`SECCOMP(_FILTER)`、`OVERLAY_FS`、`FUSE_FS`、`TUN`、`BLK_DEV_LOOP`、`EXT4_FS`、`BRIDGE`、`VETH`、`NF_NAT`
- **未开**：`SYSVIPC`、`USER_NS`、`PID_NS`、`DEVTMPFS`、`MACVLAN`、`IP_SET`、`IP6_NF_NAT`、`XT_MATCH_ADDRTYPE`
- **有意保持关闭**：`CFS_BANDWIDTH`、`CGROUP_PIDS`（会改 cgroup/调度器结构，牵动数千导出符号 CRC）

---

## 2. 为什么是这套组合

| 参考 | 作用 | 实际情况 |
|---|---|---|
| `OnePlusOSS/android_kernel_oneplus_mt6989` @ `822beed4` | **唯一**的 6.1.157 MT6989 官方源码 | AOSP GKI common 树，无 `drivers/oplus`，无设备树；只能出 `Image` |
| `JavSaia/ace5r-kernel-157` | 构建流程/工具链模板 | **从未跑通**：单 commit、仅 1 次 CI（2026-09-30）死在 `gki_defconfig`、0 artifact、0 release |
| `cctv18/oppo_oplus_realme_sm8650`（及 mt6989 fork） | 补丁集与开关实现 | 实战项目；但其天玑分支最高 **6.1.134**，141 是 SM8650，157 只能取官方树 |

结论：**源码取 OnePlusOSS，参数取 ace5r，补丁与经验取 cctv18，坑自己填。**

---

## 3. 目录结构

```
.github/workflows/fastbuild-6.1.157-mt6989.yml   # 唯一入口：14 个开关，全流程
patches/
  01-fix_sysvipc_kabi_6_7_8.patch                # 必需：SYSVIPC 占用 kABI 槽位
  02-fix_oplus_bsp_midas.patch                   # 必需：开 PID_NS 后防 oplus_bsp_midas 崩
  03-fix_cgroup.patch                            # 保留但流程不启用
  04-ntsync_base.patch                           # 可选：Wine/Proton 用 NTSYNC
  05-ntsync_compat_android14-6.1.patch           # 配合 04
  06-hide-ip6-nf-nat-in-ikconfig.patch           # BetterNet：IKCONFIG 里显示 IP6_NF_NAT=n
  README.md
scripts/
  clean-missing-refs.py                          # 删除官方树里指向不存在目录的 Kconfig/Makefile 行
README.md                                        # 面向使用者的说明（开关/刷机/排查）
PROJECT.md                                       # 本文：工程记录与决策
```

补丁全部来自 cctv18，**md5 与原件一致**（仅重命名）。

---

## 4. 开关（workflow_dispatch）

| 输入 | 默认 | 说明 |
|---|---|---|
| `ksu_type` | `bakasu` | `ksunext` / `bakasu`（原 ReSukiSU，已改名）/ `ksu` / `none` |
| `kpm_enable` | `true` | KPatch-Next：`kpimg` 打入 Image + 附 `kpn.zip` |
| `susfs_enable` | `true` | SUSFS 全套（需 `ksu_type != none`） |
| `lz4_enable` | `true` | lz4 1.10.0 + zstd 1.5.7（vendor zram 直接受益） |
| `lz4kd_enable` | `false` | 本机无效，见 §8 |
| `better_net` | `true` | ipset / xt_set / IPv6 NAT + VINTF 隐藏补丁 |
| `bbr_enable` | `false` | `false` / `true` / `default` |
| `droidspaces` | `s` | `n` 关闭 / `s` 标准 / `e` 扩展（BT_HCIVHCI、Lindroid EVDI） |
| `ssg_enable` | `true` | SSG IO 调度器（从 134 树移植） |
| `bbg_enable` | `true` | 基带保护 Baseband-guard |
| `cve_fix` | `true` | CVE-2026-43499（rtmutex） |
| `kernel_suffix` | `android14-11-o-g606246250429` | **必须与原厂一致**，否则 vendor 模块全拒载 |
| `ccache_update` | `false` | 保留开关；新 key 方案下每次都会另存 |
| `make_release` | `false` | 成功后自动发 GitHub Release |

硬性校验（失败即中止）：

- `UTS_RELEASE == 6.1.157-<kernel_suffix>`
- 开容器时：`SYSVIPC / POSIX_MQUEUE / PID_NS / IPC_NS / USER_NS / DEVTMPFS / XT_MATCH_ADDRTYPE / MACVLAN / IP6_NF_NAT / NTSYNC` 全为 `=y`，且对应 `.o` 真实生成
- `CFS_BANDWIDTH`、`CGROUP_PIDS`、`MODULE_SIG_FORCE` 不得为 `y`
- 判断依据用 `out/include/config/auto.conf`，避免 `.config` 中未知符号造成假阳性

---

## 5. Droidspaces 三档

- **n**：不碰任何 namespace 配置（保持原厂形态，继续用 `droidspaces_lkm`）
- **s**（默认）：官方文档要求的最小集 + 推荐项
  - 补丁：`01`（SYSVIPC kABI，**必打，不打会 bootloop**）、`02`（midas 防崩，**必打**）、`04/05`（NTSYNC，可选但默认带）
  - defconfig：`PID_NS/USER_NS/SYSVIPC/DEVTMPFS/XT_MATCH_ADDRTYPE/XT_TARGET_LOG/XT_MATCH_RECENT/MACVLAN/NTSYNC`
  - `MACVLAN` 来自 Droidspaces 官方文档（cctv18 没加）
- **e**：在 `s` 基础上加 `BT_HCIVHCI`、`STATIC_USERMODEHELPER=n`、`DRM_LINDROID_EVDI` + `evdi_drm.patch`

> 原生支持后 **必须停用** `/data/adb/modules/droidspaces_lkm`，否则重复注入 PID/IPC namespace。

---

## 6. 构建过程中踩过的坑（按顺序）

### 6.1 缺 `actions/checkout` → `patches/` 不存在

run `42340342051`：步骤 13 报 `patches/01-...patch: No such file or directory`。
GitHub 不会自动检出仓库；前面几步都用 `wget` 远程下载，所以没暴露。
**修复**：`steps` 首项加 `actions/checkout@v4`，并在补丁步骤加存在性断言。

### 6.2 官方树缺 `drivers/soc/oplus`，`gki_defconfig` 直接死

run `42343041452`（以及 ace5r 唯一那次运行）：

```
drivers/soc/Kconfig:30: can't open file "drivers/soc/oplus/oplus_resctrl/Kconfig"
make[2]: *** [scripts/kconfig/Makefile:94: gki_defconfig] Error 1
```

OnePlusOSS 发布时裁掉了 `drivers/soc/oplus/`（`oplus_resctrl`、`storage`），但 `Kconfig`/`Makefile` 的 `source` / `obj-y` 还在。
**修复**：`scripts/clean-missing-refs.py`，全树扫描，**只删除目标确实不存在的** `source` 与 `obj-* += dir/` 行，逐行打印。

### 6.3 Clang 20 把 host tool `resolve_btfids` 打死

```
tools/lib/bpf/libbpf.c:10756: error: assigning to 'char *' from 'const char *'
  discards qualifiers [-Werror,-Wincompatible-pointer-types-discards-qualifiers]
```

`KCFLAGS+=-Wno-error` 只作用于内核本体；`tools/lib/bpf/Makefile` 里有 `override CFLAGS += -Werror -Wall`。
**修复**：编译前 `sed` 去掉该行的 `-Werror`（只影响宿主编译的 resolve_btfids，不改 Image 参数）。

### 6.4 ccache 在失败时从不保存

`actions/cache@v4` 的保存发生在 post 步骤，且 **post-if 是 `success()`**——只要编译失败，几十分钟的对象全部丢弃，下一次又从零开始。
**修复**：

- `actions/cache/restore@v4` + `actions/cache/save@v4` 分离
- 保存步骤 `if: always() && !cancelled()`
- key 用 `...-${{ github.run_id }}-${{ github.run_attempt }}`，restore 用前缀取最近一份
- 上限 3G → 4G

---

## 7. 运行记录

| run | 参数要点 | 结果 |
|---|---|---|
| 42340342051 | 首次 | ❌ 缺 checkout，`patches/` 缺失 |
| 42343041452 | 加 checkout | ❌ `drivers/soc/oplus` 悬空 |
| 42359672608 | 加清理脚本，`bakasu` | ❌ `resolve_btfids` 被 `-Werror` 打死 |
| 42360131680 | 加 libbpf 修复，`kpm=true` | 编译中（本文写作时） |

---

## 8. lz4kd 为什么在本机无效

lz4kd 补丁改三处：`lib/lz4k(d)/`、`crypto/lz4k(d).c`、**`drivers/block/zram/zcomp.c` 的算法名表**。
`comp_algorithm` 列表由 **zram 驱动自己枚举**，不是 crypto 注册表。

本机 zram 在 `oplus_bsp_hybridswap_zram.ko` 内：

```
strings → lz4k / zstdn / zstdn_o   （没有 lz4kd）
depends → mtk_disp_notify, oplus_bsp_mm_osvelte, oplus_bsp_sched_assist,
          oplus_bsp_zsmalloc, oplus_bsp_schedinfo
```

没有可替换的通用 `zram.ko`；硬塞第二个 zram 驱动会抢 `/dev/zram0`，并丢掉 hybridswap（12G、`zstdn_o`、写回）。
在 134 上能开，是因为那边 zram 随内核源码一起编（`zram.zip` 与当次 vermagic 匹配），本机没有这个替换点。

> `lz4_enable=true` 仍然有意义：它升级的是内核 `lib/lz4`、`lib/zstd`，vendor 模块直接调用这些导出符号。

---

## 9. 风险与回退

| 风险 | 表现 | 处理 |
|---|---|---|
| vendor 模块 CRC 不一致 | `dmesg | grep disagree`，模块拒载 | 本项目避开 `CFS_BANDWIDTH/CGROUP_PIDS`，SYSVIPC 走 kABI 占位；必要时加 `module_crc_bypass` 开关 |
| `oplus_bsp_hybridswap_zram` 挂 | 能开机但无 swap，整机卡 | 刷回备份 `boot_a` |
| 内置 KSU 与旧 LKM 冲突 | 管理器异常/开机循环 | 删除 `/data/adb/modules/kernelsu` |
| Droidspaces LKM 重复注入 | 容器异常 | 停用 `droidspaces_lkm` |

**刷机前必须备份**：

```sh
adb shell su -c 'dd if=/dev/block/by-name/boot_a of=/sdcard/boot_a_stock.img'
adb pull /sdcard/boot_a_stock.img
```

**刷入**（需要明确批准）：

```sh
adb reboot bootloader
fastboot flash boot_a boot_a_stock.img   # 仅回退时
fastboot flash boot  <AK3 解出的 Image>  # 或直接 sideload AK3 zip
```

**回退**：`fastboot flash boot_a boot_a_stock.img`，数据不受影响。

---

## 10. 刷后验证清单

```sh
uname -r                                   # 6.1.157-android14-11-o-g606246250429
lsmod | grep -E 'hybridswap|zsmalloc'      # vendor 内存模块是否加载
free -h                                    # swap 是否仍有 ~12G
cat /sys/block/zram0/comp_algorithm        # 应含 lz4k/zstdn
dmesg | grep -iE 'disagrees|version magic|Invalid module'
ls /proc/self/ns                           # pid/ipc/user 应齐全
```

容器侧：

```sh
/data/local/Droidspaces/bin/droidspaces check
/data/local/Droidspaces/bin/droidspaces show
```

---

## 11. 未做 / 可加

- `rekernel_enable`：Re:Kernel（tombstone 增强，netlink），可用 `dabao1955/kernel_build_action` 的 `spatch` 方案移植；用户尚未要求
- `module_crc_bypass`：cctv18 的 `disable_module_crc_check.patch`，作为 CRC 保险
- `zram_override`：内置 zram + 黑名单 OPLUS hybridswap，**不推荐**（丢 hybridswap）
- Re-Kernel、KPM、SUSFS 之间没有依赖关系，均为独立开关

---

## 12. 变更记录

| 日期 | 内容 |
|---|---|
| 2026-11-07 | 建仓；14 开关；补丁 01–06；首次 CI |
| 2026-11-07 | 修 checkout、悬空 Kconfig、libbpf `-Werror`、ccache 保存 |
| 2026-11-07 | `ksu_type` 默认改 `bakasu`；`kpm_enable` 默认改 `true` |
| 2026-11-07 | 目录迁至 `~/projects/rmx5062-kernel-157`，补 `PROJECT.md` |
