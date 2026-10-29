"""Shared transport boundary. WhatsApp has no registered executable adapter in v1.35."""
from dataclasses import dataclass
from typing import Protocol
from .gmail_adapter import Acceptance


class OutboundAdapter(Protocol):
    channel: str
    provider: str
    def send(self, snapshot: dict, message_id: str) -> Acceptance: ...
    def reconcile(self, snapshot: dict, message_id: str) -> Acceptance | None: ...


@dataclass(frozen=True)
class ChannelCapabilities:
    channel: str
    provider: str
    executable: bool
    requires_opt_in: bool
    supports_templates: bool
    service_window_seconds: int | None
    receipts: tuple[str, ...]


CAPABILITIES = {
    'gmail': ChannelCapabilities('email','gmail',True,True,False,None,('accepted','reply')),
    # Reservation only; no assumed template approval, window, price or unsigned webhook acceptance.
    'whatsapp_cloud': ChannelCapabilities('whatsapp','whatsapp_cloud',False,True,True,None,()),
}
