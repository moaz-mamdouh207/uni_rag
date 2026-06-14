"""
LLMClient — thin async wrapper around LangChain's ChatGoogleGenerativeAI.

Changes from original:
  - Added get_llm() method so AgentLoop can call bind_tools() on the raw
    LangChain instance without touching the existing complete() path.
  - Everything else is identical to the original.
"""
from __future__ import annotations
import io
import base64
import logging

from PIL import Image as PILImage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from shared.llm.schemas import LLMResult, UsageInfo
from shared.llm.exceptions import LLMClientError, LLMRateLimitError, LLMAuthenticationError
from shared.llm.config import LLMSettings

logger = logging.getLogger(__name__)

_ROLE_TO_LC = {
    "system":    HumanMessage,  # Gemini has no system message type
    "user":      HumanMessage,
    "assistant": AIMessage,
}


class LLMClient:
    def __init__(self, settings: LLMSettings):
        self._llm = ChatGoogleGenerativeAI(
            model=settings.llm,
            google_api_key=settings.api_key,
            temperature=settings.temperature,
            max_tokens=settings.max_output_tokens,
        )
        self._vlm = ChatGoogleGenerativeAI(
            model=settings.vlm,
            google_api_key=settings.api_key,
            temperature=settings.temperature,
            max_tokens=settings.max_output_tokens,
        )

    # ------------------------------------------------------------------
    # Existing methods — unchanged
    # ------------------------------------------------------------------

    async def complete(self, messages: list[dict[str, str]]) -> LLMResult:
        lc_messages = [
            _ROLE_TO_LC[m["role"]](content=m["content"])
            for m in messages
            if m.get("role") in _ROLE_TO_LC
        ]

        try:
            response = await self._llm.ainvoke(lc_messages)

            if isinstance(response.content, list):
                text = "".join(
                    block.get("text", "")
                    for block in response.content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                text = response.content

        except Exception as exc:
            error = str(exc).lower()
            if "quota" in error or "rate" in error:
                raise LLMRateLimitError(str(exc)) from exc
            if "api key" in error or "permission" in error:
                raise LLMAuthenticationError(str(exc)) from exc
            raise LLMClientError(str(exc)) from exc

        usage            = response.usage_metadata or {}
        prompt_tokens    = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        return LLMResult(
            content=text,  # type: ignore[arg-type]
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    def call_vlm_with_prompt_and_image(
        self,
        prompt_text: str,
        img: PILImage.Image,
    ) -> str:
        buffered   = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str    = base64.b64encode(buffered.getvalue()).decode("utf-8")
        image_data = f"data:image/png;base64,{img_str}"

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": image_data}},
            ]
        )

        response = self._vlm.invoke([message])

        if isinstance(response.content, list):
            text = "".join(
                block.get("text", "")
                for block in response.content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            text = str(response.content)
            
        return text


    def call_vlm_with_prompt_and_images(
        self,
        prompt_text: str,
        img:  list[PILImage.Image],
    ) -> str:
        # 1. Standardize input to always be a list of images
        images = img if isinstance(img, list) else [img]
        
        # 2. Build the message content with the text prompt first
        message_content = [{"type": "text", "text": prompt_text}]
        
        # 3. Loop through all images, convert to base64, and append block elements
        for image in images:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            image_data = f"data:image/png;base64,{img_str}"
            
            message_content.append({
                "type": "image_url", 
                "image_url": {"url": image_data}
            }) # type: ignore

        # 4. Invoke the model with the combined content payload
        message = HumanMessage(content=message_content) # type: ignore
        response = self._vlm.invoke([message])

        # 5. Safely parse and extract response text
        if isinstance(response.content, list):
            text = "".join(
                block.get("text", "")
                for block in response.content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            text = str(response.content)
            
        return text
    # ------------------------------------------------------------------
    # New — exposes raw LangChain instance for AgentLoop.bind_tools()
    # ------------------------------------------------------------------

    def get_llm(self) -> ChatGoogleGenerativeAI:
        """
        Return the raw ChatGoogleGenerativeAI LLM instance.
        Used by AgentLoop to call bind_tools() for native function calling.
        The existing complete() path is unaffected.
        """
        return self._llm
