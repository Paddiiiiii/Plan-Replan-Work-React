import sys
from pathlib import Path
from typing import List, Dict

BASE_DIR = Path(__file__).parent
BASE_DIR_PARENT = BASE_DIR.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR_PARENT) not in sys.path:
    sys.path.insert(0, str(BASE_DIR_PARENT))

def get_equipment_info() -> str:
    """获取装备信息文本
    
    注意：如果要修改装备信息，请直接修改此函数中的文本内容，然后运行此脚本更新数据库。
    文本将被KAG自动解析，提取实体和关系。
    """
    return """轻步兵主要装备突击步枪，其有效射程为300–400米，最大射程可达800米；重装步兵主要装备重型机枪，有效射程为400–500米，最大射程约1000米；机械化步兵主要装备轻型坦克，有效射程为500–600米，最大射程约1200米；坦克部队主要装备重型坦克，有效射程为600–700米，最大射程可达1500米。反坦克步兵主要装备反坦克导弹，有效射程为700–800米，最大射程约1800米；自行火炮的有效射程为800–900米，最大射程约2000米；牵引火炮的有效射程为900–1000米，最大射程可达2200米。防空部队主要装备防空导弹，有效射程为1000–1100米，最大射程约2400米；狙击手主要装备狙击步枪，有效射程为1100–1200米，最大射程可达2600米；特种部队主要装备特种武器，其有效射程为1200–1300米，最大射程约2800米。装甲侦察单位主要装备装甲侦察车，有效射程为1300–1400米，最大射程可达3000米；工兵部队主要装备工兵装备，有效射程为1400–1500米，最大射程约3200米；后勤保障部队主要装备后勤保障装备，有效射程为1500–1600米，最大射程可达3400米；指挥单位主要装备指挥装备，有效射程为1600–1700米，最大射程约3600米；无人机侦察控制单元主要装备无人机侦察控制装备，其有效射程为1700–1800米，最大射程可达3800米。在进行缓冲区距离规划时，应综合考虑不同作战单位及其装备的射程特性，以确保火力覆盖范围的合理性与有效性。"""

if __name__ == "__main__":
    print("更新装备信息库...")
    from context_manager import ContextManager
    context_manager = ContextManager()
    count = context_manager.update_equipment_base()
    print(f"[OK] 已更新 {count} 条装备信息")

