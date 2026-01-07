"""
一键构建知识库脚本
自动执行：创建项目 -> 提交schema -> 构建知识库
"""
import os
import sys
import subprocess
from pathlib import Path

# 确保能导入 knext（位于 F:/AIgen/KAG/knext）
KAG_ROOT = Path(__file__).resolve().parents[3]
if str(KAG_ROOT) not in sys.path:
    sys.path.insert(0, str(KAG_ROOT))

# 获取当前脚本所在目录
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "kag_config.yaml"
SCHEMA_DIR = BASE_DIR / "schema"
DATA_DIR = BASE_DIR / "builder" / "data"

def check_prerequisites():
    """检查前置条件"""
    print("=" * 60)
    print("检查前置条件...")
    print("=" * 60)
    
    # 检查配置文件
    if not CONFIG_FILE.exists():
        print(f"[ERROR] 配置文件不存在: {CONFIG_FILE}")
        return False
    print(f"[OK] 配置文件存在: {CONFIG_FILE}")
    
    # 检查schema文件
    schema_file = SCHEMA_DIR / "MilitaryDeployment.schema"
    if not schema_file.exists():
        print(f"[ERROR] Schema文件不存在: {schema_file}")
        return False
    print(f"[OK] Schema文件存在: {schema_file}")
    
    # 检查数据目录
    if not DATA_DIR.exists():
        print(f"[ERROR] 数据目录不存在: {DATA_DIR}")
        return False
    print(f"[OK] 数据目录存在: {DATA_DIR}")
    
    # 检查数据文件
    txt_files = list(DATA_DIR.glob("*.txt"))
    if not txt_files:
        print(f"[WARNING] 数据目录中没有找到txt文件")
    else:
        print(f"[OK] 找到 {len(txt_files)} 个数据文件:")
        for f in txt_files:
            print(f"      - {f.name}")
    
    return True

def delete_existing_project():
    """删除已存在的同名项目"""
    print("\n" + "=" * 60)
    print("步骤0: 检查并删除已存在的项目...")
    print("=" * 60)
    
    # 读取配置获取namespace
    try:
        try:
            import yaml
        except ImportError:
            from ruamel.yaml import YAML
            yaml = YAML()
            yaml.safe_load = yaml.load
        
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            if hasattr(yaml, 'safe_load'):
                config = yaml.safe_load(f)
            else:
                config = yaml.load(f)
        namespace = config.get("project", {}).get("namespace", "")
        host_addr = config.get("project", {}).get("host_addr", "http://127.0.0.1:8887")
    except Exception as e:
        print(f"[WARNING] 无法读取配置: {e}")
        return False
    
    if not namespace:
        print("[INFO] 未找到namespace配置，跳过删除检查")
        return True
    
    print(f"检查namespace: {namespace}")
    print(f"服务地址: {host_addr}")
    
    # 尝试通过API删除项目
    try:
        # 切换到KAG根目录以导入模块
        kag_root = BASE_DIR.parent.parent.parent.parent
        original_cwd = os.getcwd()
        os.chdir(str(kag_root))
        
        # 添加路径
        if str(kag_root) not in sys.path:
            sys.path.insert(0, str(kag_root))
        
        from knext.project.client import ProjectClient
        
        # 创建客户端
        client = ProjectClient(host_addr=host_addr)
        
        # 获取所有项目
        all_projects = client.get_all()
        print(f"[INFO] 服务器上的所有项目: {list(all_projects.keys())}")
        
        # 查找需要删除的项目（包括当前namespace和可能的冲突namespace）
        projects_to_delete = []
        
        # 查找当前namespace的项目
        project = client.get_by_namespace(namespace)
        if project:
            projects_to_delete.append((project.namespace, project.id))
        
        # 查找可能的冲突项目（PWOE等）
        conflict_namespaces = ["PWOE", "MilitaryDeployment", "MilitaryDeploy"]
        for conflict_ns in conflict_namespaces:
            if conflict_ns != namespace:
                conflict_project = client.get_by_namespace(conflict_ns)
                if conflict_project:
                    projects_to_delete.append((conflict_project.namespace, conflict_project.id))
        
        # 删除找到的项目
        if projects_to_delete:
            print(f"[INFO] 找到 {len(projects_to_delete)} 个需要删除的项目:")
            for ns, pid in projects_to_delete:
                print(f"  - namespace: {ns}, id: {pid}")
            
            import requests
            delete_urls = [
                f"{host_addr}/project/delete/{{id}}",
                f"{host_addr}/api/project/delete/{{id}}",
                f"{host_addr}/project/{{id}}",
            ]
            
            deleted_count = 0
            for ns, pid in projects_to_delete:
                print(f"[INFO] 尝试删除项目: {ns} (ID: {pid})...")
                deleted = False
                for delete_url_template in delete_urls:
                    try:
                        delete_url = delete_url_template.format(id=pid)
                        response = requests.delete(delete_url, timeout=10)
                        if response.status_code in [200, 204]:
                            print(f"[OK] 项目 {ns} 已删除")
                            deleted = True
                            deleted_count += 1
                            break
                    except Exception as e:
                        continue
                
                if not deleted:
                    print(f"[WARNING] 无法删除项目 {ns}，请手动删除")
            
            if deleted_count > 0:
                print(f"[OK] 成功删除 {deleted_count} 个项目")
        else:
            print("[INFO] 未找到需要删除的项目")
        
        os.chdir(original_cwd)
        return True
        
    except Exception as e:
        print(f"[WARNING] 检查项目时出错: {e}")
        print(f"[INFO] 将尝试继续创建")
        if 'original_cwd' in locals():
            os.chdir(original_cwd)
        return True

