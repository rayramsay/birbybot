#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from utils import is_safe

def test_is_safe():
    """`is_safe` should return False if any categories are LIKELY or VERY_LIKELY;
    conversely, `is_safe` should return True if all categories are VERY_UNLIKELY,
    LIKELY, or POSSIBLE."""
    assert is_safe({'adult': 'VERY_UNLIKELY',
                    'medical': 'UNLIKELY',
                    'spoofed': 'POSSIBLE',
                    'violence': 'LIKELY',
                    'racy': 'VERY_LIKELY'}) == False
    assert is_safe({'adult': 'VERY_UNLIKELY',
                    'medical': 'UNLIKELY',
                    'spoofed': 'POSSIBLE',
                    'violence': 'UNLIKELY',
                    'racy': 'VERY_UNLIKELY'}) == True
