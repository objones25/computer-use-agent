"""CAPTCHA solving integration using CapMonster Cloud."""

import asyncio
import base64
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from capmonstercloudclient import CapMonsterClient, ClientOptions
from capmonstercloudclient.requests import (
    AmazonWafRequest,
    ImageToTextRequest,
    RecaptchaV2Request,
    RecaptchaV3ProxylessRequest,
    TurnstileRequest,
)


class CaptchaType(Enum):
    """Supported CAPTCHA types."""

    AMAZON_WAF = "amazon_waf"
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    TURNSTILE = "turnstile"
    IMAGE_TO_TEXT = "image_to_text"


@dataclass
class CaptchaResult:
    """Result from CAPTCHA solving."""

    success: bool
    solution: str | None = None
    error: str | None = None
    captcha_type: CaptchaType | None = None


class CaptchaSolver:
    """CAPTCHA solver using CapMonster Cloud API."""

    def __init__(self, api_key: str):
        """Initialize the CAPTCHA solver.

        Args:
            api_key: CapMonster Cloud API key
        """
        self.api_key = api_key
        self._client: CapMonsterClient | None = None

    @property
    def client(self) -> CapMonsterClient:
        """Get or create the CapMonster client."""
        if self._client is None:
            options = ClientOptions(api_key=self.api_key)
            self._client = CapMonsterClient(options=options)
        return self._client

    async def solve_amazon_waf(
        self,
        website_url: str,
        website_key: str | None = None,
        iv: str | None = None,
        context: str | None = None,
        challenge_script: str | None = None,
        captcha_script: str | None = None,
        proxy: dict[str, Any] | None = None,
    ) -> CaptchaResult:
        """Solve Amazon WAF CAPTCHA.

        Args:
            website_url: URL of the page with CAPTCHA
            website_key: AWS WAF website key (if known)
            iv: Initialization vector (if known)
            context: Context value (if known)
            challenge_script: Challenge script URL (if known)
            captcha_script: CAPTCHA script URL (if known)
            proxy: Optional proxy configuration

        Returns:
            CaptchaResult with solution or error
        """
        try:
            request = AmazonWafRequest(
                websiteUrl=website_url,
                websiteKey=website_key or "",
                iv=iv or "",
                context=context or "",
                challengeScript=challenge_script or "",
                captchaScript=captcha_script or "",
            )

            result = await self.client.solve_captcha(request)

            if result and hasattr(result, "solution"):
                return CaptchaResult(
                    success=True,
                    solution=str(result.solution),
                    captcha_type=CaptchaType.AMAZON_WAF,
                )
            else:
                return CaptchaResult(
                    success=False,
                    error="No solution returned from CapMonster",
                    captcha_type=CaptchaType.AMAZON_WAF,
                )

        except Exception as e:
            return CaptchaResult(
                success=False,
                error=f"Amazon WAF CAPTCHA solving failed: {str(e)}",
                captcha_type=CaptchaType.AMAZON_WAF,
            )

    async def solve_recaptcha_v2(
        self,
        website_url: str,
        website_key: str,
        proxy: dict[str, Any] | None = None,
        invisible: bool = False,
    ) -> CaptchaResult:
        """Solve reCAPTCHA v2.

        Args:
            website_url: URL of the page with CAPTCHA
            website_key: reCAPTCHA site key
            proxy: Optional proxy configuration
            invisible: Whether it's an invisible reCAPTCHA

        Returns:
            CaptchaResult with solution token or error
        """
        try:
            # RecaptchaV2Request works for both proxy and proxyless
            request = RecaptchaV2Request(
                websiteUrl=website_url,
                websiteKey=website_key,
            )
            if proxy:
                request.proxyType = proxy.get("type", "http")
                request.proxyAddress = proxy.get("address", "")
                request.proxyPort = proxy.get("port", 0)
                request.proxyLogin = proxy.get("username", "")
                request.proxyPassword = proxy.get("password", "")

            result = await self.client.solve_captcha(request)

            if result and hasattr(result, "gRecaptchaResponse"):
                return CaptchaResult(
                    success=True,
                    solution=result.gRecaptchaResponse,
                    captcha_type=CaptchaType.RECAPTCHA_V2,
                )
            else:
                return CaptchaResult(
                    success=False,
                    error="No solution returned from CapMonster",
                    captcha_type=CaptchaType.RECAPTCHA_V2,
                )

        except Exception as e:
            return CaptchaResult(
                success=False,
                error=f"reCAPTCHA v2 solving failed: {str(e)}",
                captcha_type=CaptchaType.RECAPTCHA_V2,
            )

    async def solve_recaptcha_v3(
        self,
        website_url: str,
        website_key: str,
        page_action: str = "verify",
        min_score: float = 0.3,
    ) -> CaptchaResult:
        """Solve reCAPTCHA v3.

        Args:
            website_url: URL of the page with CAPTCHA
            website_key: reCAPTCHA site key
            page_action: The action parameter for reCAPTCHA v3
            min_score: Minimum score required (0.1-0.9)

        Returns:
            CaptchaResult with solution token or error
        """
        try:
            request = RecaptchaV3ProxylessRequest(
                websiteUrl=website_url,
                websiteKey=website_key,
                pageAction=page_action,
                minScore=min_score,
            )

            result = await self.client.solve_captcha(request)

            if result and hasattr(result, "gRecaptchaResponse"):
                return CaptchaResult(
                    success=True,
                    solution=result.gRecaptchaResponse,
                    captcha_type=CaptchaType.RECAPTCHA_V3,
                )
            else:
                return CaptchaResult(
                    success=False,
                    error="No solution returned from CapMonster",
                    captcha_type=CaptchaType.RECAPTCHA_V3,
                )

        except Exception as e:
            return CaptchaResult(
                success=False,
                error=f"reCAPTCHA v3 solving failed: {str(e)}",
                captcha_type=CaptchaType.RECAPTCHA_V3,
            )

    async def solve_turnstile(
        self,
        website_url: str,
        website_key: str,
        proxy: dict[str, Any] | None = None,
    ) -> CaptchaResult:
        """Solve Cloudflare Turnstile CAPTCHA.

        Args:
            website_url: URL of the page with CAPTCHA
            website_key: Turnstile site key
            proxy: Optional proxy configuration

        Returns:
            CaptchaResult with solution token or error
        """
        try:
            # TurnstileRequest works for both proxy and proxyless
            request = TurnstileRequest(
                websiteUrl=website_url,
                websiteKey=website_key,
            )
            if proxy:
                request.proxyType = proxy.get("type", "http")
                request.proxyAddress = proxy.get("address", "")
                request.proxyPort = proxy.get("port", 0)
                request.proxyLogin = proxy.get("username", "")
                request.proxyPassword = proxy.get("password", "")

            result = await self.client.solve_captcha(request)

            if result and hasattr(result, "token"):
                return CaptchaResult(
                    success=True,
                    solution=result.token,
                    captcha_type=CaptchaType.TURNSTILE,
                )
            else:
                return CaptchaResult(
                    success=False,
                    error="No solution returned from CapMonster",
                    captcha_type=CaptchaType.TURNSTILE,
                )

        except Exception as e:
            return CaptchaResult(
                success=False,
                error=f"Turnstile solving failed: {str(e)}",
                captcha_type=CaptchaType.TURNSTILE,
            )

    async def solve_image_captcha(
        self,
        image_path: str | Path | None = None,
        image_base64: str | None = None,
    ) -> CaptchaResult:
        """Solve image-based CAPTCHA (text recognition).

        Args:
            image_path: Path to the CAPTCHA image file
            image_base64: Base64-encoded CAPTCHA image

        Returns:
            CaptchaResult with recognized text or error
        """
        try:
            if image_path and not image_base64:
                with open(image_path, "rb") as f:
                    image_base64 = base64.standard_b64encode(f.read()).decode("utf-8")

            if not image_base64:
                return CaptchaResult(
                    success=False,
                    error="No image provided",
                    captcha_type=CaptchaType.IMAGE_TO_TEXT,
                )

            request = ImageToTextRequest(body=image_base64)
            result = await self.client.solve_captcha(request)

            if result and hasattr(result, "text"):
                return CaptchaResult(
                    success=True,
                    solution=result.text,
                    captcha_type=CaptchaType.IMAGE_TO_TEXT,
                )
            else:
                return CaptchaResult(
                    success=False,
                    error="No solution returned from CapMonster",
                    captcha_type=CaptchaType.IMAGE_TO_TEXT,
                )

        except Exception as e:
            return CaptchaResult(
                success=False,
                error=f"Image CAPTCHA solving failed: {str(e)}",
                captcha_type=CaptchaType.IMAGE_TO_TEXT,
            )

    async def detect_and_solve(
        self,
        website_url: str,
        page_html: str | None = None,
        screenshot_base64: str | None = None,
    ) -> CaptchaResult:
        """Attempt to detect CAPTCHA type and solve it.

        This is a simplified detection that looks for common patterns.
        For production use, you may want more sophisticated detection.

        Args:
            website_url: URL of the current page
            page_html: HTML content of the page (for detection)
            screenshot_base64: Screenshot for image CAPTCHA solving

        Returns:
            CaptchaResult with solution or error
        """
        if page_html:
            html_lower = page_html.lower()

            # Check for Amazon WAF
            if "awswaf" in html_lower or "amazon" in website_url.lower():
                return await self.solve_amazon_waf(website_url)

            # Check for reCAPTCHA v3
            if "recaptcha/api.js?render=" in html_lower:
                # Extract site key (simplified)
                import re
                match = re.search(r'render=([a-zA-Z0-9_-]+)', page_html)
                if match:
                    return await self.solve_recaptcha_v3(
                        website_url,
                        match.group(1),
                    )

            # Check for reCAPTCHA v2
            if "g-recaptcha" in html_lower or "recaptcha" in html_lower:
                import re
                match = re.search(r'data-sitekey=["\']([^"\']+)["\']', page_html)
                if match:
                    return await self.solve_recaptcha_v2(
                        website_url,
                        match.group(1),
                    )

            # Check for Turnstile
            if "turnstile" in html_lower or "cf-turnstile" in html_lower:
                import re
                match = re.search(r'data-sitekey=["\']([^"\']+)["\']', page_html)
                if match:
                    return await self.solve_turnstile(
                        website_url,
                        match.group(1),
                    )

        # If we have a screenshot and couldn't detect type, try image CAPTCHA
        if screenshot_base64:
            return await self.solve_image_captcha(image_base64=screenshot_base64)

        return CaptchaResult(
            success=False,
            error="Could not detect CAPTCHA type",
        )
