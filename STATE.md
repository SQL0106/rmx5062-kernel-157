# 状态记录（2026-11-07，实时更新）

> 目标：realme RMX5062（mt6989，6.1.157 厂商 GKI）内置 Droidspaces 支持的 OKI 内核。
> 仓库：https://github.com/SQL0106/rmx5062-kernel-157（public，main）
> 本地：`/home/SQL916/projects/rmx5062-kernel-157`
> 唯一构建入口：`.github/workflows/fastbuild-6.1.157-mt6989.yml`

## 铁律（不变）
- **没有明确批准，绝不 `fastboot flash` / `erase` / `set_active` / `dd` 写分区**；`fastboot boot` 验证也要单独批准。
- 重启手机先征得同意（droidspaces LKM 已加载）。
- 宿主查询一律 `rsh host-android '<cmd>'`。
- 长任务：必须 `tee` 日志 + `if: always()` 上传、60 秒心跳、`timeout`、关键前置自检；**一个步骤 30–60 分钟无可观测进展即当失败处理**。

## 当前状态（2026-11-07 16:35Z）
最后 commit：`8d47ae8`（补 `block/blk-sec.h`）
最后 run：`42390810756` → **编译全部通过，链接阶段失败**（8 分钟）

### 阻塞点（当前唯一）
```
ld.lld: error: undefined symbol: fake_state
>>> referenced by selinuxfs.c:726 (../security/selinux/selinuxfs.c:726)
>>>               security/selinux/selinuxfs.o:(sel_write_context)
...
pahole: .tmp_vmlinux.btf: Invalid argument
ld.lld: error: .btf.vmlinux.bin.o: unknown file type
```
- `fake_state` 在 157 官方树里**根本不存在**（本地全树 grep 无结果），说明是**某个补丁只应用了一半**：
  使用它的 hunk 打上了，定义它的 hunk 没打上（我们所有外部补丁都是 `patch -F 3 ... || warning`，允许部分成功）。
- 嫌疑顺序：`69_hide_stuff.patch`（cctv18 other_patch，selinux 相关）> susfs `50_add_susfs...` > CVE/rtmutex > BakaSU setup。
- 下一步：确认 `fake_state` 的定义来自哪个补丁的哪个 hunk，判断是"补上定义"还是"撤掉使用的 hunk"；并把所有 `|| warning` 的补丁改成**应用后 grep 关键符号自检**。

## 已修复的问题（全部是"官方树残缺"或"脚本误删"，逐条记录，别重犯）

| # | 现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | 缺 `actions/checkout`，`patches/` 不存在 | 没检出自身仓库 | 加 checkout |
| 2 | `drivers/soc/Kconfig` 悬空 | 官方树裁掉 `drivers/soc/oplus` | `scripts/clean-missing-refs.py` |
| 3 | `tools/lib/bpf` `-Werror` 打死 resolve_btfids | Clang 20 更严 | sed 去掉 override 的 `-Werror` |
| 4 | `atomic64_t` 未定义 + `make` 卡 "Waiting for unfinished jobs" 4 小时 | 脚本删掉 `source "arch/$(SRCARCH)/Kconfig"` → CONFIG_ARM64/64BIT 全丢 | 展开 `$(SRCARCH)`/`$(HEADER_ARCH)`/`$(KCONFIG_EXT_PREFIX)` 再判存在，未知变量保留整行；跳过 `scripts/kconfig/tests` |
| 5 | `Kconfig.ext:4: can't open file "kernel/oplus_cpu/Kconfig"` | 同上，第二处 | 同上（commit `9f9e7b1`） |
| 6 | `kernel/sched/core.c: ../locking/locking_main.h: file not found` | 官方树 8 个软链指向未发布的 `vendor/oplus/...`（解包后全悬空） | 新增 workflow 步骤：`find common -xtype l`，凡 `ref134/<同路径>` 是真实文件就从 134 树补回（commit `c5e6667`） |
| 7 | `block/ssg-iosched.c: 'blk-sec.h' file not found` | SSG 移植只拷了 4 个文件，漏了 134 树的 `block/blk-sec.h` | 拷贝列表加 `blk-sec.h`（commit `8d47ae8`） |

