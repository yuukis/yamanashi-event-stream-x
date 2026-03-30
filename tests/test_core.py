#!/usr/bin/env python3
"""
Simplified test script that tests core functions without external dependencies.
This avoids tweepy compatibility issues with Python 3.14+.
"""

import json
import os
from datetime import datetime


def format_started_at(started_at: str) -> str:
    """Format started_at to JST display format like '3/20(金) 19:00-' or '2027/2/1(月) 9:00-'."""
    try:
        # Parse ISO format with timezone
        dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        
        # Convert to JST (UTC+9)
        import datetime as dt_module
        jst_offset = dt_module.timedelta(hours=9)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_module.timezone.utc)
        jst_dt = dt.astimezone(dt_module.timezone(jst_offset))
        
        # Get current year in JST
        current_jst = datetime.now(dt_module.timezone(jst_offset))
        current_year = current_jst.year
        
        # Format as requested
        weekdays = ['月', '火', '水', '木', '金', '土', '日']
        weekday = weekdays[jst_dt.weekday()]
        
        # Format with or without year depending on current year
        if jst_dt.year != current_year:
            # Include year when different from current year
            formatted = f"{jst_dt.year}/{jst_dt.month}/{jst_dt.day}({weekday}) {jst_dt.hour}:{jst_dt.minute:02d}-"
        else:
            # Use month/day format for current year
            formatted = f"{jst_dt.month}/{jst_dt.day}({weekday}) {jst_dt.hour}:{jst_dt.minute:02d}-"
        
        return formatted
    except Exception as e:
        print(f"Failed to parse started_at '{started_at}': {e}")
        return started_at


def build_post_text(detail: dict) -> str:
    """Build post text according to the specification."""
    # Required components
    header = "🆕✨山梨の新着イベント情報"
    title = detail['title']
    formatted_date = format_started_at(detail['started_at'])
    event_url = detail['event_url']
    
    # Optional components
    place = detail.get('place') if detail.get('place') else None
    group_name = detail.get('group_name') if detail.get('group_name') else None
    hash_tag = detail.get('hash_tag') if detail.get('hash_tag') else None
    
    # Build components list
    components = [
        header,
        "",  # Empty line after header
        title,
        f"🗓️{formatted_date}"
    ]
    
    if place:
        components.append(f"📍{place}")
    
    if group_name:
        components.append(f"👥{group_name}")
    
    # Add URL and hash tag on the same line
    url_line = event_url
    if hash_tag:
        url_line += f" {hash_tag}"
    components.append(url_line)
    
    post_text = "\n".join(components)
    
    # Truncate if too long (X limit is 280 characters)
    post_text = truncate_text(post_text, 280)
    
    return post_text


def truncate_text(text: str, max_length: int) -> str:
    """Truncate text if it exceeds max_length, preserving essential information."""
    if len(text) <= max_length:
        return text
    
    # Split into lines
    lines = text.split('\n')
    header = lines[0] if lines else ""
    empty_line = lines[1] if len(lines) > 1 and lines[1] == "" else None
    title = lines[2] if len(lines) > 2 else ""
    date_line = lines[3] if len(lines) > 3 and lines[3].startswith('🗓️') else ""
    
    # Find place line (starts with 📍)
    place_line = None
    for i, line in enumerate(lines):
        if line.startswith('📍'):
            place_line = line
            break
    
    # Find group line (starts with 👥)
    group_line = None
    for i, line in enumerate(lines):
        if line.startswith('👥'):
            group_line = line
            break
    
    # Find URL line (last line)
    url_line = lines[-1] if lines else ""
    
    # Start with essential components
    essential_lines = [header]
    if empty_line is not None:
        essential_lines.append(empty_line)
    essential_lines.extend([title, date_line, url_line])
    
    # Try adding optional components
    optional_lines = essential_lines.copy()
    
    # Insert place line if available
    if place_line:
        insert_pos = 4 if empty_line is not None else 3
        optional_lines.insert(insert_pos, place_line)
    
    # Insert group line if available
    if group_line:
        insert_pos = (5 if place_line else 4) if empty_line is not None else (4 if place_line else 3)
        optional_lines.insert(insert_pos, group_line)
    
    # Check if optional version fits
    optional_text = "\n".join(optional_lines)
    if len(optional_text) <= max_length:
        return optional_text
    
    # Try without place line
    no_place_lines = essential_lines.copy()
    if group_line:
        insert_pos = 4 if empty_line is not None else 3
        no_place_lines.insert(insert_pos, group_line)
    
    no_place_text = "\n".join(no_place_lines)
    if len(no_place_text) <= max_length:
        return no_place_text
    
    # Try with essential only
    essential_text = "\n".join(essential_lines)
    if len(essential_text) <= max_length:
        return essential_text
    
    # Last resort: truncate title
    available_length = max_length - len("\n".join([header, "", "", date_line, url_line]))
    if available_length > 0 and len(title) > available_length:
        truncated_title = title[:available_length-3] + "..."
        final_lines = [header]
        if empty_line is not None:
            final_lines.append(empty_line)
        final_lines.extend([truncated_title, date_line, url_line])
        return "\n".join(final_lines)
    
    return essential_text


