#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from classify_images import is_safe

def test_is_safe():
    assert is_safe({'adult': 'VERY_UNLIKELY',
                    'medical': 'UNLIKELY',
                    'spoofed': 'POSSIBLE',
                    'violence': 'VERY_UNLIKELY',
                    'racy': 'VERY_UNLIKELY'}) == True
    assert is_safe({'adult': 'VERY_UNLIKELY',
                    'medical': 'UNLIKELY',
                    'spoofed': 'POSSIBLE',
                    'violence': 'LIKELY',
                    'racy': 'VERY_LIKELY'}) == False
