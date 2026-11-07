# 补丁来源

全部取自 `cctv18/oppo_oplus_realme_sm8650`（`droidspaces_patch/` 与 `other_patch/config.patch`），
GPL-2.0，**内容未做任何修改**（md5 与原件一致），仅重命名。已对
`OnePlusOSS/android_kernel_oneplus_mt6989@822beed4`（6.1.157）真实文件逐个
`patch -p1 --dry-run -F 3` 验证可打。

| 文件 | 原点 | 作用 | 状态 |
|---|---|---|---|
| `01-fix_sysvipc_kabi_6_7_8.patch` | `fix_sysvipc_kabi_6_7_8.patch` | `CONFIG_SYSVIPC` 占用 `task_struct` 的 `ANDROID_KABI_RESERVE(6..8)`，保住 kABI | **必需**，否则 bootloop |
| `02-fix_oplus_bsp_midas.patch` | `fix_oplus_bsp_midas.patch` | `find_task_by_vpid()` 对 `oplus_bsp_midas` 返回 ghost task | **必需**，否则开机崩 |
| `03-fix_cgroup.patch` | `fix_cgroup.patch` | 恢复 `CGRP_ROOT_NOPREFIX` 的 cgroup 文件名链接 | **未使用**（cctv18 自己的 builder 也不打） |
| `04-ntsync_base.patch` | `ntsync_base.patch` | 新增 `drivers/misc/ntsync.c` + `include/uapi/linux/ntsync.h` | 随 s/e 档 |
| `05-ntsync_compat_android14-6.1.patch` | `ntsync_compat_android14-6.1.patch` | 6.1 的 NTSYNC Kconfig/Makefile 入口 | 随 s/e 档 |
| `06-hide-ip6-nf-nat-in-ikconfig.patch` | `other_patch/config.patch` | IKCONFIG 里显示 `IP6_NF_NAT=n`，功能照编，绕开 OPLUS VINTF 检测 | `better_net` 或容器开启时使用 |

未收录（cctv18 有但本仓库不需要）：
- `evdi_drm.patch`（147KB）→ workflow 里按需 `wget`，仅在 `droidspaces=e` 时下载应用。
- `disable_module_crc_check.patch` → cctv18 自己也不用；忽略 CRC 会掩盖真正的 kABI 破坏。

注意：
- `01` 在 6.1.157 上有 2 行 fuzz，属正常；它一旦打不上，构建会直接失败而不是继续。
- 补丁集合与 cctv18 `builder_6.1.134.sh` 的 Droidspaces 段一致；多出来的只有 `MACVLAN`（来自 Droidspaces 官方文档）。