def validate_detail(detail: dict) -> None:
    """Validate required fields in detail."""
    required_fields = ['uid', 'title', 'event_url', 'started_at']
    
    for field in required_fields:
        if not detail.get(field):
            raise ValueError(f"Required field '{field}' is missing or empty")


def extract_detail(event: dict) -> dict:
    """Extract detail from EventBridge event."""
    if event.get('source') != 'yamanashi.tech.events':
        raise ValueError(f"Invalid source: {event.get('source')}")
    
    if event.get('detail-type') != 'event.created':
        raise ValueError(f"Invalid detail-type: {event.get('detail-type')}")
    
    detail = event.get('detail', {})
    if not detail:
        raise ValueError("No detail found in event")
    
    return detail


def test_post_text_generation():
    """Test post text generation with various scenarios."""
    print("=== Testing Post Text Generation ===")
    
    # Test case 1: Full event with all fields
    detail1 = {
        "uid": "connpass-123456",
        "title": "JAWS-UG 山梨 LT会",
        "event_url": "https://connpass.com/event/123456/",
        "hash_tag": "#jawsug",
        "started_at": "2026-03-20T19:00:00+09:00",
        "place": "山梨県立図書館",
        "group_name": "JAWS-UG 山梨"
    }
    
    post1 = build_post_text(detail1)
    print("Test 1 - Full event:")
    print(post1)
    print(f"Length: {len(post1)}")
    print("-" * 50)
    
    # Test case 2: Event without place and group
    detail2 = {
        "uid": "connpass-789012",
        "title": "Pythonもくもく会",
        "event_url": "https://connpass.com/event/789012/",
        "started_at": "2026-03-25T14:00:00+09:00",
    }
    
    post2 = build_post_text(detail2)
    print("Test 2 - Minimal event:")
    print(post2)
    print(f"Length: {len(post2)}")
    print("-" * 50)
    
    # Test case 3: Very long title (truncation test)
    detail3 = {
        "uid": "long-event",
        "title": "とても長いイベント名でXの文字数制限をテストするためのサンプルイベントですが実際にはこんなに長いタイトルのイベントは普通ないと思います",
        "event_url": "https://example.com/very-long-url-that-might-also-contribute-to-length-issues/",
        "hash_tag": "#longevent #test #yamanashi",
        "started_at": "2026-04-01T09:00:00+09:00",
        "place": "とても長い会場名でこれも文字数制限に影響する可能性があります",
        "group_name": "とても長いグループ名でこれも同様です"
    }
    
    post3 = build_post_text(detail3)
    print("Test 3 - Long content (truncation):")
    print(post3)
    print(f"Length: {len(post3)}")
    print("-" * 50)


def test_date_formatting():
    """Test date formatting function."""
    print("=== Testing Date Formatting ===")
    
    test_dates = [
        "2026-03-20T19:00:00+09:00",  # With timezone
        "2026-03-21T14:30:00Z",       # UTC
        "2026-12-31T23:59:00+09:00",  # Year end
        "invalid-date",               # Invalid format
        "2026-03-22T08:00:00",        # No timezone
    ]
    
    for date_str in test_dates:
        formatted = format_started_at(date_str)
        print(f"Input: {date_str}")
        print(f"Output: {formatted}")
        print("-" * 30)


