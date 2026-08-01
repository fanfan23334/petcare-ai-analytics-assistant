"""Compatibility shim: legacy ``vanna.core.simple_components`` imports."""

from vanna.core import (
    SimpleComponent,
    SimpleComponentType,
    SimpleImageComponent,
    SimpleLinkComponent,
    SimpleTextComponent,
)

__all__ = [
    "SimpleComponent",
    "SimpleComponentType",
    "SimpleImageComponent",
    "SimpleLinkComponent",
    "SimpleTextComponent",
]
