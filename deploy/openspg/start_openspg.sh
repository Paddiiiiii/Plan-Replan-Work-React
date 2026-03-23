#!/usr/bin/env bash
# 在本机 Docker 启动 OpenSPG（KAG 依赖的图谱与检索后端）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 docker，请先安装 Docker。" >&2
  exit 1
fi

docker compose -f docker-compose.yml up -d

echo ""
echo "OpenSPG 已启动（若首次拉镜像需等待几分钟）"
echo "  Web UI:  http://127.0.0.1:8887"
echo "  默认账号: openspg  密码: openspg@kag"
echo ""
echo "将 MilitaryDeployment 工程同步到本机 OpenSPG（在示例目录执行）:"
echo "  cd KAG/kag/examples/MilitaryDeployment"
echo "  knext project restore --host_addr http://127.0.0.1:8887 --proj_path ."
echo ""
