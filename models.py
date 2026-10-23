#!/usr/bin/env python3
"""
机型库模块：从 MobileModels 仓库同步机型代号，支持镜像加速与自动回退

设计参考 com.rna.tools 的 getrom.sh：
  - 多镜像自动回退（gh-proxy.com / 直连 raw.githubusercontent.com）
  - 增量校验（内容合法性检查后才落盘）
  - 本地缓存 + TTL

对外接口：
    sync(force=False)             同步机型库，返回成功文件数
    lookup(code_or_name)          按代号或名称查机型，返回候选列表
    resolve_prefix(text)          把 "一加13" / "PJZ110_11.C" 解析成规范前缀
    suggest(text)                 模糊搜索，返回 (代号, 名称, 品牌) 列表
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# ---- 配置 ----
DB_DIR = os.environ.get("ROMDB_DIR", "/workspace/oplus/romdb")
MIRRORS = [
    "https://gh-proxy.com/https://raw.githubusercontent.com/KHwang9883/MobileModels/refs/heads/master/brands/{f}",
    "https://ghfast.top/https://raw.githubusercontent.com/KHwang9883/MobileModels/refs/heads/master/brands/{f}",
    "https://raw.githubusercontent.com/KHwang9883/MobileModels/refs/heads/master/brands/{f}",
]
FILES = {
    "oppo_cn.md": "OPPO",
    "oneplus.md": "OnePlus",
    "realme_cn.md": "realme",
    "vivo_cn.md": "vivo",
    "xiaomi.md": "Xiaomi",
}
TTL = 7 * 24 * 3600  # 机型库 7 天更新一次足够
UA = "ota-cli/1.0"


def log(msg):
    print(msg, file=sys.stderr)


# ---------- 下载 ----------
def _fetch_one(fname, timeout=45):
    """依次尝试各镜像，返回 (内容, 使用的镜像) 或 (None, None)"""
    for tmpl in MIRRORS:
        url = tmpl.format(f=fname)
        host = url.split("/")[2]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 100:
                continue
            text = data.decode("utf-8", errors="replace")
            # 合法性校验：必须有 Markdown 结构
            if "#" not in text and "**" not in text:
                continue
            return text, host
        except Exception:
            continue
    return None, None


# ---------- 解析 ----------
def parse_mm(text):
    """
    解析 MobileModels 的 .md 文件。

    实际格式示例：

        **一加 13 (`dodge`):**

        `PJZ110`: 一加 13 国行版

        `CPH2649`: 一加 13 印度版

        **OPPO Find X:**

        `PAFM00`: OPPO Find X 标准版 全网通版

    规则：
      - `**名称 (`codename`):**`  → 段标题，括号内是项目代号
      - ` `CODE`: 描述`             → 具体型号代号
      - 同一段下的多个型号共享段标题

    返回 [(代号, 展示名, 描述)]
    """
    out = []
    seen = set()
    cur_name = None
    cur_codename = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue

        # 段标题：**名称 (`codename`):**
        m = re.match(r"^\*\*(.+?)\*\*\s*[:：]?\s*$", line)
        if m:
            inner = m.group(1).strip()
            # 提取括号内的 codename（反引号包着）
            cm = re.search(r"[（(]\s*`([^`]+)`\s*[)）]", inner)
            cur_codename = cm.group(1) if cm else None
            # 去掉括号部分得到纯名称
            name = re.sub(r"\s*[（(]\s*`[^`]+`\s*[)）]\s*", "", inner).strip()
            name = name.rstrip(":：").strip()
            cur_name = name or None
            continue

        # 型号行：`CODE`: 描述
        if line.startswith("`"):
            cm = re.match(r"^`([^`]+)`\s*[:：]\s*(.*)$", line)
            if not cm:
                continue
            code = cm.group(1).strip()
            desc = cm.group(2).strip()
            # 展示名优先用描述（更具体），退化为段标题
            label = desc or cur_name or code
            key = (code, label)
            if key not in seen:
                seen.add(key)
                out.append((code, label, cur_codename))
            continue

    return out


# ---------- 同步 ----------
def sync(force=False, verbose=True):
    """同步机型库，返回成功下载的文件数"""
    os.makedirs(DB_DIR, exist_ok=True)
    stamp = os.path.join(DB_DIR, ".last_sync")

    if not force and os.path.exists(stamp):
        try:
            if time.time() - os.path.getmtime(stamp) < TTL:
                n = len([f for f in os.listdir(DB_DIR) if f.endswith(".md")])
                if verbose:
                    log(f"[*] 机型库缓存有效（{n} 个文件，7 天内）")
                return n
        except OSError:
            pass

    ok, fail = 0, []
    for fname, brand in FILES.items():
        if verbose:
            log(f"[*] 同步 {brand} 机型库…")
        text, host = _fetch_one(fname)
        if text:
            path = os.path.join(DB_DIR, fname)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, path)
            ok += 1
            if verbose:
                log(f"    ✓ {fname}  ({len(text)//1024} KB, via {host})")
        else:
            fail.append(fname)
            if verbose:
                log(f"    ✗ {fname}  全部镜像失败")

    if ok:
        with open(stamp, "w") as f:
            f.write(str(int(time.time())))
    if fail and verbose:
        log(f"[!] {len(fail)} 个文件失败：{', '.join(fail)}")
    return ok


# ---------- 查询 ----------
_cache = None


def _load(verbose=False):
    """加载本地机型库到内存（只读一次）"""
    global _cache
    if _cache is not None:
        return _cache

    items = []
    if os.path.isdir(DB_DIR):
        for fname, brand in FILES.items():
            path = os.path.join(DB_DIR, fname)
            if not os.path.exists(path):
                continue
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for code, label, codename in parse_mm(text):
                items.append({
                    "code": code,
                    "name": label,
                    "brand": brand,
                    "codename": codename,
                })
    _cache = items
    if verbose:
        log(f"[*] 机型库已加载 {len(items)} 条")
    return items


def suggest(text, limit=20):
    """模糊搜索，按匹配度排序（精确 > 前缀 > 包含）"""
    items = _load()
    if not items:
        return []
    q = text.strip().upper()
    if not q:
        return []

    # 归一化：去掉空格，便于 "一加 13" 匹配 "一加13"
    qn = q.replace(" ", "")

    scored = []
    for it in items:
        code = it["code"].upper()
        name = it["name"].upper()
        namen = name.replace(" ", "")
        score = 0
        if code == q or namen == qn:
            score = 100
        elif namen.startswith(qn):
            # 前缀匹配：越短说明越贴近（"一加 13" 优于 "一加 13R"）
            score = 90 - min(20, len(namen) - len(qn))
        elif code.startswith(q):
            score = 70
        elif qn in namen:
            score = 50 - min(20, namen.index(qn))
        elif q in code:
            score = 40
        else:
            continue

        # 国行加权
        if any(k in it["name"] for k in ("国行", "全网通")):
            score += 5

        scored.append((score, it))

    scored.sort(key=lambda x: (-x[0], x[1]["code"]))
    return [it for _, it in scored[:limit]]


def lookup(code):
    """精确查代号，返回机型信息或 None"""
    items = _load()
    c = code.strip().upper()
    for it in items:
        if it["code"].upper() == c:
            return it
    return None


def resolve_prefix(text):
    """
    把各种输入解析成规范 OTA 前缀。

        "PJZ110"            → ("PJZ110", None)     需补分支
        "PJZ110_11.C"       → ("PJZ110", "11.C")
        "PJZ110_11.C.36_..." → ("PJZ110", "11.C")  带完整版本
        "一加 13"            → ("PJZ110", None)     通过机型库匹配（优先国行）
        "OP 13"             → ("PJZ110", None)
    """
    t = text.strip()
    if not t:
        return None, None

    # 已带分支：XXX_11.Y（Y 是字母，如 A/C/F/H/J；后面可能还跟版本号）
    m = re.match(r"^([A-Za-z0-9]+)_(\d+\.[A-Za-z])(?:_|\.|$)", t)
    if m:
        return m.group(1).upper(), m.group(2)

    # 纯代号（PJZ110 / CPH2649 / ONE A0001 这类）
    if re.match(r"^[A-Za-z]{1,5}[\s]?[A-Z]?\d{3,5}[A-Za-z]?$", t):
        return t.upper(), None

    # 通过机型库查名称，优先国行
    hits = suggest(t, limit=8)
    if hits:
        # 国行/CN 优先
        preferred = [h for h in hits
                     if any(k in h["name"] for k in ("国行", "中国", "全网通", "标准版"))
                     and not any(k in h["name"] for k in ("印度", "欧洲", "北美", "国际"))]
        pick = (preferred or hits)[0]
        return pick["code"].upper(), None

    return t.upper(), None


# ---------- CLI（独立测试用）----------
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "sync":
        n = sync(force="--force" in sys.argv)
        print(f"同步完成：{n} 个文件")
        return 0

    if cmd == "list":
        items = _load(verbose=True)
        brands = {}
        for it in items:
            brands.setdefault(it["brand"], []).append(it)
        for b, arr in brands.items():
            print(f"\n{b}（{len(arr)} 条）")
            for it in arr[:10]:
                print(f"  {it['code']:16} {it['name']}")
            if len(arr) > 10:
                print(f"  … 还有 {len(arr)-10} 条")
        return 0

    if cmd == "find" and len(sys.argv) > 2:
        for it in suggest(sys.argv[2]):
            print(f"{it['code']:16} {it['name']:24} [{it['brand']}]")
        return 0

    if cmd == "resolve" and len(sys.argv) > 2:
        code, br = resolve_prefix(sys.argv[2])
        print(f"代号: {code}")
        print(f"分支: {br or '(未指定)'}")
        return 0

    print("用法: models.py {sync [--force] | list | find <关键词> | resolve <文本>}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
