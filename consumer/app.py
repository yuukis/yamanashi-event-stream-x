import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

import boto3
import yaml
from botocore.exceptions import ClientError

# Optional import for tweepy (for testing compatibility)
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError as e:
    logging.warning(f"tweepy not available: {e}")
    tweepy = None
    TWEEPY_AVAILABLE = False

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

# AWS clients - initialized lazily
_dynamodb = None
_table = None

def get_dynamodb_table():
    """Get DynamoDB table with lazy initialization."""
    global _dynamodb, _table
    if _table is None:
        _dynamodb = boto3.resource('dynamodb')
        table_name = os.getenv('TABLE_NAME', 'posted_events')
        _table = _dynamodb.Table(table_name)
    return _table

# Twitter API configuration
X_API_KEY = os.getenv('X_API_KEY')
X_API_SECRET = os.getenv('X_API_SECRET')
X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
X_ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')

# X post length limit  
X_MAX_LENGTH = 280

# Template configuration
TEMPLATE_CONFIG = None

def load_template_config() -> Dict[str, Any]:
    """Load template configuration from YAML file."""
    template_path = Path(__file__).parent / "post_template.yaml"
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info("Template configuration loaded successfully")
        return config
    except FileNotFoundError:
        logger.error(f"Template file not found: {template_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to load template configuration: {e}")
        raise

# Load template configuration at startup
TEMPLATE_CONFIG = load_template_config()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for EventBridge events."""
    logger.info("Lambda execution started")
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract detail from EventBridge event
        detail = extract_detail(event)
        logger.info(f"Received uid: {detail.get('uid')}")
        
        # Validate required fields
        validate_detail(detail)
        
        uid = detail['uid']
        
        # Check if already posted
        if is_posted(uid):
            logger.info(f"Event {uid} already posted, skipping")
            return {'statusCode': 200, 'body': 'already_posted'}
        
        # Build post text
        post_text = build_post_text(detail)
        logger.info(f"Post text length: {len(post_text)}")
        logger.debug(f"Post text: {post_text}")
        
        # Post to X
        post_to_x(post_text)
        logger.info("Posted to X successfully")
        
        # Mark as posted in DynamoDB
        mark_posted(detail)
        logger.info(f"Marked {uid} as posted")
        
        return {'statusCode': 200, 'body': 'posted'}
        
    except Exception as e:
        logger.error(f"Failed to process event: {str(e)}", exc_info=True)
        return {'statusCode': 500, 'body': 'failed'}


def extract_detail(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extract detail from EventBridge event."""
    if event.get('source') != 'yamanashi.tech.events':
        raise ValueError(f"Invalid source: {event.get('source')}")
    
    if event.get('detail-type') != 'event.created':
        raise ValueError(f"Invalid detail-type: {event.get('detail-type')}")
    
    detail = event.get('detail', {})
    if not detail:
        raise ValueError("No detail found in event")
    
    return detail


def validate_detail(detail: Dict[str, Any]) -> None:
    """Validate required fields in detail."""
    required_fields = ['uid', 'title', 'event_url', 'started_at']
    
    for field in required_fields:
        if not detail.get(field):
            raise ValueError(f"Required field '{field}' is missing or empty")


def is_posted(uid: str) -> bool:
    """Check if event is already posted by looking up DynamoDB."""
    try:
        table = get_dynamodb_table()
        response = table.get_item(Key={'uid': uid})
        return 'Item' in response
    except ClientError as e:
        logger.error(f"Failed to check if posted: {e}")
        return False