### 悬空软链补齐结果（run 42390123132 实测，全部来自 ref134）
```
[fixed] drivers/soc/oplus/oplus_resctrl
[fixed] drivers/soc/oplus/storage
[fixed] include/soc/oplus/storage
[fixed] kernel/locking/locking_main.h
[fixed] kernel/locking/oplus_locking.c      (obj-y, 必须能编)
[fixed] kernel/locking/sa_common_struct.h
[fixed] kernel/oplus_cpu
[fixed] mm/mm-trace.h                        (mm/vmscan.c 引用)
```

## run 历史（截至 16:32Z）

| run | commit | 结果 | 时长 | 失败点 |
|---|---|---|---|---|
| 42340342051 | – | failure | 1.6m | 缺 checkout |
| 42343041452 | – | failure | 1.8m | drivers/soc/oplus 悬空 |
| 42359672608 | – | failure | 1.8m | libbpf -Werror |
| 42360131680 | – | cancelled | 108m | 为验证"x86 慢"取消（决策失误） |
| 42367803692 | 5ff8a34? 前 | cancelled | 239.8m | 僵尸构建（$(SRCARCH) bug） |
| 42375502906 | | cancelled | 134.6m | 同上 |
| 42386122166 | 5ff8a34 | failure | 2.6m | `Kconfig.ext: kernel/oplus_cpu/Kconfig` |
| 42389556644 | 9f9e7b1 | failure | 3.7m | `locking_main.h` |
| 42390123132 | c5e6667 | failure | 3.5m | `blk-sec.h` |
| 42390810756 | 8d47ae8 | failure | 8.4m | **链接 `fake_state`（编译已全过）** |

浪费总计约 8 小时 02 分（482 分钟）；教训已写进 supermemory：
- 项目级 error-solution `AbjG5ARgqNZj4BbCLBcaxh`
- 用户级 learned-pattern `cAvUWc8ZAJW7zLRP418knV`

## 环境与源码事实
- 源：`OnePlusOSS/android_kernel_oneplus_mt6989` @ `822beed40827f1e9a103bc06ab4714a670080b72`（Makefile SUBLEVEL=157）
- 参考：`cctv18/android_kernel_oneplus_mt6989` @ `16bc556523df15b47f47ec4185616f0304c44240`（6.1.134，只用于补文件/移植 SSG）
- 只编 `Image`；版本后缀固定 `android14-11-o-g606246250429`；构建机 `ubuntu-24.04-arm`；LLVM 20.1.8 ARM64
- 本地已解包 157 全树：`/tmp/opencode/src/android_kernel_oneplus_mt6989-<sha>/`（可离线 grep）
- `CONFIG_OPLUS_SCHED_TUNE` 相关引用（`kernel/oplus_cpu`）全部有 `IS_ENABLED()` 保护，未开启，不影响编译

## 默认参数（每次手动触发都要带）
`ksu_type=bakasu, kpm_enable=true, susfs_enable=true, lz4_enable=true, lz4kd_enable=false, better_net=true, bbr_enable=false, droidspaces=s, ssg_enable=true, bbg_enable=true, cve_fix=true, fast_build=false, kernel_suffix=android14-11-o-g606246250429, ccache_update=false, make_release=false`

## 轮询
- 脚本 `~/.local/bin/rmx5062-ci-watch.sh [间隔秒] <run_id>`，日志 `~/.cache/rmx5062-ci/poll.log`
- 运行期 GitHub 取不到日志（`BlobNotFound`），只有 job 结束才能 `gh api .../actions/jobs/<jid>/logs`
- 判断"真在编译"：编译步骤持续 >8 分钟无失败（前几次都是秒挂）；最终仍有 `[hb] objs=` 心跳可回溯

## 出包后的步骤（需批准才刷）
1. 下载 artifact → `strings Image | grep 6.1.157-`、sha256
2. fedora `~/projects/rmx5062-fastboot-test/`：`work/magiskboot repack` 生成 `new-boot.img`（原厂 `boot_a-orig.img` sha256 `bc1895b0…fa09`，`KERNEL_FMT lz4_legacy`）
3. 等用户明确批准再 `fastboot boot`
4. 刷入后需删 `/data/adb/modules/kernelsu`、停用 `droidspaces_lkm`
