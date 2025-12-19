import os
from typing import Optional, List

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI
from typing import Any  # 为了使用原始 dict 并忽略类型检查

load_dotenv()

for key in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
):
    if os.environ.get(key, "").startswith("socks://"):
        os.environ[key] = os.environ[key].replace("socks://", "socks5://")


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> None:
        self.api_key: Optional[str] = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url: Optional[str] = base_url or os.getenv("OPENAI_BASE_URL")
        self.model: str = model or os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        self.temperature: float = (
            float(temperature)
            if temperature is not None
            else float(os.getenv("LLM_TEMPERATURE", "0.7"))
        )

        # OpenAI 客户端在未配置 API Key 时为空
        self.client: Optional[OpenAI]

        if not self.api_key:
            logger.warning(
                "OPENAI_API_KEY not found in environment variables. LLM features will not work."
            )
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def check_connection(self) -> None:
        """检查 LLM 提供者是否可达并能正常工作。"""
        if not self.client:
            raise ValueError(
                "LLM Client is not initialized. Please check OPENAI_API_KEY."
            )

        try:
            logger.info(f"Checking LLM connection to {self.base_url or 'OpenAI'}...")
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],  # type: ignore[arg-type]
                max_tokens=1,
            )
            logger.info("LLM connection successful.")
        except Exception as e:
            raise ConnectionError(f"无法连接到 LLM 提供者: {e}")

    def get_completion(
        self, prompt: str, system_prompt: str = "You are a helpful assistant."
    ) -> str:
        if not self.client:
            return "LLM 客户端未初始化。"

        try:
            logger.debug(
                f"LLM Request [Text]:\nSystem: {system_prompt}\nUser: {prompt}"
            )
            response = self.client.chat.completions.create(  # type: ignore[call-arg]
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                stream=False,
            )
            content = response.choices[0].message.content.strip()
            logger.debug(f"LLM Response [Text]:\n{content}")
            return content
        except Exception as e:
            logger.error(f"调用 LLM 时出错: {e}")
            return f"Error: {e}"

    def get_json_completion(
        self, prompt: str, system_prompt: str = "You are a helpful assistant."
    ) -> str:
        if not self.client:
            return "{}"

        try:
            logger.debug(
                f"LLM Request [JSON]:\nSystem: {system_prompt}\nUser: {prompt}"
            )

            response = self.client.chat.completions.create(  # type: ignore[call-arg]
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt + "\nRespond in JSON format.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=self.temperature,
                stream=False,
            )
            content = response.choices[0].message.content.strip()
            logger.debug(f"LLM Response [JSON]:\n{content}")
            return content
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return "{}"
