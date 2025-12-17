# API Gateway Deployment Guide for SafeSim

This guide shows you how to deploy SafeSim behind AWS API Gateway, providing a single public endpoint with built-in security, throttling, and monitoring.

## Architecture Overview

```
Internet → API Gateway → Streamlit Backend (EC2/ECS/App Runner)
```

**Benefits:**
- Single public endpoint
- Built-in DDoS protection
- Request throttling and rate limiting
- CloudWatch monitoring and logging
- Custom domain support with SSL
- Cost-effective ($3.50 per million requests)

## Prerequisites

1. Streamlit backend already deployed (EC2, ECS, or App Runner)
2. Backend URL accessible from API Gateway
3. AWS CLI configured

## Quick Start

### Step 1: Deploy Streamlit Backend

First, deploy your Streamlit app using one of these methods:

**Option A: App Runner**
```bash
./scripts/deploy-apprunner.sh us-east-1
# Note the App Runner service URL
```

**Option B: EC2**
```bash
./scripts/deploy-ec2.sh <instance-ip> <key-file>
# Note the EC2 public IP and port (8501)
```

**Option C: ECS/Fargate**
```bash
# Deploy to ECS and note the ALB URL or task IP
```

### Step 2: Setup API Gateway

Run the setup script with your backend URL:

```bash
# For App Runner
./scripts/setup-api-gateway.sh https://your-app-runner-url.us-east-1.awsapprunner.com

# For EC2
./scripts/setup-api-gateway.sh http://ec2-54-123-45-67.compute-1.amazonaws.com:8501

# For ECS/ALB
./scripts/setup-api-gateway.sh http://your-alb-123456789.us-east-1.elb.amazonaws.com:8501
```

The script will:
1. Create an HTTP API Gateway (v2)
2. Configure proxy integration to your backend
3. Set up routes for all requests
4. Create a production stage
5. Output your API Gateway endpoint

### Step 3: Access Your Application

Your SafeSim app is now available at:
```
https://<api-id>.execute-api.<region>.amazonaws.com/prod
```

## Manual Setup (Alternative)

If you prefer to set up manually or use CloudFormation:

### Using AWS CLI

```bash
# 1. Create HTTP API
API_ID=$(aws apigatewayv2 create-api \
    --name safesim-api \
    --protocol-type HTTP \
    --cors-configuration AllowOrigins="*",AllowMethods="GET,POST,PUT,DELETE,OPTIONS",AllowHeaders="*" \
    --query 'ApiId' \
    --output text)

# 2. Create integration
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id $API_ID \
    --integration-type HTTP_PROXY \
    --integration-uri "http://your-backend-url:8501" \
    --integration-method ANY \
    --payload-format-version "1.0" \
    --connection-type INTERNET \
    --query 'IntegrationId' \
    --output text)

# 3. Create default route
aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key '$default' \
    --target "integrations/$INTEGRATION_ID"

# 4. Create stage
aws apigatewayv2 create-stage \
    --api-id $API_ID \
    --stage-name prod \
    --auto-deploy

# 5. Get endpoint
echo "https://${API_ID}.execute-api.$(aws configure get region).amazonaws.com/prod"
```

### Using CloudFormation

```bash
# Update api-gateway-config.yaml with your backend URL
# Then deploy:
aws cloudformation create-stack \
    --stack-name safesim-api-gateway \
    --template-body file://api-gateway-config.yaml \
    --parameters ParameterKey=StreamlitBackendUrl,ParameterValue=http://your-backend:8501 \
    --region us-east-1
```

## Custom Domain Setup

### Step 1: Request SSL Certificate

```bash
# Request certificate in ACM (must be in us-east-1 for API Gateway)
aws acm request-certificate \
    --domain-name api.safesim.example.com \
    --validation-method DNS \
    --region us-east-1

# Follow DNS validation instructions
```

### Step 2: Create Domain Name in API Gateway

```bash
CERT_ARN="arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID"

aws apigatewayv2 create-domain-name \
    --domain-name api.safesim.example.com \
    --domain-name-configurations CertificateArn=$CERT_ARN,EndpointType=REGIONAL \
    --region us-east-1
```

### Step 3: Create API Mapping

```bash
API_ID="your-api-id"
DOMAIN_NAME="api.safesim.example.com"

aws apigatewayv2 create-api-mapping \
    --domain-name $DOMAIN_NAME \
    --api-id $API_ID \
    --stage prod \
    --region us-east-1
```

### Step 4: Update DNS

