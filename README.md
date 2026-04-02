# Yamanashi Tech Events Stream X Consumer

AWS Lambda application that consumes Yamanashi event data from Amazon EventBridge and automatically posts to X (Twitter).

## Architecture

- **EventBridge**: Receives `event.created` events from `yamanashi.tech.events` source
- **Lambda**: Processes events and posts to X
- **DynamoDB**: Tracks posted events to prevent duplicates
- **X API**: Posts formatted event announcements

### Function Structure

- `lambda_handler()`: Main entry point
- `extract_detail()`: Parse EventBridge event  
- `validate_detail()`: Validate required fields
- `is_posted()`: Check DynamoDB for duplicates
- `build_post_text()`: Generate formatted post
- `format_started_at()`: Format date/time for display
- `truncate_text()`: Handle text length limits
- `post_to_x()`: Send to X API
- `mark_posted()`: Save to DynamoDB

## Prerequisites

- AWS SAM CLI
- Python 3.12
- X API credentials (API v2)

## Setup

### 1. X API Credentials

Create a X Developer account and obtain:
- API Key
- API Secret  
- Access Token
- Access Token Secret

### 2. Store Credentials in AWS Systems Manager Parameter Store

Store your X API credentials securely:

```bash
aws ssm put-parameter \
  --name "/yamanashi-event-stream-x/x-api-key" \
  --value "your-api-key" \
  --type "SecureString"

aws ssm put-parameter \
  --name "/yamanashi-event-stream-x/x-api-secret" \
  --value "your-api-secret" \
  --type "SecureString"

aws ssm put-parameter \
  --name "/yamanashi-event-stream-x/x-access-token" \
  --value "your-access-token" \
  --type "SecureString"

aws ssm put-parameter \
  --name "/yamanashi-event-stream-x/x-access-token-secret" \
  --value "your-access-token-secret" \
  --type "SecureString"
```

## Deployment

### Manual Deployment with SAM

#### Build and Deploy

```bash
# Build the application
sam build

# Deploy with guided setup (first time)
sam deploy --guided

# Or deploy with existing configuration
sam deploy
```

#### Configuration Parameters

- `TableName`: DynamoDB table name (default: `posted_events`)
- `LogLevel`: Logging level (default: `INFO`)

### Automated Deployment with GitHub Actions

This project includes GitHub Actions workflows for automated testing and deployment.

