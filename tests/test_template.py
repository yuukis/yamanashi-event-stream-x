#!/usr/bin/env python3
"""
Template functionality tests for the yamanashi-event-stream-x application.
Tests YAML template loading, date formatting, and post text generation.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Add consumer directory to path to import app
consumer_dir = Path(__file__).parent.parent / "consumer"
sys.path.insert(0, str(consumer_dir))

try:
    import app
    TEMPLATE_AVAILABLE = True
except ImportError:
    TEMPLATE_AVAILABLE = False
    print("Warning: Could not import app module - template tests will be skipped")


def test_template_config_loading():
    """Test that template configuration loads correctly."""
    print("=== Template Configuration Loading Test ===")
    
    if not TEMPLATE_AVAILABLE:
        print("❌ SKIPPED: Template not available")
        return False
    
    try:
        # Check that template config is loaded
        assert app.TEMPLATE_CONFIG is not None, "Template config should not be None"
        assert 'template' in app.TEMPLATE_CONFIG, "Template config should have 'template' key"
        assert 'limits' in app.TEMPLATE_CONFIG, "Template config should have 'limits' key"
        assert 'formatting' in app.TEMPLATE_CONFIG, "Template config should have 'formatting' key"
        
        # Check template structure
        template = app.TEMPLATE_CONFIG['template']
        assert 'header' in template, "Template should have header"
        assert 'place_format' in template, "Template should have place_format"
        assert 'group_format' in template, "Template should have group_format"
        
        print("✅ Template configuration loaded successfully")
        return True
        
    except Exception as e:
        print(f"❌ Template loading failed: {e}")
        return False


def test_date_formatting():
    """Test date formatting with year logic and trailing dash."""
    print("\n=== Date Formatting Test ===")
    
    if not TEMPLATE_AVAILABLE:
        print("❌ SKIPPED: Template not available")
        return False
    
    try:
        # Test current year (2026) - should not include year
        result_2026 = app.format_started_at('2026-03-30T19:00:00+09:00')
        expected_2026 = '3/30(月) 19:00-'
        assert result_2026 == expected_2026, f"Expected '{expected_2026}', got '{result_2026}'"
        print(f"✅ Current year format: {result_2026}")
        
        # Test different year (2027) - should include year
        result_2027 = app.format_started_at('2027-02-01T09:00:00+09:00')
        expected_2027 = '2027/2/1(土) 9:00-'
        assert result_2027 == expected_2027, f"Expected '{expected_2027}', got '{result_2027}'"
        print(f"✅ Different year format: {result_2027}")
        
        # Test past year (2025) - should include year
        result_2025 = app.format_started_at('2025-12-15T14:30:00+09:00')
        expected_2025 = '2025/12/15(日) 14:30-'
        assert result_2025 == expected_2025, f"Expected '{expected_2025}', got '{result_2025}'"
        print(f"✅ Past year format: {result_2025}")
        
        # Test UTC to JST conversion
        result_utc = app.format_started_at('2026-03-30T10:00:00Z')
        expected_utc = '3/30(月) 19:00-'  # 10:00 UTC = 19:00 JST
        assert result_utc == expected_utc, f"Expected '{expected_utc}', got '{result_utc}'"
        print(f"✅ UTC to JST conversion: {result_utc}")
        
        return True
        
    except Exception as e:
        print(f"❌ Date formatting test failed: {e}")
        return False


def test_post_text_generation():
    """Test post text generation with various combinations."""
    print("\n=== Post Text Generation Test ===")
    
    if not TEMPLATE_AVAILABLE:
        print("❌ SKIPPED: Template not available")
        return False
    
    try:
        # Test minimal event (required fields only)
        minimal_event = {
            'uid': 'minimal-test',
            'title': 'シンプルイベント',
            'started_at': '2026-04-01T14:30:00Z',
            'event_url': 'https://example.com/minimal'
        }
        
        minimal_result = app.build_post_text(minimal_event)
        expected_lines = [
            '🆕✨山梨の新着イベント情報',
            '',
            'シンプルイベント',
            '🗓️4/1(火) 23:30-',
            'https://example.com/minimal'
        ]
        expected_minimal = '\n'.join(expected_lines)
        
        assert minimal_result == expected_minimal, f"Minimal post mismatch:\nExpected:\n{expected_minimal}\nActual:\n{minimal_result}"
        print("✅ Minimal event post generation")
        
        # Test full event (all optional fields)
        full_event = {
            'uid': 'full-test',
            'title': 'Pythonもくもく会',
            'started_at': '2026-03-30T19:00:00+09:00',
            'event_url': 'https://example.com/events/123',
            'place': '山梨県立図書館',
            'group_name': '山梨Python会',
            'hash_tag': '#yamanashi #python'
        }
        
        full_result = app.build_post_text(full_event)
        
        # Check that all components are present
        assert '🆕✨山梨の新着イベント情報' in full_result
        assert 'Pythonもくもく会' in full_result
        assert '📍山梨県立図書館' in full_result
        assert '👥山梨Python会' in full_result
        assert '🗓️3/30(月) 19:00-' in full_result
        assert 'https://example.com/events/123 #yamanashi #python' in full_result
        
        print("✅ Full event post generation")
        
        # Test event with different year
        future_event = {
            'uid': 'future-test',
            'title': '新年イベント',
            'started_at': '2027-01-01T09:00:00+09:00',
            'event_url': 'https://example.com/2027'
        }
        
        future_result = app.build_post_text(future_event)
        assert '🗓️2027/1/1(金) 9:00-' in future_result
        print("✅ Future year event post generation")
        
        return True
        
    except Exception as e:
        print(f"❌ Post text generation test failed: {e}")
        return False


def test_text_truncation():
    """Test text truncation functionality with long content."""
    print("\n=== Text Truncation Test ===")
    
    if not TEMPLATE_AVAILABLE:
        print("❌ SKIPPED: Template not available")
        return False
    
    try:
        # Create an event with very long title
        long_event = {
            'uid': 'long-test',
            'title': 'これは非常に長いイベントタイトルでX（旧Twitter）の文字数制限280文字を超えることを想定したテストケースです。実際の投稿時には適切に切り詰められることを確認します。',
            'started_at': '2026-03-30T19:00:00+09:00',
            'event_url': 'https://example.com/very-long-url-for-testing-truncation',
            'place': '山梨県立図書館の非常に長い会議室名',
            'group_name': '山梨Python会の長いグループ名'
        }
        
        long_result = app.build_post_text(long_event)
        
        # Check that result is within character limit
        max_length = app.TEMPLATE_CONFIG['limits']['max_length']
        assert len(long_result) <= max_length, f"Post length {len(long_result)} exceeds limit {max_length}"
        
        # Check that essential elements are preserved
        assert '🆕✨山梨の新着イベント情報' in long_result
        assert '🗓️3/30(月) 19:00-' in long_result
        assert 'https://example.com/very-long-url-for-testing-truncation' in long_result
        
        print(f"✅ Text truncation (length: {len(long_result)}/{max_length})")
        
        return True
        
    except Exception as e:
        print(f"❌ Text truncation test failed: {e}")
        return False


def test_hash_tag_handling():
    """Test hash tag processing."""
    print("\n=== Hash Tag Handling Test ===")
    
    if not TEMPLATE_AVAILABLE:
        print("❌ SKIPPED: Template not available")
        return False
    
    try:
        # Test with hash tag
        with_hashtag = {
            'uid': 'hashtag-test',
            'title': 'テストイベント',
            'started_at': '2026-03-30T19:00:00+09:00',
            'event_url': 'https://example.com/hashtag',
            'hash_tag': '#テスト #山梨'
        }
        
        result_with = app.build_post_text(with_hashtag)
        assert 'https://example.com/hashtag #テスト #山梨' in result_with
        print("✅ With hash tag")
        
        # Test without hash tag
        without_hashtag = {
            'uid': 'no-hashtag-test',
            'title': 'テストイベント',
            'started_at': '2026-03-30T19:00:00+09:00',
            'event_url': 'https://example.com/no-hashtag'
        }
        
        result_without = app.build_post_text(without_hashtag)
        assert result_without.endswith('https://example.com/no-hashtag')
        print("✅ Without hash tag")
        
        return True
        
    except Exception as e:
        print(f"❌ Hash tag handling test failed: {e}")
        return False


def test_error_handling():
    """Test error handling for invalid inputs."""
    print("\n=== Error Handling Test ===")
    
    if not TEMPLATE_AVAILABLE:
        print("❌ SKIPPED: Template not available")
        return False
    
    try:
        # Test invalid date format
        invalid_date = app.format_started_at('invalid-date')
        assert invalid_date == 'invalid-date', "Should return original string for invalid date"
        print("✅ Invalid date handling")
        
        # Test with missing optional fields (should not crash)
        minimal_event = {
            'uid': 'error-test',
            'title': 'エラーテスト',
            'started_at': '2026-03-30T19:00:00+09:00',
            'event_url': 'https://example.com/error'
        }
        
        result = app.build_post_text(minimal_event)
        assert result is not None and len(result) > 0
        print("✅ Missing optional fields handling")
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False


def run_all_tests():
    """Run all template tests."""
    print("🧪 Running Template Functionality Tests")
    print("=" * 50)
    
    tests = [
        test_template_config_loading,
        test_date_formatting,
        test_post_text_generation,
        test_text_truncation,
        test_hash_tag_handling,
        test_error_handling
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
    
    print("\n" + "=" * 50)
    print(f"🧪 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All template tests passed!")
    else:
        print("⚠️  Some tests failed - check output above")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)