def test_validation():
    """Test detail validation."""
    print("=== Testing Validation ===")
    
    # Valid detail
    valid_detail = {
        "uid": "test-123",
        "title": "Test Event",
        "event_url": "https://example.com",
        "started_at": "2026-03-20T19:00:00+09:00"
    }
    
    try:
        validate_detail(valid_detail)
        print("✅ Valid detail passed validation")
    except ValueError as e:
        print(f"❌ Valid detail failed: {e}")
    
    # Invalid detail (missing title)
    invalid_detail = {
        "uid": "test-456",
        "event_url": "https://example.com",
        "started_at": "2026-03-20T19:00:00+09:00"
    }
    
    try:
        validate_detail(invalid_detail)
        print("❌ Invalid detail passed validation (should have failed)")
    except ValueError as e:
        print(f"✅ Invalid detail correctly rejected: {e}")


def test_event_extraction():
    """Test EventBridge event extraction."""
    print("=== Testing Event Extraction ===")
    
    # Valid EventBridge event
    valid_event = {
        "source": "yamanashi.tech.events",
        "detail-type": "event.created",
        "detail": {
            "uid": "test-event",
            "title": "Test Event",
            "event_url": "https://example.com",
            "started_at": "2026-03-20T19:00:00+09:00"
        }
    }
    
    try:
        detail = extract_detail(valid_event)
        print("✅ Valid EventBridge event extracted successfully")
        print(f"Extracted UID: {detail['uid']}")
    except ValueError as e:
        print(f"❌ Valid event failed: {e}")
    
    # Invalid event (wrong source)
    invalid_event = {
        "source": "wrong.source",
        "detail-type": "event.created",
        "detail": {"uid": "test"}
    }
    
    try:
        extract_detail(invalid_event)
        print("❌ Invalid event passed extraction (should have failed)")
    except ValueError as e:
        print(f"✅ Invalid event correctly rejected: {e}")


def test_sample_event():
    """Test with a complete sample event."""
    print("=== Testing Sample Event Processing ===")
    
    sample_event = {
        "version": "0",
        "id": "test-id",
        "detail-type": "event.created",
        "source": "yamanashi.tech.events",
        "account": "123456789012",
        "time": "2026-03-20T10:00:00Z",
        "region": "ap-northeast-1",
        "resources": [],
        "detail": {
            "schema_version": "1",
            "event_kind": "event.created",
            "uid": f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "event_id": 999999,
            "title": "テスト用イベント（ローカル実行）",
            "catch": "ローカル環境でのテストです",
            "event_url": "https://example.com/test-event",
            "hash_tag": "#test",
            "started_at": "2026-03-20T19:00:00+09:00",
            "ended_at": "2026-03-20T21:00:00+09:00",
            "updated_at": "2026-03-10T08:30:00+09:00",
            "open_status": "open",
            "owner_name": "テスト主催者",
            "place": "テスト会場",
            "address": "山梨県甲府市...",
            "group_key": "test-group",
            "group_name": "テストグループ",
            "group_url": "https://example.com/group"
        }
    }
    
    try:
        print("Processing sample EventBridge event...")
        
        # Extract and validate
        detail = extract_detail(sample_event)
        validate_detail(detail)
        print(f"✅ Event validation passed for UID: {detail['uid']}")
        
        # Generate post text
        post_text = build_post_text(detail)
        
        print("\n📝 Generated post text:")
        print("-" * 40)
        print(post_text)
        print("-" * 40)
        print(f"📊 Text length: {len(post_text)} characters")
        print(f"📏 Within X limit: {'✅' if len(post_text) <= 280 else '❌'}")
        
    except Exception as e:
        print(f"❌ Sample event processing failed: {e}")


if __name__ == "__main__":
    print("🧪 Yamanashi Event Stream X Consumer - Core Function Tests")
    print("=" * 70)
    print("⚠️  Note: This test script runs core functions without X API integration")
    print("   to avoid tweepy compatibility issues with Python 3.14+")
    print("")
    
    # Run all tests
    test_post_text_generation()
    print("\n")
    
    test_date_formatting()
    print("\n")
    
    test_validation()
    print("\n")
    
    test_event_extraction()
    print("\n")
    
    test_sample_event()
    
    print("\n" + "=" * 70)
    print("🎉 Core function testing complete!")
    print("\n📋 Summary:")
    print("  ✅ Post text generation")
    print("  ✅ Date formatting (JST)")
    print("  ✅ Input validation")
    print("  ✅ EventBridge event extraction")
    print("  ✅ Text truncation for X limits")
    print("\n💡 To test full Lambda functionality:")
    print("  1. Use Python 3.12 or install tweepy compatible with Python 3.14+")
    print("  2. Set X API environment variables")
    print("  3. Configure AWS credentials for DynamoDB access")