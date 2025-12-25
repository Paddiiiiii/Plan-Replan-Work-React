import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
BASE_DIR_PARENT = BASE_DIR.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR_PARENT) not in sys.path:
    sys.path.insert(0, str(BASE_DIR_PARENT))

try:
    from context_manager import ContextManager
except ImportError:
    from context_manager import ContextManager

if __name__ == "__main__":
    print("更新装备信息库...")
    context_manager = ContextManager()
    count = context_manager.update_equipment_base()
    print(f"✓ 已更新 {count} 条装备信息")

