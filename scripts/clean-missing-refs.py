#!/usr/bin/env python3
"""删除 Kconfig/Makefile 中指向不存在路径的引用。

原因: OnePlusOSS 的 android_kernel_oneplus_mt6989 官方树在发布时裁掉了
drivers/soc/oplus/ (oplus_resctrl、storage), 但 drivers/soc/Kconfig 与
drivers/soc/Makefile 仍保留 source/obj 行, 导致 `make gki_defconfig` 直接失败:

    drivers/soc/Kconfig:30: can't open file "drivers/soc/oplus/oplus_resctrl/Kconfig"

这里只删除「目标确实不存在」的行, 目标存在的一律原样保留; 每删一行都会打印出来。
"""
import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "."
removed = []

SOURCE_RE = re.compile(r'^\s*source\s+"([^"]+)"\s*$')
OBJ_DIR_RE = re.compile(r'^\s*obj-[ym]?\s*\+?=\s*([A-Za-z0-9_./+-]+/)\s*$')

for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in (".git", "out")]
    # kconfig 自带的测试用例里有故意写坏的 Kconfig, 不能动
    if dirpath.replace("\\", "/").endswith("scripts/kconfig/tests"):
        dirnames[:] = []
        continue
    for fn in filenames:
        if not (fn == "Kconfig" or fn.startswith("Kconfig.") or fn.startswith("Makefile")):
            continue
        path = os.path.join(dirpath, fn)
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            continue

        new_lines = []
        for line in lines:
            m = SOURCE_RE.match(line)
            if m:
                raw = m.group(1)
                # 含 $(SRCARCH)/$(HEADER_ARCH)/$(KCONFIG_EXT_PREFIX) 等变量的路径无法静态判断,
                # 一律保留 —— 曾因删掉 arch/Kconfig 里的 source "arch/$(SRCARCH)/Kconfig"
                # 导致 CONFIG_ARM64/CONFIG_64BIT 全丢, 编译 kernel/bounds.c 时 atomic64_t 未定义。
                if "$" in raw:
                    new_lines.append(line)
                    continue
                target = os.path.join(root, raw)
                if not os.path.exists(target):
                    removed.append((path, line.strip()))
                    continue
            elif fn.startswith("Makefile"):
                m = OBJ_DIR_RE.match(line)
                if m:
                    target = os.path.join(dirpath, m.group(1))
                    if not os.path.isdir(target):
                        removed.append((path, line.strip()))
                        continue
            new_lines.append(line)

        if len(new_lines) != len(lines):
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

for p, line in removed:
    print("removed: %s : %s" % (p, line))
print("共删除 %d 行悬空引用" % len(removed))