Add a CNAME record pointing to the API Gateway domain:
```
api.safesim.example.com → <api-gateway-domain>.execute-api.us-east-1.amazonaws.com
```

## Configuration Options

### Throttling and Rate Limiting

Update stage settings:

```bash
aws apigatewayv2 update-stage \
    --api-id $API_ID \
    --stage-name prod \
    --default-route-settings \
        ThrottlingBurstLimit=10000,ThrottlingRateLimit=5000,DetailedMetricsEnabled=true
```

### CORS Configuration

Update CORS settings:

```bash
aws apigatewayv2 update-api \
    --api-id $API_ID \
    --cors-configuration \
        AllowOrigins="https://yourdomain.com",AllowMethods="GET,POST",AllowHeaders="*"
```

### Request/Response Transformations

For advanced transformations, use API Gateway mapping templates or Lambda authorizers.

## Monitoring and Logging

### CloudWatch Logs

Enable access logging:

```bash
LOG_GROUP="/aws/apigateway/safesim"

aws logs create-log-group --log-group-name $LOG_GROUP

aws apigatewayv2 update-stage \
    --api-id $API_ID \
    --stage-name prod \
    --access-log-settings \
        DestinationArn=arn:aws:logs:REGION:ACCOUNT:log-group:$LOG_GROUP,Format='$requestId $ip $requestTime $httpMethod $routeKey $status $protocol $responseLength'
```

### CloudWatch Metrics

View metrics in CloudWatch:
- `Count` - Number of requests
- `4XXError` - Client errors
- `5XXError` - Server errors
- `Latency` - Response time
- `IntegrationLatency` - Backend response time

## Security Best Practices

1. **Use API Keys** (for simple authentication):
```bash
# Create API key
API_KEY_ID=$(aws apigatewayv2 create-api-key --name safesim-key --query 'Id' --output text)

# Create usage plan
USAGE_PLAN_ID=$(aws apigateway create-usage-plan \
    --name safesim-plan \
    --api-stages apiId=$API_ID,stage=prod \
    --throttle burstLimit=1000,rateLimit=500 \
    --query 'id' --output text)

# Associate API key
aws apigateway create-usage-plan-key \
    --usage-plan-id $USAGE_PLAN_ID \
    --key-id $API_KEY_ID \
    --key-type API_KEY
```

2. **Use Lambda Authorizer** (for JWT/OAuth):
   - Create Lambda function for authentication
   - Configure as authorizer in API Gateway
   - See AWS documentation for details

3. **Enable WAF** (Web Application Firewall):
   - Attach AWS WAF to API Gateway
   - Configure rules for SQL injection, XSS, etc.

4. **Restrict IPs** (if needed):
   - Use API Gateway resource policy
   - Or use WAF IP whitelist rules

## Troubleshooting

### 502 Bad Gateway

- Check backend is running and accessible
- Verify security groups allow traffic from API Gateway
- Check CloudWatch logs for integration errors

### CORS Errors

- Update CORS configuration in API Gateway
- Ensure backend allows OPTIONS requests
- Check browser console for specific CORS errors

### Timeout Issues

- Increase timeout in integration settings (max 30 seconds)
- Optimize backend response time
- Consider caching for static content

### WebSocket Issues

API Gateway HTTP API v2 supports WebSockets, but Streamlit's WebSocket implementation may need special handling. If you encounter issues:

1. Ensure backend supports WebSocket upgrades
2. Check integration timeout settings
3. Consider using Application Load Balancer instead

## Cost Estimation

- **API Gateway**: $3.50 per million requests (first 300M free)
- **Data Transfer**: $0.09 per GB (first 1GB free)
- **Custom Domain**: Free
- **CloudWatch Logs**: $0.50 per GB ingested

**Example**: 100K requests/month = ~$0.35/month

## Updating Backend URL

If you need to change the backend URL:

```bash
aws apigatewayv2 update-integration \
    --api-id $API_ID \
    --integration-id $INTEGRATION_ID \
    --integration-uri "http://new-backend-url:8501"
```

## Cleanup

To remove API Gateway:

```bash
# Delete API (this will delete all associated resources)
aws apigatewayv2 delete-api --api-id $API_ID

# Or using CloudFormation
aws cloudformation delete-stack --stack-name safesim-api-gateway
```

## Next Steps

1. Set up custom domain with SSL
2. Configure API keys or Lambda authorizer
3. Set up CloudWatch alarms
4. Configure auto-scaling for backend
5. Set up CI/CD for API Gateway updates

For more details, see the [AWS API Gateway documentation](https://docs.aws.amazon.com/apigateway/).

