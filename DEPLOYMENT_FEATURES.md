# Deployment Script Features

## AWS Profile Support

The deployment script now supports using AWS profiles:

```bash
# Use default profile
./scripts/deploy-aws.sh --region us-east-1

# Use specific profile
./scripts/deploy-aws.sh --profile myprofile --region us-east-1
```

All AWS CLI commands will use the specified profile automatically.

## Environment Variables Support

### Automatic .env File Loading

The script automatically reads environment variables from a `.env` file and passes them to App Runner:

1. **Create `.env` file** in the project root:
   ```bash
   OPENAI_API_KEY=sk-your-key-here
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

2. **Deploy** - the script will automatically:
   - Load variables from `.env`
   - Convert them to App Runner format
   - Configure them in the service

### Custom .env File Location

You can specify a custom location:

```bash
./scripts/deploy-aws.sh --env-file .env.production
```

### How It Works

1. Script reads `.env` file line by line
2. Parses `KEY=VALUE` pairs
3. Converts to JSON format for App Runner
4. Includes in service configuration
5. Variables are available to your application at runtime

### Supported Variables

Any environment variables you add to `.env` will be passed through:
- `OPENAI_API_KEY` - For OpenAI backend
- `ANTHROPIC_API_KEY` - For Claude backend
- Any custom variables your app needs

## Command Line Options

```bash
./scripts/deploy-aws.sh [OPTIONS]

Options:
  --profile PROFILE     AWS profile to use (default: default)
  --region REGION       AWS region (default: us-east-1)
  --service-name NAME   App Runner service name (default: safesim-service)
  --env-file FILE       Path to .env file (default: .env)
  -h, --help           Show help message
```

## Examples

### Basic Deployment
```bash
./scripts/deploy-aws.sh --region us-east-1
```

### With Profile and Custom Service Name
```bash
./scripts/deploy-aws.sh --profile production --region us-west-2 --service-name safesim-prod
```

### With Environment Variables
```bash
# Create .env file first
echo "OPENAI_API_KEY=sk-xxx" > .env
echo "ANTHROPIC_API_KEY=sk-ant-xxx" >> .env

# Deploy
./scripts/deploy-aws.sh --profile myprofile --env-file .env
```

### Update Existing Deployment
```bash
# Just run again with same parameters
./scripts/deploy-aws.sh --profile myprofile --region us-east-1 --service-name safesim-service
```

## Security Notes

1. **Never commit `.env` files** - Add to `.gitignore`
2. **Use AWS Secrets Manager** for production
3. **Rotate API keys** regularly
4. **Use IAM roles** where possible instead of access keys

## Troubleshooting

### Profile Not Found
```bash
# List available profiles
aws configure list-profiles

# Configure new profile
aws configure --profile myprofile
```

### Environment Variables Not Loading
- Check `.env` file exists and is readable
- Verify format: `KEY=VALUE` (no spaces around `=`)
- Check file path if using `--env-file`

### Variables Not Available in App
- Check App Runner service configuration in AWS Console
- Verify variables are in correct format in `.env`
- Check CloudWatch logs for errors

