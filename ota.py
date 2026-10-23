#!/usr/bin/env python3
"""
OTA 一键工具：查询 ROM 链接 → 提取分区镜像

数据源（按优先级）:
  1. ROMer 索引库 (rom.yule.ink)  - 长期有效链接，覆盖广
  2. OPlus-Tracker (tomboy_pro)   - 官方实时接口，10分钟过期

用法:
    ./ota.py link <model> [--c16|--c17|--c15]     查下载链接
    ./ota.py get <model> <partition[,partition2]>  查链接并提取分区
    ./ota.py parts <url-or-model>                  列出分区

示例:
    ./ota.py link PJZ110
    ./ota.py link PJZ110 --c16
    ./ota.py get PJZ110 dtbo,boot,init_boot
    ./ota.py parts PJZ110

环境:
    PDG=/workspace/payload-dumper/pdg   提取器路径
    提取结果输出到 <OUTDIR>/<model>/
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ROMER_API = "https://rom.yule.ink/api/ota/catalog"
ROMER_CACHE = "/tmp/romer_catalog.json"
ROMER_TTL = 3600

PDG = os.environ.get("PDG", "/workspace/payload-dumper/pdg")
OUTDIR = os.environ.get("OUTDIR", "/workspace/ota_out")
TRACKER_DIR = "/workspace/oplus"
TRACKER_PY = os.path.join(TRACKER_DIR, "venv/bin/python")
TRACKER = os.path.join(TRACKER_DIR, "tomboy_pro.py")


def log(msg):
    print(msg, file=sys.stderr)


def romer_fetch(force=False):
    if not force and os.path.exists(ROMER_CACHE):
        if time.time() - os.path.getmtime(ROMER_CACHE) < ROMER_TTL:
            return json.load(open(ROMER_CACHE))
    log("[*] 拉取 ROMer 索引...")
    req = urllib.request.Request(ROMER_API, headers={"User-Agent": "ota-cli/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    open(ROMER_CACHE, "wb").write(data)
    return json.loads(data)


def os_major(version):
    m = re.search(r"[_A-Z0-9]+_(\d+)\.\d+\.\d+", version or "")
    return m.group(1) if m else "?"


def find_romer(model, want_cos=None):
    """在 ROMer 索引里找指定型号；want_cos 形如 '16' 时过滤 ColorOS 大版本"""
    doc = romer_fetch()
    hits = [r for r in doc.get("releases", [])
            if (r.get("model") or "").upper() == model.upper()]
    if want_cos:
        hits = [r for r in hits if os_major(r.get("version")) == want_cos]
    if not hits:
        return None
    # 优先标记为 latest 的；否则取构建时间最新的
    latest = [r for r in hits if r.get("is_latest")]
    pool = latest or hits
    pool.sort(key=lambda r: r.get("build_timestamp") or "")
    return pool[-1]


def find_tracker(model, cos_hint=None):
    """用 tomboy_pro 实时查询，返回 (url, version, ota_version)"""
    if not (os.path.exists(TRACKER_PY) and os.path.exists(TRACKER)):
        return None
    # 分支映射：C15→_11.A  C16→_11.C  C17→_11.F
    branches = ["A", "C", "F"]
    if cos_hint == "15":
        branches = ["A"]
    elif cos_hint == "16":
        branches = ["C"]
    elif cos_hint == "17":
        branches = ["F"]
    for br in branches:
        prefix = f"{model}_11.{br}"
        try:
            out = subprocess.run(
                [TRACKER_PY, TRACKER, prefix, "cn", "--original_link", "1"],
                capture_output=True, text=True, timeout=90, cwd=TRACKER_DIR
            ).stdout
        except Exception as e:
            log(f"[!] 查询 {prefix} 失败: {e}")
            continue
        m_url = re.search(r"• Link: (\S+)", out)
        m_ver = re.search(r"• Version: (\S+)", out)
        m_ota = re.search(r"• Ota Version: (\S+)", out)
        if m_url and m_ver:
            return {
                "url": m_url.group(1),
                "version": m_ver.group(1),
                "ota_version": m_ota.group(1) if m_ota else "",
                "source": "OPlus-Tracker",
                "expires": re.search(r"expire at (.+)", out),
            }
    return None


def _load_models():
    """懒加载机型库模块（可选依赖，缺失时不影响主流程）"""
    try:
        import importlib
        return importlib.import_module("models")
    except Exception:
        return None


def normalize_model(text):
    """
    把用户输入统一解析成 (代号, 分支)。

        "PJZ110"        → ("PJZ110", None)
        "PJZ110_11.C"   → ("PJZ110", "11.C")
        "一加 13"        → ("PJZ110", None)
    """
    m = _load_models()
    if m:
        try:
            return m.resolve_prefix(text)
        except Exception:
            pass
    return text.strip().upper(), None


def cmd_models(args):
    """机型库管理"""
    m = _load_models()
    if not m:
        print("机型库模块 models.py 缺失，请确认它和 ota.py 在同一目录")
        return 1

    if args.action == "sync":
        n = m.sync(force=args.force)
        print(f"同步完成：{n} 个文件")
        return 0

    if args.action == "search":
        if not args.keyword:
            print("用法: ota.py models search <关键词>")
            return 1
        hits = m.suggest(args.keyword)
        if not hits:
            print(f"未找到与 {args.keyword!r} 匹配的机型")
            return 1
        print(f"{'代号':<18}{'机型':<32}{'品牌'}")
        print("-" * 68)
        for it in hits:
            print(f"{it['code']:<18}{it['name']:<32}{it['brand']}")
        return 0

    if args.action == "resolve":
        if not args.keyword:
            print("用法: ota.py models resolve <文本>")
            return 1
        code, br = m.resolve_prefix(args.keyword)
        print(f"输入: {args.keyword}")
        print(f"代号: {code}")
        print(f"分支: {br or '(未指定，需配合 --c15/--c16/--c17)'}")
        info = m.lookup(code)
        if info:
            print(f"机型: {info['name']}  [{info['brand']}]")
        return 0

    if args.action == "list":
        items = m._load(verbose=True)
        print(f"共 {len(items)} 条机型记录")
        return 0

    print("用法: ota.py models {sync|search|resolve|list}")
    return 1


def cmd_link(args):
    raw = args.model
    model, br = normalize_model(raw)
    if model != raw.strip().upper():
        log(f"[*] 机型解析: {raw} → {model}" + (f" (分支 {br})" if br else ""))

    want = {"15": "15", "16": "16", "17": "17"}.get(args.cos) if args.cos else None
    # 从输入里带的分支推断 ColorOS 大版本
    if not want and br:
        want = {"A": "15", "C": "16", "F": "17", "H": "17"}.get(br[-1].upper())

    log(f"[*] 查询 {model} ...")
    r = find_romer(model, want)
    if r:
        print(f"来源:     ROMer 索引")
        print(f"机型:     {r.get('device')}")
        print(f"型号:     {r.get('model')}")
        print(f"版本:     {r.get('version')}")
        print(f"OTA:      {r.get('ota_version')}")
        print(f"系统:     ColorOS {os_major(r.get('version'))}")
        print(f"补丁:     {r.get('security_patch','-')}")
        print(f"构建:     {r.get('build_timestamp','-')}")
        src = r.get("source_url") or ""
        if "downloadCheck" in src:
            print(f"原始页:   {src}")
            real = resolve_dynamic(src)
            print(f"下载:     {real}")
            print(f"          （签名链接，约 10 分钟内有效）")
        else:
            print(f"下载:     {src}")
            print(f"          （静态地址，长期有效）")
        return 0

    log(f"[!] ROMer 无 {model} 记录，尝试官方接口...")
    t = find_tracker(model, want)
    if t:
        print(f"来源:     {t['source']}（链接约 10 分钟过期）")
        print(f"型号:     {model}")
        print(f"版本:     {t['version']}")
        print(f"OTA:      {t['ota_version']}")
        print(f"链接:     {t['url']}")
        return 0

    print(f"未找到 {model} 的 ROM 记录")
    return 1


def resolve_dynamic(url):
    """downloadCheck? 之类的动态链接需要先解析成真实 zip 地址"""
    if "downloadCheck" not in url:
        return url
    log("[*] 解析动态链接...")
    trans = os.path.join(TRACKER_DIR, "C16_transer.py")
    if not os.path.exists(trans):
        log("[!] 缺少 C16_transer.py，无法解析动态链接")
        return url
    try:
        out = subprocess.run(
            [TRACKER_PY, trans, url],
            capture_output=True, text=True, timeout=120, cwd=TRACKER_DIR
        ).stdout
    except Exception as e:
        log(f"[!] 解析失败: {e}")
        return url
    # 取 Success 之后的第一条 https 链接
    m = re.search(r"Success to resolve.*?\n=+\n(https?://\S+)", out, re.S)
    if m:
        log("[+] 动态链接已解析")
        return m.group(1)
    log("[!] 未能解析出真实地址")
    return url


def resolve_url(target, want_cos=None):
    """
    解析出可用下载链接。

    target    型号代号或 URL
    want_cos  ColorOS 大版本（'15'/'16'/'17'），None 表示取最新
    """
    if target.lower().startswith("http"):
        return resolve_dynamic(target)

    model = target.upper()

    # 1. 优先 ROMer 索引（可按版本过滤）
    r = find_romer(model, want_cos)
    if r and r.get("source_url"):
        log(f"[*] 使用 ROMer 记录: {r.get('version')}")
        return resolve_dynamic(r["source_url"])

    # 2. 回退官方接口
    t = find_tracker(model, want_cos)
    if t:
        log(f"[*] 使用官方接口: {t['version']}")
        return t["url"]

    # 3. 指定了版本但没找到，明确提示
    if want_cos:
        log(f"[!] 未找到 ColorOS {want_cos} 的版本，可能该机型没有此分支")
    return None


def cmd_parts(args):
    raw = args.target
    model, br = normalize_model(raw)
    want = getattr(args, "cos", None)
    if not want and br:
        want = {"A": "15", "C": "16", "F": "17", "H": "17"}.get(br[-1].upper())
    url = resolve_url(model, want)
    if not url:
        print("无法解析出下载链接")
        return 1
    log("[*] 读取分区列表（仅元数据）...")
    p = subprocess.run([PDG, "-l", url], capture_output=True, text=True, timeout=180)
    for line in p.stdout.splitlines():
        if "Found partitions" in line or not line.startswith("Found"):
            m = re.search(r"Found partitions:\s*(.+)", line)
            if m:
                parts = [x.strip() for x in m.group(1).split(",")]
                print(f"共 {len(parts)} 个分区:\n")
                for x in parts:
                    print(f"  {x}")
                return 0
    print(p.stdout[-2000:] or p.stderr[-2000:])
    return 1


def cmd_get(args):
    raw = args.model
    model, br = normalize_model(raw)
    if model != raw.strip().upper():
        log(f"[*] 机型解析: {raw} → {model}" + (f" (分支 {br})" if br else ""))

    # 版本选择：优先 --cXX，其次输入里带的分支
    want = None
    if getattr(args, "cos", None):
        want = args.cos
    elif br:
        want = {"A": "15", "C": "16", "F": "17", "H": "17"}.get(br[-1].upper())

    url = resolve_url(model, want)
    if not url:
        print("无法解析出下载链接")
        return 1

    # 输出目录带版本后缀，避免不同版本混在一起
    suffix = f"_c{want}" if want else ""
    outdir = os.path.join(OUTDIR, model + suffix)
    os.makedirs(outdir, exist_ok=True)

    parts = [x.strip() for x in args.partitions.split(",") if x.strip()]

    log(f"[*] 提取 {', '.join(parts)} → {outdir}")
    cmd = [PDG, "-q", "-c", "4", "-p", ",".join(parts), "-o", outdir, url]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        print("[!] 提取失败:")
        print((p.stderr or p.stdout)[-2000:])
        return p.returncode

    print(f"输出目录: {outdir}\n")
    for f in sorted(os.listdir(outdir)):
        fp = os.path.join(outdir, f)
        if os.path.isfile(fp):
            sz = os.path.getsize(fp)
            print(f"  {f:<28}{sz:>12,} 字节")
    return 0


def main():
    ap = argparse.ArgumentParser(description="OTA 查询与分区提取")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("link", help="查询下载链接")
    p1.add_argument("model")
    p1.add_argument("--c15", dest="cos", action="store_const", const="15")
    p1.add_argument("--c16", dest="cos", action="store_const", const="16")
    p1.add_argument("--c17", dest="cos", action="store_const", const="17")
    p1.set_defaults(func=cmd_link)

    p2 = sub.add_parser("parts", help="列出分区")
    p2.add_argument("target", help="URL 或型号")
    p2.add_argument("--c15", dest="cos", action="store_const", const="15")
    p2.add_argument("--c16", dest="cos", action="store_const", const="16")
    p2.add_argument("--c17", dest="cos", action="store_const", const="17")
    p2.set_defaults(func=cmd_parts)

    p3 = sub.add_parser("get", help="提取分区")
    p3.add_argument("model")
    p3.add_argument("partitions", help="逗号分隔，如 dtbo,boot")
    p3.add_argument("--c15", dest="cos", action="store_const", const="15",
                    help="指定 ColorOS 15（默认取最新）")
    p3.add_argument("--c16", dest="cos", action="store_const", const="16",
                    help="指定 ColorOS 16")
    p3.add_argument("--c17", dest="cos", action="store_const", const="17",
                    help="指定 ColorOS 17")
    p3.set_defaults(func=cmd_get)

    p4 = sub.add_parser("models", help="机型库管理（同步/搜索/解析）")
    p4.add_argument("action", choices=["sync", "search", "resolve", "list"])
    p4.add_argument("keyword", nargs="?", help="关键词或型号文本")
    p4.add_argument("--force", action="store_true", help="强制重新同步")
    p4.set_defaults(func=cmd_models)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
