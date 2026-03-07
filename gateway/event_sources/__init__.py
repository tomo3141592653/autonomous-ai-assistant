"""
Event Sources for Ayumu Gateway

Each source runs in its own daemon thread and calls a callback when an event occurs.
"""

from event_sources.timer_source import TimerSource
from event_sources.email_source import EmailSource
from event_sources.discord_source import DiscordSource
from event_sources.voice_source import VoiceSource
from event_sources.cron_source import CronSource
from event_sources.one_timer_source import OneTimerSource

__all__ = ["TimerSource", "EmailSource", "DiscordSource", "VoiceSource", "CronSource", "OneTimerSource"]
