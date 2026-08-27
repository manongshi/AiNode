import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

from app.config import settings
from app.services.chunking import split_text


NOTE_PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompt.txt"
MIND_MAP_PROMPT_FILE = Path(__file__).resolve().parents[1] / "siweiprompt.txt"


class AIServiceError(RuntimeError):
    pass


class AIService:
    def __init__(self) -> None:
        self.providers = {
            "deepseek": {
                "name": "DeepSeek",
                "api_key": settings.ai_api_key,
                "base_url": settings.ai_base_url,
                "model": settings.ai_model,
            },
            "qwen": {
                "name": "Qwen",
                "api_key": settings.qwen_api_key,
                "base_url": settings.qwen_base_url,
                "model": settings.qwen_model,
            },
        }

    async def generate_note(
        self,
        text: str,
        style: str,
        extra_instruction: str | None = None,
        provider: str = "deepseek",
    ) -> tuple[str, dict, str, int]:
        chunks = split_text(text)
        if not chunks:
            raise AIServiceError("字幕内容为空，无法生成笔记")

        if len(chunks) == 1:
            note, mind_map, content_type = await self._create_final_note(chunks[0], style, extra_instruction, provider)
            return note, mind_map, content_type, 1

        summaries = await self.analyze_chunks(chunks, provider=provider)
        digest = await self.merge_summaries(summaries, provider)
        note, mind_map, content_type = await self._create_final_note(digest, style, extra_instruction, provider)
        return note, mind_map, content_type, len(chunks)

    async def analyze_chunks(
        self,
        chunks: list[str],
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
        provider: str = "deepseek",
    ) -> list[str]:
        """对长文本分块进行局部分析，并在每个分块完成时报告真实进度。"""
        if not chunks:
            raise AIServiceError("没有可供 AI 分析的文本分块")

        semaphore = asyncio.Semaphore(3)

        async def summarize(index: int, chunk: str) -> tuple[int, str]:
            async with semaphore:
                summary = await self.complete(
                    system=(
                        "你是一个严谨的中文知识整理助手。只能依据用户提供的字幕内容总结，"
                        "不能补充字幕中没有出现的事实。输出简洁、准确、可合并。"
                    ),
                    user=(
                        f"这是视频字幕的第 {index + 1} 段，共 {len(chunks)} 段。\n"
                        "请提取本段的主题、关键观点、重要概念、数据和可执行事项。"
                        "如果本段只是过渡或重复内容，请明确标记。\n\n"
                        f"字幕内容：\n{chunk}"
                    ),
                    max_tokens=1200,
                    provider=provider,
                )
                return index, summary

        summaries = [""] * len(chunks)
        completed = 0
        tasks = [asyncio.create_task(summarize(index, chunk)) for index, chunk in enumerate(chunks)]
        for task in asyncio.as_completed(tasks):
            index, summary = await task
            summaries[index] = summary
            completed += 1
            if progress_callback:
                await progress_callback(completed, len(chunks))
        return summaries

    async def merge_summaries(self, summaries: list[str], provider: str = "deepseek") -> str:
        return await self._merge_summaries(summaries, provider)

    async def create_final_note(
        self,
        content: str,
        style: str,
        extra_instruction: str | None = None,
        provider: str = "deepseek",
    ) -> tuple[str, dict, str]:
        return await self._create_final_note(content, style, extra_instruction, provider)

    async def _create_final_note(self, content: str, style: str, extra_instruction: str | None, provider: str) -> tuple[str, dict, str]:
        style_instruction = {
            "structured": "输出结构化笔记，包含标题、内容概览、分章节重点、关键概念、行动建议和待确认问题。",
            "brief": "输出一份较短的摘要笔记，只保留最重要的结论和行动建议。",
            "study": "输出适合学习复习的笔记，包含知识点、概念解释、例子、易错点和复习问题。",
        }.get(style, "输出结构化笔记。")
        note_prompt = NOTE_PROMPT_FILE.read_text(encoding="utf-8").replace("{{text}}", content)
        mind_map_prompt = MIND_MAP_PROMPT_FILE.read_text(encoding="utf-8").replace("{{content}}", content)
        extra = f"\n\n额外要求：{extra_instruction}" if extra_instruction else ""
        response = await self.complete(
            system=(
                "你是一个中文笔记编辑与思维导图结构化助手。一次完成两项任务，"
                "只返回合法 JSON，不要提及分块、模型或处理过程。"
            ),
            user=(
                f"{style_instruction}{extra}\n\n"
                "必须使用下面两个提示词的全部规则，在一次输出中生成笔记和思维导图。\n"
                "先根据内容自行判断最合适的整理类型。电影、电视剧或故事解说使用剧情梳理，保留背景、人物、事件推进、冲突、转折、结局和主题；"
                "教程使用步骤与关键决策；知识讲解使用概念、原理、例子和应用；访谈或观点内容使用观点、依据和结论。"
                "只能依据提供内容，不得补写未提及的剧情或事实。\n"
                "输出格式只能是：{\"contentType\": \"整理类型\", \"note\": \"Markdown 笔记内容\", \"mindMap\": {Markmap JSON}}。\n"
                "contentType 是 2 到 8 个字的中文类型名称；note 字段必须是笔记提示词要求的完整 Markdown；mindMap 字段必须是思维导图提示词要求的 Markmap JSON 对象。\n\n"
                f"【笔记提示词】\n{note_prompt}\n\n【思维导图提示词】\n{mind_map_prompt}"
            ),
            max_tokens=6000,
            json_mode=True,
            provider=provider,
        )
        try:
            data = json.loads(response)
        except json.JSONDecodeError as exc:
            raise AIServiceError("AI 返回的笔记与思维导图不是有效 JSON") from exc
        note = data.get("note")
        mind_map = data.get("mindMap")
        content_type = data.get("contentType")
        if not isinstance(note, str) or not note.strip() or not isinstance(mind_map, dict) or not isinstance(mind_map.get("content"), str):
            raise AIServiceError("AI 返回的笔记或思维导图数据不完整")
        return note.strip(), mind_map, content_type.strip() if isinstance(content_type, str) and content_type.strip() else "通用笔记"

    async def _merge_summaries(self, summaries: list[str], provider: str) -> str:
        combined = "\n\n".join(f"第 {index + 1} 段摘要：\n{summary}" for index, summary in enumerate(summaries))
        if len(combined) <= 14000:
            return await self.complete(
                system="你是一个中文内容编辑，负责合并多个局部摘要，保留事实并消除重复。",
                user=(
                    "请把下面的分段摘要合并成一份有顺序的全局提纲。"
                    "保留章节关系、关键事实、概念之间的联系和不确定信息。\n\n"
                    f"{combined}"
                ),
                max_tokens=2600,
                provider=provider,
            )

        groups = [combined[index : index + 12000] for index in range(0, len(combined), 12000)]
        reduced = await asyncio.gather(
            *(
                self.complete(
                    system="你是一个中文内容编辑，负责压缩分段摘要，保留关键事实。",
                    user=f"请压缩下面的摘要，保留主题、结论、概念和数据：\n\n{group}",
                    max_tokens=1800,
                    provider=provider,
                )
                for group in groups
            )
        )
        return await self._merge_summaries(list(reduced), provider)

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int,
        json_mode: bool = False,
        provider: str = "deepseek",
    ) -> str:
        provider_config = self.providers.get(provider)
        if not provider_config:
            raise AIServiceError("不支持的 AI 模型提供商")
        if not provider_config["api_key"]:
            raise AIServiceError(f'{provider_config["name"]} API 密钥未配置')
        payload = {
            "model": provider_config["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        if provider == "qwen":
            payload["enable_thinking"] = True
        else:
            payload["thinking"] = {"type": "disabled"}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = f'Bearer {provider_config["api_key"]}'
        try:
            async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
                for attempt in range(2):
                    response = await client.post(f'{provider_config["base_url"]}/chat/completions', headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
                    if attempt == 0:
                        await asyncio.sleep(0.5)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise AIServiceError(f"AI 接口返回错误：{detail}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise AIServiceError(f'{provider_config["name"]} 接口无法访问，请检查模型配置和网络') from exc

        raise AIServiceError("AI 接口连续两次没有返回有效内容，请稍后重试")
