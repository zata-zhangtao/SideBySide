"""
Image to Words Agent using LangGraph

功能：
- 输入：一张图片（字节或路径）
- 输出：图片中的单词、释义以及例句
- 使用dashscope多模态模型和LangGraph工作流
- API密钥从环境变量DASHSCOPE_API_KEY读取

工作流程：
1. 提取节点：使用视觉语言模型识别图片中的所有单词
2. 补充节点：为缺失释义或例句的单词补充完整信息
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, TypedDict

import dashscope
from langgraph.graph import END, START, StateGraph


# 模型名称配置
# 对于多模态（图片）任务，使用视觉语言模型
VISION_MODEL = os.getenv("VISION_MODEL", "qwen3-vl-plus")
# 对于纯文本生成任务，使用文本模型
TEXT_MODEL = os.getenv("TEXT_MODEL", "qwen3-max-preview")


class ImageState(TypedDict, total=False):
    """LangGraph Agent状态定义"""
    image_bytes: bytes
    image_base64: str
    extracted_items: List[Dict[str, Any]]
    completed_items: List[Dict[str, Any]]


def _ensure_api_key() -> str:
    """确保API密钥已设置"""
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("请设置环境变量 DASHSCOPE_API_KEY")
    dashscope.api_key = api_key
    return api_key


def encode_image_to_base64(image_bytes: bytes) -> str:
    """将图片字节编码为base64字符串"""
    return base64.b64encode(image_bytes).decode("utf-8")


def detect_image_format(image_bytes: bytes) -> str:
    """
    检测图片格式，返回MIME类型

    Args:
        image_bytes: 图片字节数据

    Returns:
        MIME类型字符串 (e.g., "image/png", "image/jpeg")
    """
    if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"
    elif image_bytes.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
        return "image/gif"
    elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:12]:
        return "image/webp"
    else:
        # 默认使用PNG
        return "image/png"


def extract_text_from_response(response: Any) -> str:
    """
    从dashscope响应中提取文本内容

    支持多种响应格式，包括多模态API的嵌套结构
    """
    # 首先尝试常见的属性名
    for attr in ("output_text", "text", "message", "content"):
        try:
            v = getattr(response, attr, None)
            if isinstance(v, str) and v.strip():
                return v
        except Exception:
            pass

    # 尝试访问 output 属性
    try:
        if hasattr(response, "output"):
            output = response.output
            # 尝试 choices 格式
            choices = getattr(output, "choices", None)
            if choices and len(choices) > 0:
                choice = choices[0]
                message = getattr(choice, "message", None)
                if message:
                    content = getattr(message, "content", None)
                    # 处理 content 是数组的情况（dashscope 多模态格式）
                    if isinstance(content, list) and len(content) > 0:
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                text = item["text"]
                                if isinstance(text, str) and text.strip():
                                    return text
                            elif isinstance(item, str) and item.strip():
                                return item
                    elif isinstance(content, str) and content.strip():
                        return content
            # 尝试直接访问 text
            text = getattr(output, "text", None)
            if isinstance(text, str) and text.strip():
                return text
            # 如果 output 是字典
            if isinstance(output, dict):
                if "choices" in output and output["choices"]:
                    choice = output["choices"][0]
                    if isinstance(choice, dict):
                        message = choice.get("message", {})
                        if isinstance(message, dict):
                            content = message.get("content")
                            if isinstance(content, list) and len(content) > 0:
                                for item in content:
                                    if isinstance(item, dict) and "text" in item:
                                        text = item["text"]
                                        if isinstance(text, str) and text.strip():
                                            return text
                                    elif isinstance(item, str) and item.strip():
                                        return item
                            elif isinstance(content, str) and content.strip():
                                return content
                if "text" in output:
                    text = output["text"]
                    if isinstance(text, str) and text.strip():
                        return text
    except Exception:
        pass

    # 尝试字典格式
    try:
        if isinstance(response, dict):
            out = response.get("output") or {}
            if isinstance(out, dict):
                # 先尝试 choices 路径（多模态格式）
                if "choices" in out and out["choices"]:
                    choice = out["choices"][0]
                    if isinstance(choice, dict):
                        message = choice.get("message", {})
                        if isinstance(message, dict):
                            content = message.get("content")
                            if isinstance(content, list) and len(content) > 0:
                                for item in content:
                                    if isinstance(item, dict) and "text" in item:
                                        text = item["text"]
                                        if isinstance(text, str) and text.strip():
                                            return text
                                    elif isinstance(item, str) and item.strip():
                                        return item
                            elif isinstance(content, str) and content.strip():
                                return content
                # 尝试直接获取 text
                text = out.get("text") or out.get("content")
                if isinstance(text, str) and text.strip():
                    return text
            # OpenAI 风格的格式
            choices = response.get("choices") or []
            if choices:
                c0 = choices[0]
                if isinstance(c0, dict):
                    message = c0.get("message") or {}
                    if isinstance(message, dict):
                        content = message.get("content")
                        if isinstance(content, list) and len(content) > 0:
                            for item in content:
                                if isinstance(item, dict) and "text" in item:
                                    text = item["text"]
                                    if isinstance(text, str) and text.strip():
                                        return text
                                elif isinstance(item, str) and item.strip():
                                    return item
                        elif isinstance(content, str) and content.strip():
                            return content
            # 直接包含 text
            if "text" in response:
                text = response["text"]
                if isinstance(text, str) and text.strip():
                    return text
    except Exception:
        pass

    # 最后尝试转换为字符串
    return str(response)


def node_extract_words(state: ImageState) -> ImageState:
    """
    LangGraph节点1：从图片中提取单词信息

    使用视觉语言模型识别图片中的所有英语单词，
    并尝试提供释义和例句。
    """
    _ensure_api_key()
    image_base64 = state["image_base64"]

    system_prompt = (
        "你是一个专业的英语词汇识别专家。"
        "你的任务是从图片中识别出所有英语单词，并提供每个单词的释义和例句。"
        "只输出数据，不要添加任何解释性文字。"
    )

    user_prompt = (
        "请仔细分析这张图片，识别出图片中出现的所有英语单词。\n"
        "对于每个单词，请提供：\n"
        "1. 单词本身（term）\n"
        "2. 中文释义（definition）\n"
        "3. 英文例句（example）\n\n"
        "请以JSON数组格式输出，每个元素是一个对象，包含以下字段：\n"
        "- term: 英语单词（字符串）\n"
        "- definition: 中文释义（字符串，简洁明了，不超过20字）\n"
        "- example: 英文例句（字符串，自然流畅）\n\n"
        "如果图片中没有单词或无法识别，请返回空数组 []。\n"
        "只输出JSON数组，不要添加任何其他文字、代码块标记或解释。\n\n"
        "示例格式：\n"
        '[\n'
        '  {"term": "meticulous", "definition": "一丝不苟的；细致的", "example": "She kept meticulous notes of every meeting."},\n'
        '  {"term": "serene", "definition": "宁静的；安详的", "example": "The lake looked serene in the morning light."}\n'
        ']'
    )

    # 构建消息 - dashscope多模态API格式
    image_bytes = state.get("image_bytes")
    if image_bytes:
        mime_type = detect_image_format(image_bytes)
    else:
        mime_type = "image/png"

    data_url = f"data:{mime_type};base64,{image_base64}"
    messages = [
        {
            "role": "system",
            "content": [{"text": system_prompt}]
        },
        {
            "role": "user",
            "content": [
                {"image": data_url},
                {"text": user_prompt}
            ]
        }
    ]

    try:
        # 调用dashscope的多模态API
        response = dashscope.MultiModalConversation.call(
            model=VISION_MODEL,
            messages=messages
        )

        # 检查响应状态
        if hasattr(response, "status_code") and response.status_code != 200:
            print(f"[提取节点] API调用失败，状态码: {response.status_code}")
            if hasattr(response, "message"):
                print(f"[提取节点] 错误信息: {response.message}")
            return {"extracted_items": []}

        # 提取响应文本
        text = extract_text_from_response(response)

        # Debug输出
        if os.getenv("LLM_DEBUG", "").lower() in ("1", "true", "yes"):
            print(f"[提取节点] 原始响应类型: {type(response)}")
            if hasattr(response, "__dict__"):
                print(f"[提取节点] 响应属性: {list(response.__dict__.keys())}")
            print(f"[提取节点] 提取的文本前500字符: {text[:500]}")

        # 清理文本（移除可能的代码块标记）
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text, flags=re.MULTILINE)
            text = re.sub(r"```$", "", text, flags=re.MULTILINE)
        text = text.strip()

        # 尝试解析JSON
        items = []
        try:
            data = json.loads(text)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and "items" in data:
                items = data["items"]
        except json.JSONDecodeError:
            # 尝试从文本中提取JSON数组
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                try:
                    items = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        # 验证和规范化数据
        extracted_items = []
        for item in items:
            if isinstance(item, dict):
                term = item.get("term") or item.get("word") or ""
                if term and isinstance(term, str) and term.strip():
                    extracted_items.append({
                        "term": term.strip(),
                        "definition": item.get("definition") or None,
                        "example": item.get("example") or None
                    })

        print(f"[提取节点] 识别到 {len(extracted_items)} 个单词")
        return {"extracted_items": extracted_items}

    except Exception as e:
        print(f"[提取节点] 错误: {e}")
        return {"extracted_items": []}


def node_complete_info(state: ImageState) -> ImageState:
    """
    LangGraph节点2：补充缺失的释义和例句

    对于第一步提取出的单词，如果缺少释义或例句，
    使用文本模型生成补充。

    优化：批量处理缺失信息，减少API调用次数
    """
    _ensure_api_key()
    extracted_items = state.get("extracted_items", [])

    if not extracted_items:
        return {"completed_items": []}

    # 分离需要补充和不需要补充的单词
    complete_items = []
    incomplete_items = []

    for item in extracted_items:
        term = item.get("term", "").strip()
        if not term:
            continue

        definition = item.get("definition")
        example = item.get("example")

        # 检查是否需要补充信息
        need_definition = not definition or not isinstance(definition, str) or not definition.strip()
        need_example = not example or not isinstance(example, str) or not example.strip()

        if need_definition or need_example:
            incomplete_items.append({
                "term": term,
                "definition": definition,
                "example": example,
                "need_definition": need_definition,
                "need_example": need_example
            })
        else:
            complete_items.append({
                "term": term,
                "definition": definition.strip() if isinstance(definition, str) else None,
                "example": example.strip() if isinstance(example, str) else None
            })

    # 如果没有需要补充的，直接返回
    if not incomplete_items:
        print(f"[补充节点] 所有 {len(complete_items)} 个单词信息完整，无需补充")
        return {"completed_items": complete_items}

    # 批量补充：构建批量请求
    try:
        # 构建批量prompt，一次性处理多个单词
        words_to_complete = []
        for item in incomplete_items:
            word_info = {"term": item["term"]}
            if item["need_definition"]:
                word_info["need"] = "definition" if item["need_example"] else "definition_only"
            elif item["need_example"]:
                word_info["need"] = "example_only"
            else:
                word_info["need"] = "both"
            words_to_complete.append(word_info)

        batch_prompt = (
            "给定以下英文单词列表，请为每个单词补充缺失的信息：\n\n"
            + "\n".join([f"{i+1}. {w['term']} (需要: {w['need']})" for i, w in enumerate(words_to_complete)])
            + "\n\n请输出一个JSON数组，每个元素包含：\n"
            "- term: 单词\n"
            "- definition: 中文释义（简洁，不超过20字）\n"
            "- example: 英文例句（自然流畅）\n\n"
            "仅输出JSON数组，不要添加其他文本或代码块。\n"
            "示例格式:\n"
            '[\n'
            '  {"term": "ability", "definition": "能力；才能", "example": "She has great ability."},\n'
            '  {"term": "serene", "definition": "宁静的；安详的", "example": "The lake was serene."}\n'
            ']'
        )

        response = dashscope.Generation.call(
            model=TEXT_MODEL,
            prompt=batch_prompt
        )

        text = extract_text_from_response(response)
        text = text.strip()

        # 清理代码块标记
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text, flags=re.MULTILINE)
            text = re.sub(r"```$", "", text, flags=re.MULTILINE)
        text = text.strip()

        # 解析JSON数组
        enriched_data = []
        try:
            data = json.loads(text)
            if isinstance(data, list):
                enriched_data = data
        except json.JSONDecodeError:
            # 尝试提取JSON数组
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                try:
                    enriched_data = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        # 将批量结果与原始数据合并
        enriched_dict = {item.get("term", "").lower(): item for item in enriched_data if isinstance(item, dict)}

        for item in incomplete_items:
            term = item["term"]
            term_lower = term.lower()

            definition = item["definition"]
            example = item["example"]

            # 从批量结果中获取补充信息
            if term_lower in enriched_dict:
                enriched = enriched_dict[term_lower]
                if item["need_definition"] and "definition" in enriched:
                    gen_def = enriched["definition"]
                    if isinstance(gen_def, str) and gen_def.strip():
                        definition = gen_def.strip()
                if item["need_example"] and "example" in enriched:
                    gen_ex = enriched["example"]
                    if isinstance(gen_ex, str) and gen_ex.strip():
                        example = gen_ex.strip()

            complete_items.append({
                "term": term,
                "definition": definition.strip() if isinstance(definition, str) and definition else None,
                "example": example.strip() if isinstance(example, str) and example else None
            })

        print(f"[补充节点] 批量完成 {len(incomplete_items)} 个单词的信息补充")

    except Exception as e:
        print(f"[补充节点] 批量处理失败，回退到逐个处理: {e}")
        # 回退：逐个处理
        for item in incomplete_items:
            term = item["term"]
            definition = item["definition"]
            example = item["example"]

            try:
                prompt_parts = []
                if item["need_definition"]:
                    prompt_parts.append("1) 一个简洁的中文释义（不超过20字）")
                if item["need_example"]:
                    prompt_parts.append("2) 一句自然的英文例句")

                prompt = (
                    f"给定英文单词: {term}\n"
                    f"请补充以下缺失信息:\n" + "\n".join(prompt_parts) + "\n"
                    "仅输出一个JSON对象，不要添加多余文本或代码块。键名固定：\n"
                    "definition: 中文释义；example: 英文例句。\n"
                    "示例: {\"definition\": \"能力；才能\", \"example\": \"She has great ability.\"}"
                )

                response = dashscope.Generation.call(
                    model=TEXT_MODEL,
                    prompt=prompt
                )

                text = extract_text_from_response(response)
                text = text.strip()

                # 清理代码块标记
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\n?", "", text, flags=re.MULTILINE)
                    text = re.sub(r"```$", "", text, flags=re.MULTILINE)
                text = text.strip()

                # 解析JSON
                try:
                    gen_data = json.loads(text)
                    if isinstance(gen_data, dict):
                        if item["need_definition"] and "definition" in gen_data:
                            gen_def = gen_data["definition"]
                            if isinstance(gen_def, str) and gen_def.strip():
                                definition = gen_def.strip()
                        if item["need_example"] and "example" in gen_data:
                            gen_ex = gen_data["example"]
                            if isinstance(gen_ex, str) and gen_ex.strip():
                                example = gen_ex.strip()
                except json.JSONDecodeError:
                    # 如果解析失败，尝试从文本中提取
                    if item["need_definition"]:
                        def_match = re.search(r'"definition"\s*:\s*"([^"]+)"', text)
                        if def_match:
                            definition = def_match.group(1)
                    if item["need_example"]:
                        ex_match = re.search(r'"example"\s*:\s*"([^"]+)"', text)
                        if ex_match:
                            example = ex_match.group(1)
            except Exception as e2:
                print(f"[补充节点] 为单词 '{term}' 生成信息时出错: {e2}")

            complete_items.append({
                "term": term,
                "definition": definition.strip() if isinstance(definition, str) and definition else None,
                "example": example.strip() if isinstance(example, str) and example else None
            })

    print(f"[补充节点] 完成 {len(complete_items)} 个单词的信息补充")
    return {"completed_items": complete_items}


def build_agent_graph() -> StateGraph:
    """
    构建LangGraph工作流

    工作流包含两个节点：
    1. extract_words: 从图片中提取单词
    2. complete_info: 补充缺失信息
    """
    graph = StateGraph(ImageState)

    # 添加节点
    graph.add_node("extract_words", node_extract_words)
    graph.add_node("complete_info", node_complete_info)

    # 添加边：定义执行顺序
    graph.add_edge(START, "extract_words")
    graph.add_edge("extract_words", "complete_info")
    graph.add_edge("complete_info", END)

    return graph.compile()


def extract_vocabulary_from_image(image_path: str | Path | bytes) -> List[Dict[str, Any]]:
    """
    处理图片，返回单词列表

    Args:
        image_path: 图片文件路径（字符串或Path对象）或图片字节数据

    Returns:
        单词列表，每个元素包含 term, definition, example

    Raises:
        FileNotFoundError: 当图片文件不存在时
        ValueError: 当API密钥未设置时
    """
    # 读取图片
    if isinstance(image_path, bytes):
        image_bytes = image_path
    else:
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        image_bytes = image_path.read_bytes()

    image_base64 = encode_image_to_base64(image_bytes)

    # 初始化状态
    initial_state: ImageState = {
        "image_bytes": image_bytes,
        "image_base64": image_base64,
        "extracted_items": [],
        "completed_items": []
    }

    # 运行agent
    graph = build_agent_graph()
    result = graph.invoke(initial_state)

    # 返回结果
    return result.get("completed_items", [])
