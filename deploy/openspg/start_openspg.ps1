# 在本机 Docker 启动 OpenSPG（KAG 依赖的图谱与检索后端）
# 前置：已安装 Docker Desktop（Windows）并确保 docker compose 可用
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 docker 命令，请先安装并启动 Docker Desktop。"
}

docker compose -f docker-compose.yml up -d

Write-Host ""
Write-Host "OpenSPG 已启动（若首次拉镜像需等待几分钟）"
Write-Host "  Web UI:  http://127.0.0.1:8887"
Write-Host "  默认账号: openspg  密码: openspg@kag"
Write-Host ""
Write-Host "将 MilitaryDeployment 工程同步到本机 OpenSPG（在示例目录执行）:"
Write-Host "  cd KAG\kag\examples\MilitaryDeployment"
Write-Host "  knext project restore --host_addr http://127.0.0.1:8887 --proj_path ."
Write-Host ""
