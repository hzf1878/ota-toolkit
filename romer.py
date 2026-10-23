#!/usr/bin/env python3
"""
ROMer 查询工具 - https://rom.yule.ink/
基于其公开 API: /api/ota/catalog

用法:
    ./romer.py list                    列出所有机型及最新版本
    ./romer.py find <关键词>            按机型/型号/版本搜索
    ./romer.py latest <model>          查某型号最新版本
    ./romer.py c17                     列出已更新 ColorOS 17 的机型
    ./romer.py info <model>            某型号完整版本历史
"""
import json
import os
import sys
import time
import urllib.request

API = "https://rom.yule.ink/api/ota/catalog"
CACHE = "/tmp/romer_catalog.json"
CACHE_TTL = 3600


def fetch(force=False):
    if not force and os.path.exists(CACHE):
        if time.time() - os.path.getmtime(CACHE) < CACHE_TTL:
            return json.load(open(CACHE))
    print("[*] 拉取 catalog...", file=sys.stderr)
    req = urllib.request.Request(API, headers={"User-Agent": "romer-cli/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    open(CACHE, "wb").write(data)
    return json.loads(data)


def releases(doc):
    return doc.get("releases", [])


def os_major(ver):
    """从 version 字段推断 ColorOS 大版本。
    version 形如 PJZ110_17.0.0.103(CN01) → 17
    兼容国际版 CPH2573_16.0.0.201(EX01) → 16
    """
    import re
    # 取第一个 _数字.数字 的数字部分
    m = re.search(r"[_A-Z0-9]+_(\d+)\.\d+\.\d+", ver)
    if m:
        return m.group(1)
    return "?"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    doc = fetch()
    rel = releases(doc)

    if cmd == "list":
        latest = [r for r in rel if r.get("is_latest")]
        print(f"共 {len(rel)} 条记录，{len(latest)} 个机型有最新版标记\n")
        print(f"{'机型':<22}{'型号':<12}{'版本':<32}{'OS'}")
        print("-" * 80)
        for r in sorted(latest, key=lambda x: x.get("device", "")):
            print(f"{r.get('device',''):<22}{r.get('model',''):<12}"
                  f"{r.get('version',''):<32}C{os_major(r.get('version',''))}")

    elif cmd == "find":
        if len(sys.argv) < 3:
            print("用法: romer.py find <关键词>")
            return 1
        kw = sys.argv[2].lower()
        hits = [r for r in rel if kw in " ".join(
            str(r.get(k, "")) for k in ("device", "model", "version", "ota_version")
        ).lower()]
        print(f"匹配 {len(hits)} 条：\n")
        for r in hits[-30:]:
            flag = " ★" if r.get("is_latest") else ""
            print(f"{r.get('device',''):<20}{r.get('model',''):<10}"
                  f"{r.get('version',''):<32}C{os_major(r.get('version',''))}{flag}")

    elif cmd == "latest":
        if len(sys.argv) < 3:
            print("用法: romer.py latest <model>")
            return 1
        m = sys.argv[2]
        hits = [r for r in rel if r.get("model") == m]
        if not hits:
            print(f"未找到型号 {m}")
            return 1
        cur = hits[-1] if not any(r.get("is_latest") for r in hits) else \
              [r for r in hits if r.get("is_latest")][-1]
        print(f"机型:   {cur.get('device')}")
        print(f"型号:   {cur.get('model')}")
        print(f"版本:   {cur.get('version')}")
        print(f"OTA:    {cur.get('ota_version')}")
        print(f"系统:   ColorOS {os_major(cur.get('version',''))}")
        print(f"补丁:   {cur.get('security_patch','-')}")
        print(f"构建:   {cur.get('build_timestamp','-')}")
        if cur.get("size"):
            print(f"大小:   {cur['size'] / 1024**3:.2f} GB")
        print(f"链接:   {cur.get('source_url','-')}")

    elif cmd == "c17":
        hits = [r for r in rel if os_major(r.get('version','')) in ("17", "17+")]
        devices = sorted({(r.get("device"), r.get("model"), r.get("version"))
                          for r in hits})
        print(f"已更新 ColorOS 17 的机型（{len(devices)} 款）:\n")
        print(f"{'机型':<22}{'型号':<12}{'最新版本'}")
        print("-" * 72)
        seen = set()
        for d, m, v in devices:
            if d in seen:
                continue
            seen.add(d)
            print(f"{d:<22}{m:<12}{v}")

    elif cmd == "info":
        if len(sys.argv) < 3:
            print("用法: romer.py info <model>")
            return 1
        m = sys.argv[2]
        hits = [r for r in rel if r.get("model") == m]
        print(f"{m} 共 {len(hits)} 个版本：\n")
        for r in hits:
            flag = " ★最新" if r.get("is_latest") else ""
            print(f"{r.get('version',''):<34}C{os_major(r.get('version',''))}"
                  f"  {r.get('build_timestamp','')[:10]}{flag}")

    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
