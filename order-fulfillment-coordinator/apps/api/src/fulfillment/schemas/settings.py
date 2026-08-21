from __future__ import annotations

from pydantic import BaseModel


class AppSettings(BaseModel):
    theme: str = "dark"
    appName: str = "Warehouse OS"
    timezone: str = "UTC"
    language: str = "English"
    emailAlerts: bool = True
    smsAlerts: bool = False
    delayNotifications: bool = True
    anomalyAlerts: bool = True
    twoFactor: bool = False
    sessionTimeout: int = 60
    compactMode: bool = False
    apiEndpoint: str = ""
    webhookUrl: str = ""
    autoCleanupDays: int = 90
    autoBackup: bool = True
