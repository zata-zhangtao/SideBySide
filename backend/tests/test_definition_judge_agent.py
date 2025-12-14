"""
Test definition_judge_agent - 语义相似判定
"""

import os
from pathlib import Path


def main():
    import sys
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    print("=" * 80)
    print("测试 definition_judge_agent")
    print("=" * 80)

    if not os.getenv("DASHSCOPE_API_KEY"):
        print("⚠️  警告: DASHSCOPE_API_KEY 未设置，跳过在线评估测试")
        return

    from app.services.agents import judge_definitions

    word_items = [
        {"term": "meticulous", "definition": "一丝不苟的；非常仔细的"},
        {"term": "serene", "definition": "宁静的；安详的"},
        {"term": "robust", "definition": "强健的；稳固的；鲁棒的"},
        {"term": "gale", "definition": "大风"},
    ]

    # 用户答案刻意使用同义或表达差异
    user_answers = {
        "meticulous": "非常细致，注意每个小细节的",
        "serene": "平静安宁的",
        "robust": "脆弱的，容易坏的",  # 故意错误
        "gale":"暴风",
    }

    result = judge_definitions(word_items, user_answers, strictness="medium", language="zh")

    print("\n评估结果：")
    for r in result:
        print(f"- {r['term']}: {r['verdict']} (score={r['score']})")
        print(f"  reason: {r.get('reason','')}")
        if r.get("missing_keywords"):
            print(f"  missing: {r['missing_keywords']}")

    print("\n" + "=" * 80)
    print("完成")


if __name__ == "__main__":
    main()

