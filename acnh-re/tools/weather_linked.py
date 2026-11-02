#!/usr/bin/env python3
"""Verify complete ordinary-day weather selection across the 05:00 boundary."""
from native_linker import ModuleSandbox
from weather_native import build

if __name__=='__main__':build(ModuleSandbox(),'weather/native_linked_verification.json',full_hours=True)
