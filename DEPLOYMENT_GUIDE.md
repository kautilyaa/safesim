# SafeSim AWS Deployment Guide

This guide will help you deploy SafeSim to AWS with both a Streamlit UI and FastAPI API, accessible via a fixed URL.

## Architecture

```
Internet → API Gateway → App Runner → Docker Container
                                    ├── Nginx (reverse proxy)
                                    ├── Streamlit UI (port 8501)
                                    └── FastAPI API (port 8000)
```

**Features:**
- ✅ Fixed URL via API Gateway
- ✅ Streamlit UI at root path (`/`)
- ✅ FastAPI API at `/api/*`
- ✅ Automatic HTTPS
- ✅ Built-in DDoS protection
- ✅ Auto-scaling

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured (`aws configure`)
3. **Docker** installed and running
4. **jq** installed (for JSON parsing)
5. **API Keys** (optional, for OpenAI/Anthropic if using those backends)

## Quick Deployment

### Step 1: Configure AWS CLI

```bash
# Configure default profile
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter default region (e.g., us-east-1)
# Enter default output format (json)

# OR configure a named profile
aws configure --profile myprofile
```

### Step 2: Set Up Environment Variables (Optional)

Create a `.env` file in the project root with your API keys:

```bash
# Copy example file
cp .env.example .env

# Edit .env and add your API keys
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Note:** The `.env` file is automatically loaded and passed to App Runner during deployment.

### Step 3: Run Deployment Script

```bash
# Make script executable (if not already)
chmod +x scripts/deploy-aws.sh

# Deploy with default profile
./scripts/deploy-aws.sh --region us-east-1 --service-name safesim-service

# Deploy with specific AWS profile
./scripts/deploy-aws.sh --profile myprofile --region us-east-1 --service-name safesim-service

# Deploy with custom .env file
./scripts/deploy-aws.sh --profile myprofile --env-file .env.production
```

**Available Options:**
- `--profile PROFILE`: AWS profile to use (default: default)
- `--region REGION`: AWS region (default: us-east-1)
- `--service-name NAME`: App Runner service name (default: safesim-service)
- `--env-file FILE`: Path to .env file (default: .env)
- `--help`: Show help message

The script will:
1. ✅ Create ECR repository
2. ✅ Build and push Docker image
3. ✅ Create/update App Runner service
4. ✅ Set up API Gateway with fixed URL
5. ✅ Output your deployment URLs

### Step 3: Access Your Application

After deployment completes, you'll see output like:

```
🎉 SafeSim is now deployed!
═══════════════════════════════════════════════════════════════

📍 Fixed URL (API Gateway):
   https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod

🌐 Streamlit UI:
   https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod

🔌 API Endpoints:
   - API Docs:      https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/api/docs
   - Health Check:  https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/api/health
   - Simplify:      https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/api/simplify
```

## Manual Deployment Steps

If you prefer to deploy manually or need more control:

### 1. Build and Push Docker Image

```bash
# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1
REPO_NAME=safesim

# Create ECR repository
aws ecr create-repository --repository-name $REPO_NAME --region $REGION

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Build image
docker build -t $REPO_NAME:latest .

# Tag and push
docker tag $REPO_NAME:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:latest
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:latest
```

### 2. Create App Runner Service

```bash
# Create IAM role for App Runner (if not exists)
aws iam create-role \
    --role-name AppRunnerECRAccessRole \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "build.apprunner.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }'

aws iam attach-role-policy \
    --role-name AppRunnerECRAccessRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

# Create App Runner service
aws apprunner create-service \
    --service-name safesim-service \
    --source-configuration '{
        "ImageRepository": {
            "ImageIdentifier": "'${ACCOUNT_ID}'.dkr.ecr.'${REGION}'.amazonaws.com/'${REPO_NAME}':latest",
            "ImageConfiguration": {
                "Port": "8501",
                "RuntimeEnvironmentVariables": {}
            },
            "ImageRepositoryType": "ECR"
        },
        "AutoDeploymentsEnabled": true,
        "AuthenticationConfiguration": {
            "AccessRoleArn": "arn:aws:iam::'${ACCOUNT_ID}':role/AppRunnerECRAccessRole"
        }
    }' \
    --instance-configuration '{
        "Cpu": "1 vCPU",
        "Memory": "2 GB"
    }' \
    --health-check-configuration '{
        "Protocol": "HTTP",
        "Path": "/api/health",
        "Interval": 10,
        "Timeout": 5,
        "HealthyThreshold": 1,
        "UnhealthyThreshold": 5
    }' \
    --region $REGION
```

### 3. Set Up API Gateway

```bash
# Get App Runner service URL
SERVICE_URL=$(aws apprunner describe-service \
    --service-arn <SERVICE_ARN> \
    --region $REGION \
    --query 'Service.ServiceUrl' \
    --output text)

# Create API Gateway HTTP API
API_ID=$(aws apigatewayv2 create-api \
    --name safesim-api \
    --protocol-type HTTP \
    --cors-configuration AllowOrigins="*",AllowMethods="GET,POST,PUT,DELETE,OPTIONS",AllowHeaders="*",MaxAge=300 \
    --region $REGION \
    --query 'ApiId' \
    --output text)

# Create integration
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id $API_ID \
    --integration-type HTTP_PROXY \
    --integration-uri "$SERVICE_URL" \
    --integration-method ANY \
    --payload-format-version "1.0" \
    --connection-type INTERNET \
    --timeout-in-millis 30000 \
    --region $REGION \
    --query 'IntegrationId' \
    --output text)

