#!/bin/sh
# 一键初始化：创建 venv、装依赖、同步机型库
set -e

PY=${PYTHON:-python3}
DIR=$(cd "$(dirname "$0")" && pwd)
cd "$DIR"

echo "==> 检查 Python"
$PY --version || { echo "缺少 python3"; exit 1; }

echo "==> 创建虚拟环境"
[ -d venv ] || $PY -m venv venv

echo "==> 安装依赖"
./venv/bin/python -m pip install --quiet --upgrade pip
./venv/bin/python -m pip install --quiet -r requirements.txt

echo "==> 同步机型库"
./venv/bin/python ota.py models sync || echo "（机型库同步失败，可稍后重试）"

echo
echo "==> 完成。试试："
echo "    ./ota.py models search \"一加 13\""
echo "    ./ota.py link PJZ110 --c16"
echo
echo "注意：分区提取需要 pdg（payload-dumper-go），"
echo "      未安装时 link / parts 仍可用。"
