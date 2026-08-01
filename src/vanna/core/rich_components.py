"""Compatibility shim: legacy ``vanna.core.rich_components`` imports."""

from vanna.core.rich_component import ComponentType

from vanna.core import (
    ArtifactComponent,
    BadgeComponent,
    CardComponent,
    DataFrameComponent,
    IconTextComponent,
    LogViewerComponent,
    NotificationComponent,
    ProgressBarComponent,
    ProgressDisplayComponent,
    RichTextComponent,
    StatusCardComponent,
    TaskListComponent,
)

__all__ = [
    "ArtifactComponent",
    "BadgeComponent",
    "CardComponent",
    "ComponentType",
    "DataFrameComponent",
    "IconTextComponent",
    "LogViewerComponent",
    "NotificationComponent",
    "ProgressBarComponent",
    "ProgressDisplayComponent",
    "RichTextComponent",
    "StatusCardComponent",
    "TaskListComponent",
]
