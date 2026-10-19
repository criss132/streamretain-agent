"""Entorno simulado (datos sintéticos) y mock de la API de marketing."""

from .simulator import MarketingAPI, MarketingAPIError, MarketingTimeout, StreamingEnv

__all__ = ["StreamingEnv", "MarketingAPI", "MarketingAPIError", "MarketingTimeout"]
