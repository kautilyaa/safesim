# Quick Deploy Guide - SafeSim to AWS

## One-Command Deployment

Deploy SafeSim (Streamlit UI + FastAPI API) to AWS with a fixed URL:

```bash
# Basic deployment
./scripts/deploy-aws.sh --region us-east-1 --service-name safesim-service

# With AWS profile
./scripts/deploy-aws.sh --profile myprofile --region us-east-1

# With environment variables from .env file
./scripts/deploy-aws.sh --profile myprofile --env-file .env
```

That's it! The script handles everything:
- ✅ Builds Docker image
- ✅ Pushes to ECR
- ✅ Creates/updates App Runner service
- ✅ Sets up API Gateway with fixed URL
- ✅ Loads environment variables from .env file
- ✅ Outputs your deployment URLs

## Prerequisites

1. **AWS CLI configured:** `aws configure` or `aws configure --profile myprofile`
2. **Docker running**
3. **jq installed** (script will try to install if missing)
4. **(Optional) .env file** with API keys (see `.env.example`)

## Environment Variables

Create a `.env` file with your API keys:

```bash
cp .env.example .env
# Edit .env and add your keys
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
```

The script automatically loads these and passes them to App Runner.

## What You Get

After deployment, you'll have:

- **Streamlit UI**: `https://<api-id>.execute-api.<region>.amazonaws.com/prod`
- **API Docs**: `https://<api-id>.execute-api.<region>.amazonaws.com/prod/api/docs`
- **API Endpoint**: `https://<api-id>.execute-api.<region>.amazonaws.com/prod/api/simplify`

## Testing

```bash
# Test API health
curl https://<api-id>.execute-api.<region>.amazonaws.com/prod/api/health

# Test API simplify
curl -X POST https://<api-id>.execute-api.<region>.amazonaws.com/prod/api/simplify \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patient prescribed 50mg Atenolol PO q.d. for hypertension.",
    "llm_backend": "dummy",
    "strictness": "high"
  }'
```

## Updating

To update after code changes:

```bash
./scripts/deploy-aws.sh us-east-1 safesim-service
```

## Cost

~$5-10/month for light usage (App Runner + API Gateway)

## Full Documentation

See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for detailed instructions.

