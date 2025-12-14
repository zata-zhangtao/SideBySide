"""
Test images2words_agent - 基本功能测试
"""

import json
import os
from pathlib import Path


def main():
    """测试 images2words_agent 基本功能"""

    # 添加项目根目录到 sys.path
    import sys
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # 测试图片路径
    test_image = Path(__file__).parent / "asset" / "image.png"

    print("=" * 80)
    print("测试 images2words_agent")
    print("=" * 80)

    # 检查图片是否存在
    print(f"\n1. 检查测试图片: {test_image}")
    if not test_image.exists():
        print(f"❌ 图片不存在: {test_image}")
        return
    print(f"✓ 图片存在 ({test_image.stat().st_size} bytes)")

    # 导入模块
    print("\n2. 导入模块...")
    try:
        from app.services.agents import extract_vocabulary_from_image
        print("✓ 导入成功")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return

    # 检查 API Key
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("\n⚠️  警告: DASHSCOPE_API_KEY 未设置")
        print("请设置环境变量后再运行测试")
        return

    # 处理图片
    print("\n3. 处理图片...")
    try:
        result = extract_vocabulary_from_image(test_image)
        print(f"✓ 成功提取 {len(result)} 个单词")
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 显示结果
    print("\n4. 提取结果（前10个）:")
    print("-" * 80)
    for i, item in enumerate(result[:10], 1):
        print(f"{i}. {item['term']}")
        if item.get('definition'):
            print(f"   释义: {item['definition']}")
        if item.get('example'):
            print(f"   例句: {item['example']}")
        print()

    # 保存完整结果
    output_file = Path(__file__).parent / "test_output.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 完整结果已保存到: {output_file}")
    print("\n" + "=" * 80)
    print(f"测试完成！共提取 {len(result)} 个单词")
    print("=" * 80)


if __name__ == "__main__":
    main()
