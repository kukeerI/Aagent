# test_orchestrator.py
from realorchestrator import RealOrchestrator # 修正了导入名

if __name__ == "__main__":
    agent = RealOrchestrator()
    
    print("\n" + "="*50)
    print("测试任务：写一个冒泡排序算法，并解释原理")
    print("="*50)
    agent.start_work("写一个冒泡排序算法，并解释原理。")