#!/bin/bash
# Setup API Gateway for SafeSim
# Usage: ./scripts/setup-api-gateway.sh <backend-url> [region] [domain-name]

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backend-url> [region] [domain-name]"
    echo "Example: $0 http://ec2-54-123-45-67.compute-1.amazonaws.com:8501 us-east-1 api.safesim.example.com"
    exit 1
fi

BACKEND_URL=$1
REGION=${2:-us-east-1}
DOMAIN_NAME=${3:-""}

echo "🚀 Setting up API Gateway for SafeSim"
echo "Backend URL: $BACKEND_URL"
echo "Region: $REGION"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "⚠️  jq is not installed. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install jq
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y jq
    fi
fi

echo "📝 Creating API Gateway HTTP API..."

# Create HTTP API
API_ID=$(aws apigatewayv2 create-api \
    --name safesim-api \
    --protocol-type HTTP \
    --cors-configuration AllowOrigins="*",AllowMethods="GET,POST,PUT,DELETE,OPTIONS",AllowHeaders="*",MaxAge=300 \
    --region $REGION \
    --query 'ApiId' \
    --output text)

echo "✅ Created API Gateway: $API_ID"

# Create integration
echo "🔗 Creating integration with backend..."
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id $API_ID \
    --integration-type HTTP_PROXY \
    --integration-uri "$BACKEND_URL" \
    --integration-method ANY \
    --payload-format-version "1.0" \
    --connection-type INTERNET \
    --timeout-in-millis 30000 \
    --region $REGION \
    --query 'IntegrationId' \
    --output text)

echo "✅ Created integration: $INTEGRATION_ID"

# Create default route (catch-all)
echo "🛣️  Creating routes..."
aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key '$default' \
    --target "integrations/$INTEGRATION_ID" \
    --region $REGION \
    > /dev/null

# Create health check route
aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'GET /_stcore/health' \
    --target "integrations/$INTEGRATION_ID" \
    --region $REGION \
    > /dev/null

echo "✅ Created routes"

# Create stage
echo "🎭 Creating production stage..."
aws apigatewayv2 create-stage \
    --api-id $API_ID \
    --stage-name prod \
    --auto-deploy \
    --default-route-settings ThrottlingBurstLimit=5000,ThrottlingRateLimit=2000,DetailedMetricsEnabled=true \
    --region $REGION \
    > /dev/null

echo "✅ Created stage"

# Get API endpoint
API_ENDPOINT="https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"

echo ""
echo "✅ API Gateway setup complete!"
echo ""
echo "📋 API Endpoint: $API_ENDPOINT"
echo ""
echo "🔗 Access your SafeSim app at:"
echo "   $API_ENDPOINT"
echo ""
echo "📝 Next steps:"
echo "1. Test the endpoint: curl $API_ENDPOINT/_stcore/health"
echo "2. (Optional) Set up custom domain:"
echo "   - Request SSL certificate in ACM"
echo "   - Create domain name in API Gateway"
echo "   - Update DNS records"
echo ""
echo "💡 To update backend URL later:"
echo "   aws apigatewayv2 update-integration --api-id $API_ID --integration-id $INTEGRATION_ID --integration-uri \"<new-url>\" --region $REGION"