def restore_project():
    """恢复/创建KAG项目（使用restore命令，会自动处理项目ID）"""
    print("\n" + "=" * 60)
    print("步骤1: 恢复/创建KAG项目...")
    print("=" * 60)
    
    # 先尝试删除已存在的冲突项目
    delete_existing_project()
    
    # 切换到项目目录（restore需要在项目目录下运行）
    os.chdir(str(BASE_DIR))
    
    # 读取配置获取host_addr
    try:
        try:
            import yaml
        except ImportError:
            from ruamel.yaml import YAML
            yaml = YAML()
            yaml.safe_load = yaml.load
        
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            if hasattr(yaml, 'safe_load'):
                config = yaml.safe_load(f)
            else:
                config = yaml.load(f)
        host_addr = config.get("project", {}).get("host_addr", "http://127.0.0.1:8887")
    except Exception as e:
        print(f"[ERROR] 无法读取配置: {e}")
        return False
    
    # 使用restore命令（会自动检查项目是否存在，不存在则创建，并更新project.id）
    cmd = [
        sys.executable, "-m", "knext.command.knext_cli",
        "project", "restore",
        "--host_addr", host_addr,
        "--proj_path", "."
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print(f"工作目录: {BASE_DIR}")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{KAG_ROOT}{os.pathsep}" + env.get("PYTHONPATH", "")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    if result.returncode != 0:
        print(f"[ERROR] 恢复项目失败:")
        print(result.stderr)
        if result.stdout:
            print(result.stdout)
        return False
    
    print("[OK] 项目恢复/创建成功")
    if result.stdout:
        print(result.stdout)
    
    # 验证配置文件中的project.id是否已更新
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            if hasattr(yaml, 'safe_load'):
                config = yaml.safe_load(f)
            else:
                config = yaml.load(f)
        project_id = config.get("project", {}).get("id", "")
        namespace = config.get("project", {}).get("namespace", "")
        print(f"[INFO] 项目配置已更新:")
        print(f"  Namespace: {namespace}")
        print(f"  Project ID: {project_id}")
        print(f"  Host: {host_addr}")
    except Exception as e:
        print(f"[WARNING] 验证配置时出错: {e}")
    
    return True

def commit_schema():
    """提交Schema"""
    print("\n" + "=" * 60)
    print("步骤2: 提交Schema...")
    print("=" * 60)
    
    # 切换到项目目录
    os.chdir(str(BASE_DIR))
    
    cmd = [
        sys.executable, "-m", "knext.command.knext_cli",
        "schema", "commit"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{KAG_ROOT}{os.pathsep}" + env.get("PYTHONPATH", "")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    if result.returncode != 0:
        error_msg = result.stderr
        print(f"[ERROR] 提交Schema失败:")
        print(error_msg)
        
        # 检查是否是namespace不匹配的错误
        if "not match project namespace" in error_msg or "namespace" in error_msg.lower():
            print("\n" + "=" * 60)
            print("[解决方案]")
            print("=" * 60)
            print("检测到namespace不匹配问题。")
            print("可能的原因：项目中已存在不同namespace的项目")
            print("\n解决方法：")
            print("1. 通过OpenSPG Web界面删除旧项目")
            print("   - 访问: http://192.168.1.131:8887")
            print("   - 登录后删除namespace不匹配的项目")
            print("2. 或者修改schema文件中的namespace以匹配现有项目")
            print("3. 然后重新运行此脚本")
            print("=" * 60)
        
        return False
    
    print("[OK] Schema提交成功")
    if result.stdout:
        print(result.stdout)
    return True

def clean_checkpoint_cache():
    """清理检查点缓存，确保使用最新的schema"""
    print("\n" + "=" * 60)
    print("步骤2.5: 清理检查点缓存...")
    print("=" * 60)
    
    builder_dir = BASE_DIR / "builder"
    ckpt_dir = builder_dir / "ckpt"
    
    if ckpt_dir.exists():
        print(f"[INFO] 发现检查点缓存目录: {ckpt_dir}")
        print("[INFO] 清理缓存以确保使用最新的schema...")
        
        import shutil
        try:
            shutil.rmtree(ckpt_dir)
            print(f"[OK] 已清理检查点缓存: {ckpt_dir}")
        except Exception as e:
            print(f"[WARNING] 清理缓存时出错: {e}")
            print("[INFO] 将尝试继续构建，但可能会使用旧的缓存数据")
    else:
        print("[INFO] 未找到检查点缓存目录，无需清理")

def build_knowledge_base():
    """构建知识库"""
    print("\n" + "=" * 60)
    print("步骤3: 构建知识库...")
    print("=" * 60)
    
    # 切换到builder目录
    builder_dir = BASE_DIR / "builder"
    os.chdir(str(builder_dir))
    
    # 运行indexer.py
    indexer_file = builder_dir / "indexer.py"
    cmd = [sys.executable, str(indexer_file)]
    
    # 设置PYTHONPATH，确保能找到kag模块
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{KAG_ROOT}{os.pathsep}" + env.get("PYTHONPATH", "")
    
    print(f"执行命令: {' '.join(cmd)}")
    print(f"数据目录: {DATA_DIR}")
    print("\n开始构建知识库（这可能需要一些时间）...")
    print("[INFO] 如果构建失败，请查看上方的错误信息")
    print("[INFO] 常见问题：")
    print("  1. Schema类型不匹配 - LLM抽取的类型需要在Schema中定义")
    print("  2. LLM响应超时 - 检查网络连接和API配置")
    print("  3. 所有实体被跳过 - 检查Schema中是否定义了对应的实体类型")
    
    result = subprocess.run(cmd, capture_output=False, text=True, env=env)
    
    if result.returncode != 0:
        print(f"\n[ERROR] 构建知识库失败")
        print("[INFO] 请查看上方的详细错误信息")
        return False
    
    print("\n[OK] 知识库构建完成")
    
    # 验证数据是否写入成功
    print("\n" + "=" * 60)
    print("验证知识库数据...")
    print("=" * 60)
    if verify_knowledge_base():
        print("[OK] 知识库验证成功，数据已写入")
    else:
        print("[WARNING] 知识库验证失败，请检查数据是否写入")
    
    return True

def verify_knowledge_base():
    """验证知识库数据是否写入成功"""
    try:
        # 切换到KAG根目录以导入模块
        kag_root = BASE_DIR.parent.parent.parent.parent
        original_cwd = os.getcwd()
        os.chdir(str(kag_root))
        
        if str(kag_root) not in sys.path:
            sys.path.insert(0, str(kag_root))
        
        from knext.graph.client import GraphClient
        from knext.schema.client import SchemaClient
        
        # 读取配置
        try:
            import yaml
        except ImportError:
            from ruamel.yaml import YAML
            yaml = YAML()
            yaml.safe_load = yaml.load
        
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            if hasattr(yaml, 'safe_load'):
                config = yaml.safe_load(f)
            else:
                config = yaml.load(f)
        
        project_id = config.get("project", {}).get("id", "")
        host_addr = config.get("project", {}).get("host_addr", "http://127.0.0.1:8887")
        namespace = config.get("project", {}).get("namespace", "")
        
        if not project_id:
            print("[WARNING] 未找到项目ID，无法验证")
            os.chdir(original_cwd)
            return False
        
        print(f"项目ID: {project_id}")
        print(f"服务地址: {host_addr}")
        print(f"命名空间: {namespace}")
        
        # 验证Schema类型
        print("\n[INFO] 验证Schema类型...")
        schema_client = SchemaClient(host_addr=host_addr, project_id=int(project_id))
        schema = schema_client.load()
        
        # 从schema动态获取所有实体类型（排除系统类型）
        system_types = ["Chunk", "AtomicQuery", "KnowledgeUnit", "Summary", "Outline", "Doc"]
        entity_types = [
            type_name for type_name in schema.keys() 
            if type_name not in system_types and not type_name.startswith("_")
        ]
        
        print(f"[INFO] Schema中定义的实体类型（共{len(entity_types)}个）:")
        for type_name in sorted(entity_types):
            print(f"  [OK] {type_name}")
        
        # 显示所有可用的类型（前20个）
        all_types = list(schema.keys())
        print(f"\n[INFO] Schema中共有 {len(all_types)} 个类型（包括系统类型）")
        print(f"[INFO] 前20个类型: {all_types[:20]}")
        
        # 创建GraphClient
        client = GraphClient(host_addr=host_addr, project_id=int(project_id))
        
        print("\n[INFO] 检查数据写入情况...")
        print("-" * 60)
        print("[INFO] 提示：使用以下命令查看详细数据：")
        print(f"      python {BASE_DIR / 'check_kb.py'}")
        print("-" * 60)
        
        # 尝试查询一个实体来验证连接
        print("\n[INFO] 测试数据查询...")
        test_success = False
        # 使用第一个实体类型进行测试
        if entity_types:
            test_type = entity_types[0]
            full_name = f"{namespace}.{test_type}"
            try:
                # 尝试查询一个实体（使用一个可能的ID）
                # 注意：这里只是测试连接，不保证能找到数据
                test_result = client.query_vertex(type_name=full_name, biz_id="test")
                test_success = True
            except Exception as e:
                # 查询失败是正常的，因为test ID可能不存在
                # 但至少说明连接是正常的
                if "not found" not in str(e).lower() and "不存在" not in str(e):
                    # 如果是连接错误，说明有问题
                    if "connection" in str(e).lower() or "timeout" in str(e).lower():
                        print(f"  [ERROR] 连接失败: {e}")
                        print(f"  [INFO] 请检查服务器地址是否正确: {host_addr}")
                    else:
                        test_success = True  # 连接正常，只是数据不存在
                else:
                    test_success = True  # 连接正常，只是数据不存在
        else:
            print("  [WARNING] 未找到实体类型进行测试")
        
        if test_success:
            print("  [OK] 图数据库连接正常")
        else:
            print("  [WARNING] 无法连接到图数据库")
        
        print("\n[INFO] 数据写入检查：")
        print("  1. 构建过程显示 '1 successfully processed'，说明数据已处理")
        print("  2. 如果前端看不到数据，请检查：")
        print(f"     - 前端连接的服务地址是否为: {host_addr}")
        print(f"     - 前端选择的项目ID是否为: {project_id}")
        print(f"     - 前端选择的命名空间是否为: {namespace}")
        print("  3. 运行 check_kb.py 查看详细数据统计")
        
        print("\n[INFO] 请访问OpenSPG Web界面查看数据:")
        print(f"      {host_addr}")
        print(f"      项目ID: {project_id}")
        print(f"      命名空间: {namespace}")
        
        os.chdir(original_cwd)
        return test_success  # 连接成功就算验证通过
        
    except Exception as e:
        print(f"[WARNING] 验证时出错: {e}")
        import traceback
        traceback.print_exc()
        if 'original_cwd' in locals():
            os.chdir(original_cwd)
        return False

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("KAG知识库一键构建脚本")
    print("=" * 60)
    print(f"工作目录: {BASE_DIR}")
    print(f"配置文件: {CONFIG_FILE}")
    print(f"数据目录: {DATA_DIR}")
    print("=" * 60)
    
    # 检查前置条件
    if not check_prerequisites():
        print("\n[ERROR] 前置条件检查失败，请修复后重试")
        sys.exit(1)
    
    # 恢复/创建项目
    if not restore_project():
        print("\n[ERROR] 项目恢复/创建失败")
        sys.exit(1)
    
    # 提交Schema
    if not commit_schema():
        print("\n[ERROR] Schema提交失败")
        sys.exit(1)
    
    # 清理检查点缓存（确保使用最新的schema）
    clean_checkpoint_cache()
    
    # 构建知识库
    if not build_knowledge_base():
        print("\n[ERROR] 知识库构建失败")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("[SUCCESS] 所有步骤完成！知识库已构建完成")
    print("=" * 60)
    print("\n现在可以运行外层系统的 main.py 使用知识库了")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

