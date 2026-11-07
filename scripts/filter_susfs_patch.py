#!/usr/bin/env python3
"""按文件前缀过滤 SUSFS 主补丁里的 hunk。

背景: cctv18/susfs4oki 的 50_ 主补丁是给「原版 KernelSU + 10_enable_susfs_for_ksu.patch」
组合写的 —— 它对 security/selinux/{hooks,selinuxfs,avc}.c 的改动依赖该补丁提供的
`fake_state`、`fake_status`、`susfs_ksu_sid`、`susfs_priv_app_sid` 等符号。

BakaSU/SukiSU 已经把这套 selinux hide 改成自己的实现(kernel/feature/selinux_hide.c,
基于 backup_sepolicy + hook/patch_memory), 源码里根本没有 fake_state; 直接打会得到:

    ld.lld: error: undefined symbol: fake_state

因此 ksu_type != 'ksu' 时, 用本脚本把补丁里指向 security/selinux/ 的 hunk 全部剔除,
只保留 fs/、mm/、kernel/ 等与 KSU 实现无关的部分。

用法: filter_susfs_patch.py <输入patch> <输出patch> <要丢弃的文件前缀> [...]
"""
import sys


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    src_path, out_path = sys.argv[1], sys.argv[2]
    drop_prefixes = tuple(sys.argv[3:])

    with open(src_path, encoding="utf-8", errors="surrogateescape") as f:
        lines = f.readlines()

    out, kept, dropped = [], 0, []
    i = 0
    while i < len(lines):
        if not lines[i].startswith("diff --git"):
            out.append(lines[i])
            i += 1
            continue

        j = i + 1
        while j < len(lines) and not lines[j].startswith("diff --git"):
            j += 1
        section = lines[i:j]

        # diff --git a/<path> b/<path>
        header = section[0].split()
        target = header[3][2:] if len(header) > 3 else ""
        drop = target.startswith(drop_prefixes)

        k = 0
        while k < len(section) and not section[k].startswith("@@"):
            k += 1
        file_head, hunks = section[:k], section[k:]

        if drop:
            dropped.append((target, len(file_head) and sum(1 for l in hunks if l.startswith("@@"))))
        else:
            out.extend(file_head)
            out.extend(hunks)
            kept += sum(1 for l in hunks if l.startswith("@@"))
        i = j

    with open(out_path, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.writelines(out)

    for target, n in dropped:
        print("dropped: %s (%d hunks)" % (target, n))
    print("保留 %d 个 hunk, 丢弃 %d 个文件" % (kept, len(dropped)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