#### Setup
1. Set up AWS IAM role with OIDC or access keys
2. Configure GitHub repository secrets:
   - `AWS_ROLE_ARN` (or `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
   - `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`
3. Push to `main` branch for automatic deployment

#### Workflows
- **Test**: Runs on PR/push - syntax check and SAM validation
- **Deploy**: Deploys to AWS on push to main

## Template Configuration

The app uses a YAML template file to define the X post format, making it easy to customize without code changes.

### Template File

The post template is configured in `consumer/post_template.yaml`:

```yaml
# X投稿のテンプレート設定
template:
  # 基本的な投稿フォーマット
  header: "🆕✨山梨の新着イベント情報"
  
  # オプション要素のテンプレート
  place_format: "📍{place}"
  group_format: "👥{group_name}"
  
  # ハッシュタグの接頭辞/接尾辞
  hash_tag:
    prefix: ""
    suffix: " {hash_tag}"
    
# 文字数制限
limits:
  max_length: 280
  truncate_suffix: "..."

# フォーマット設定
formatting:
  # 日付フォーマットの曜日表記
  weekdays: ["月", "火", "水", "木", "金", "土", "日"]
```

### Customization

You can customize the post format by editing the template file:

- **Header text**: Change `template.header`
- **Emoji icons**: Modify `place_format` and `group_format`  
- **Character limit**: Adjust `limits.max_length`
- **Truncation text**: Change `limits.truncate_suffix`
- **Weekday names**: Update `formatting.weekdays`

The template supports Python string formatting with `{variable_name}` placeholders.

## Post Format

The app generates posts using the configured template. With default settings, events are posted in this format:

```
🆕✨山梨の新着イベント情報

{イベント名}
📍{開催場所} (if available)
👥{グループ名} (if available)  
🗓️{開催日時}
{イベントURL} {ハッシュタグ} (if available)
```

**Example Output:**
```
🆕✨山梨の新着イベント情報

Pythonもくもく会 - 春のプログラミング祭り
📍山梨県立図書館
👥山梨Python会
🗓️3/30(月) 19:00-
https://example.com/events/123 #yamanashi #python
```

### Date Format Logic

The date formatting includes intelligent year handling:
- **Current year events**: `3/30(月) 19:00-` (no year shown)
- **Different year events**: `2027/2/1(月) 9:00-` (year included)
- **Time suffix**: All times end with "-" to indicate event start time

### Text Truncation

If the post exceeds X's character limit (280), content is removed in this order:
1. Remove place line (📍)
2. Remove group line (👥)  
3. Truncate title with "..."

Essential elements are always preserved:
- Header
- Event title
- Date/time
- Event URL

## Event Schema

The app expects EventBridge events with this structure:

```json
{
  "source": "yamanashi.tech.events",
  "detail-type": "event.created", 
  "detail": {
    "uid": "string",
    "title": "string", 
    "event_url": "string",
    "started_at": "string",
    "place": "string or null",
    "group_name": "string or null",
    "hash_tag": "string or null"
  }
}
```

### Required Fields
- `uid`: Unique event identifier
- `title`: Event name
- `event_url`: Event page URL
- `started_at`: ISO formatted date/time

## Local Testing

### Core Function Tests

Test core functions without external dependencies:

```bash
# Run core function tests
python tests/test_core.py

# Run template functionality tests
python tests/test_template.py
```

### Template Tests

The template tests cover:
- **Template configuration loading**: YAML file parsing and validation
- **Date formatting**: Year logic, JST conversion, trailing dash
- **Post text generation**: Required/optional fields, template application
- **Text truncation**: Character limits and content prioritization
- **Hash tag handling**: With and without hash tags
- **Error handling**: Invalid dates and missing fields

### Full Lambda Testing

Test the complete Lambda function locally:

```bash
# Install dependencies
pip install -r consumer/requirements.txt

# Set environment variables
export TABLE_NAME=posted_events
export LOG_LEVEL=DEBUG
export X_API_KEY=your-key
export X_API_SECRET=your-secret  
export X_ACCESS_TOKEN=your-token
export X_ACCESS_TOKEN_SECRET=your-token-secret

# Run with sample event
python consumer/app.py
```

### Test Structure

```
tests/
├── test_core.py      # Core functions without external dependencies
└── test_template.py  # Template functionality comprehensive tests
```

## Monitoring

The application logs to CloudWatch with these events:
- Execution start/end
- Received UID
- Already posted checks  
- Post success/failure
- Post text length
- DynamoDB operations

Log retention is set to 14 days.

## Duplicate Prevention

The app tracks posted events in DynamoDB using the event `uid` as the primary key. Events are only posted if:
1. The `uid` doesn't exist in DynamoDB
2. X posting succeeds
3. The record is saved to DynamoDB after successful posting

## Error Handling

- Invalid/missing required fields: Skip processing
- X API errors: Log error, don't save to DynamoDB
- DynamoDB errors: Log and raise exception
- Already posted: Skip silently

## Development

### Project Structure

```
yamanashi-event-stream-x/
├── consumer/
│   ├── app.py              # Lambda function code
│   └── requirements.txt    # Python dependencies
├── tests/
│   └── test_core.py        # Core function tests
├── .github/workflows/      # CI/CD workflows
├── template.yaml          # SAM template
└── README.md             # Documentation
```

### Local Testing

```bash
# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r consumer/requirements.txt

# Run core function tests
python tests/test_core.py
```

### SAM Commands

```bash
# Validate template
sam validate

# Build application
sam build

# Deploy
sam deploy --guided
```