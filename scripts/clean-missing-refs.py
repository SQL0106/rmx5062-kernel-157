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
VAR_RE = re.compile(r'\$\((\w+)\)|\$\{(\w+)\}')

# Kconfig 里会用的变量; 未知变量一律保留整行(宁可不删, 也不要误删)
VAR_DEFAULTS = {
    "SRCARCH": "arm64",
    "HEADER_ARCH": "arm64",
    "KCONFIG_EXT_PREFIX": "",
}


def expand(raw):
    """把 $(VAR) 展开成实际路径; 遇到未知变量返回 None 表示'无法判断, 保留'。"""
    if "$" not in raw:
        return raw
    unknown = []

    def rep(m):
        name = m.group(1) or m.group(2)
        if name in VAR_DEFAULTS:
            return VAR_DEFAULTS[name]
        unknown.append(name)
        return m.group(0)

    out = VAR_RE.sub(rep, raw)
    return None if unknown else out

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
                expanded = expand(raw)
                if expanded is None:
                    # 含未知变量的路径无法静态判断, 保留 (例如 $(KCONFIG_EXT_PREFIX))
                    new_lines.append(line)
                    continue
                target = os.path.join(root, expanded)
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