def build_post_text(detail: Dict[str, Any]) -> str:
    """Build post text according to the template configuration."""
    template_config = TEMPLATE_CONFIG['template']
    limits = TEMPLATE_CONFIG['limits']
    
    # Required components from template
    header = template_config['header']
    title = detail['title']
    formatted_date = format_started_at(detail['started_at'])
    event_url = detail['event_url']
    
    # Optional components
    place = detail.get('place') if detail.get('place') else None
    group_name = detail.get('group_name') if detail.get('group_name') else None
    hash_tag = detail.get('hash_tag') if detail.get('hash_tag') else None
    
    # Build hash tag suffix
    hash_tag_suffix = ""
    if hash_tag:
        hash_tag_config = template_config.get('hash_tag', {})
        hash_tag_suffix = hash_tag_config.get('suffix', " {hash_tag}").format(hash_tag=hash_tag)
    
    # Build components list
    components = [header, "", title, f"🗓️{formatted_date}"]
    
    # Add optional components using templates
    if place:
        place_line = template_config['place_format'].format(place=place)
        components.insert(-1, place_line)  # Insert before URL
    
    if group_name:
        group_line = template_config['group_format'].format(group_name=group_name)
        components.insert(-1, group_line)  # Insert before URL
    
    # Add URL line
    components.append(event_url + hash_tag_suffix)
    
    post_text = "\n".join(components)
    
    # Truncate if too long
    max_length = limits.get('max_length', X_MAX_LENGTH)
    post_text = truncate_text(post_text, max_length)
    
    return post_text


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
        
        # Get weekdays from template config
        formatting_config = TEMPLATE_CONFIG.get('formatting', {})
        weekdays = formatting_config.get('weekdays', ['月', '火', '水', '木', '金', '土', '日'])
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
        logger.warning(f"Failed to parse started_at '{started_at}': {e}")
        return started_at


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
    place_index = -1
    for i, line in enumerate(lines):
        if line.startswith('📍'):
            place_line = line
            place_index = i
            break
    
    # Find group line (starts with 👥)
    group_line = None
    group_index = -1
    for i, line in enumerate(lines):
        if line.startswith('👥'):
            group_line = line
            group_index = i
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
    limits = TEMPLATE_CONFIG.get('limits', {})
    truncate_suffix = limits.get('truncate_suffix', '...')
    available_length = max_length - len("\n".join([header, "", "", date_line, url_line]))
    if available_length > 0 and len(title) > available_length:
        truncated_title = title[:available_length-len(truncate_suffix)] + truncate_suffix
        final_lines = [header]
        if empty_line is not None:
            final_lines.append(empty_line)
        final_lines.extend([truncated_title, date_line, url_line])
        return "\n".join(final_lines)
    
    return essential_text


def post_to_x(text: str) -> None:
    """Post text to X (Twitter) using tweepy."""
    if not TWEEPY_AVAILABLE:
        raise RuntimeError("tweepy is not available - cannot post to X")
        
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]):
        raise ValueError("X API credentials not properly configured")
    
    try:
        # Create tweepy client
        client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True
        )
        
        # Post tweet
        response = client.create_tweet(text=text)
        logger.info(f"Tweet posted successfully: {response.data['id']}")
        
    except Exception as e:
        logger.error(f"Failed to post to X: {e}")
        raise


def mark_posted(detail: Dict[str, Any]) -> None:
    """Mark event as posted in DynamoDB."""
    try:
        item = {
            'uid': detail['uid'],
            'posted_at': datetime.utcnow().isoformat(),
            'title': detail['title'],
            'event_url': detail['event_url']
        }
        
        # Add group_key if not null
        if detail.get('group_key'):
            item['group_key'] = detail['group_key']
        
        table = get_dynamodb_table()
        table.put_item(Item=item)
        logger.debug(f"Saved to DynamoDB: {item}")
        
    except ClientError as e:
        logger.error(f"Failed to save to DynamoDB: {e}")
        raise


# Sample event for testing
sample_event = {
    "version": "0",
    "id": "xxxx",
    "detail-type": "event.created",
    "source": "yamanashi.tech.events",
    "account": "123456789012",
    "time": "2026-03-20T10:00:00Z",
    "region": "ap-northeast-1",
    "resources": [],
    "detail": {
        "schema_version": "1",
        "event_kind": "event.created",
        "uid": "connpass-123456",
        "event_id": 123456,
        "title": "JAWS-UG 山梨 LT会",
        "catch": "AWSをテーマにしたLT会です",
        "event_url": "https://connpass.com/event/123456/",
        "hash_tag": "#jawsug",
        "started_at": "2026-03-20T19:00:00+09:00",
        "ended_at": "2026-03-20T21:00:00+09:00",
        "updated_at": "2026-03-10T08:30:00+09:00",
        "open_status": "open",
        "owner_name": "JAWS-UG 山梨",
        "place": "山梨県立図書館",
        "address": "山梨県甲府市...",
        "group_key": "jawsug-yamanashi",
        "group_name": "JAWS-UG 山梨",
        "group_url": "https://..."
    }
}


if __name__ == "__main__":
    # For local testing
    result = lambda_handler(sample_event, None)
    print(f"Result: {result}")