# Create routes
aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key '$default' \
    --target "integrations/$INTEGRATION_ID" \
    --region $REGION

aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'GET /api/{proxy+}' \
    --target "integrations/$INTEGRATION_ID" \
    --region $REGION

aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'POST /api/{proxy+}' \
    --target "integrations/$INTEGRATION_ID" \
    --region $REGION

# Create stage
aws apigatewayv2 create-stage \
    --api-id $API_ID \
    --stage-name prod \
    --auto-deploy \
    --region $REGION

# Your API Gateway URL
echo "https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"
```

## Environment Variables

### Using .env File (Recommended)

The deployment script automatically reads environment variables from a `.env` file and passes them to App Runner:

1. **Create `.env` file:**
   ```bash
   cp .env.example .env
   ```

2. **Add your API keys:**
   ```bash
   OPENAI_API_KEY=sk-your-key-here
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

3. **Deploy:** The script will automatically load and configure these variables.

### Manual Configuration

To update environment variables after deployment:

```bash
# Update service with environment variables
aws apprunner update-service \
    --service-arn <SERVICE_ARN> \
    --source-configuration '{
        "ImageRepository": {
            "ImageIdentifier": "<IMAGE_URI>",
            "ImageConfiguration": {
                "Port": "8501",
                "RuntimeEnvironmentVariables": {
                    "OPENAI_API_KEY": "your-key",
                    "ANTHROPIC_API_KEY": "your-key"
                }
            },
            "ImageRepositoryType": "ECR"
        }
    }' \
    --region $REGION
```

### Using AWS Secrets Manager (Production)

For production deployments, use AWS Secrets Manager:

```bash
# Store secrets
aws secretsmanager create-secret \
    --name safesim/api-keys \
    --secret-string '{"OPENAI_API_KEY":"your-key","ANTHROPIC_API_KEY":"your-key"}'

# Reference in App Runner (requires additional IAM permissions)
```

**Note:** The `.env` file approach is simpler for development. For production, consider using AWS Secrets Manager or Parameter Store.

## Testing the Deployment

### Test Streamlit UI

```bash
# Open in browser
open https://<api-id>.execute-api.<region>.amazonaws.com/prod
```

### Test API

```bash
# Health check
curl https://<api-id>.execute-api.<region>.amazonaws.com/prod/api/health

# Simplify text
curl -X POST https://<api-id>.execute-api.<region>.amazonaws.com/prod/api/simplify \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patient prescribed 50mg Atenolol PO q.d. for hypertension.",
    "llm_backend": "dummy",
    "strictness": "high"
  }'

# View API docs
open https://<api-id>.execute-api.<region>.amazonaws.com/prod/api/docs
```

## Updating the Deployment

To update your deployment after making code changes:

```bash
# Simply run the deployment script again
./scripts/deploy-aws.sh [region] [service-name]
```

The script will:
- Rebuild the Docker image
- Push to ECR
- Update the App Runner service (auto-deploys)

## Custom Domain Setup

To use a custom domain:

1. **Request SSL Certificate** in AWS Certificate Manager (ACM)
2. **Create Domain Name** in API Gateway:
   ```bash
   aws apigatewayv2 create-domain-name \
       --domain-name api.yourdomain.com \
       --domain-name-configurations CertificateArn=<CERT_ARN> \
       --region $REGION
   ```
3. **Create API Mapping**:
   ```bash
   aws apigatewayv2 create-api-mapping \
       --domain-name api.yourdomain.com \
       --api-id $API_ID \
       --stage prod \
       --region $REGION
   ```
4. **Update DNS** records to point to the API Gateway domain

## Cost Estimation

**App Runner:**
- ~$0.007/hour (~$5/month for minimal usage)
- Scales automatically based on traffic

**API Gateway:**
- $3.50 per million requests
- First 1M requests/month free (for first 12 months)

**ECR:**
- $0.10 per GB/month for storage
- Minimal cost for small images

**Total:** ~$5-10/month for light usage

## Troubleshooting

### Service won't start

1. Check CloudWatch logs:
   ```bash
   aws apprunner list-operations --service-arn <SERVICE_ARN> --region $REGION
   ```

2. View logs in AWS Console → App Runner → Service → Logs

### API Gateway returns 502

1. Check App Runner service is healthy
2. Verify integration URI is correct
3. Check security groups allow traffic

### High memory usage

1. Increase App Runner instance size:
   ```bash
   aws apprunner update-service \
       --service-arn <SERVICE_ARN> \
       --instance-configuration Cpu="2 vCPU",Memory="4 GB" \
       --region $REGION
   ```

## Security Best Practices

1. **Use Secrets Manager** for API keys (don't hardcode)
2. **Enable CloudWatch Logging** for monitoring
3. **Set up CloudWatch Alarms** for errors
4. **Use IAM roles** instead of access keys where possible
5. **Enable API Gateway throttling** to prevent abuse
6. **Use custom domain** with SSL certificate

## Next Steps

1. Set up CI/CD pipeline (GitHub Actions, CodePipeline)
2. Configure custom domain
3. Set up monitoring and alerts
4. Implement rate limiting
5. Add authentication if needed

## Support

For issues or questions:
- Check CloudWatch logs
- Review AWS App Runner documentation
- Review API Gateway documentation

