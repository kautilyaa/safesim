#!/bin/bash
# Comprehensive AWS Deployment Script for SafeSim
# Deploys both Streamlit UI and FastAPI API with fixed URL via API Gateway
# Usage: ./scripts/deploy-aws.sh [--profile PROFILE] [--region REGION] [--service-name NAME] [--env-file FILE]

set -e

# Default values
REGION="us-east-1"
SERVICE_NAME="safesim-service"
REPO_NAME="safesim"
IMAGE_TAG="latest"
AWS_PROFILE=""
ENV_FILE=".env"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --service-name)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --profile PROFILE     AWS profile to use (default: default)"
            echo "  --region REGION       AWS region (default: us-east-1)"
            echo "  --service-name NAME   App Runner service name (default: safesim-service)"
            echo "  --env-file FILE       Path to .env file (default: .env)"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  The script will read environment variables from the specified .env file"
            echo "  and pass them to App Runner. Supported variables:"
            echo "    - OPENAI_API_KEY"
            echo "    - ANTHROPIC_API_KEY"
            echo "    - Any other variables you need"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build AWS CLI command prefix
AWS_CMD="aws"
if [ ! -z "$AWS_PROFILE" ]; then
    AWS_CMD="aws --profile $AWS_PROFILE"
    echo "🔐 Using AWS profile: $AWS_PROFILE"
fi

echo "🚀 SafeSim AWS Deployment"
echo "Region: $REGION"
echo "Service Name: $SERVICE_NAME"
echo "Environment File: $ENV_FILE"
echo ""

# Check prerequisites
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install it first."
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "⚠️  jq is not installed. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install jq || echo "Please install jq manually: brew install jq"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y jq || echo "Please install jq manually"
    fi
fi

# Load environment variables from .env file if it exists
ENV_VARS_JSON="{}"
if [ -f "$ENV_FILE" ]; then
    echo "📄 Loading environment variables from $ENV_FILE..."
    
    # Read .env file and convert to JSON format for App Runner
    ENV_VARS_JSON="{"
    FIRST=true
    
    while IFS='=' read -r key value || [ -n "$key" ]; do
        # Skip empty lines and comments
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        
        # Remove leading/trailing whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        
        # Remove quotes if present
        value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")
        
        if [ ! -z "$key" ] && [ ! -z "$value" ]; then
            if [ "$FIRST" = true ]; then
                FIRST=false
            else
                ENV_VARS_JSON="${ENV_VARS_JSON},"
            fi
            # Escape quotes in value
            value_escaped=$(echo "$value" | sed 's/"/\\"/g')
            ENV_VARS_JSON="${ENV_VARS_JSON}\"${key}\":\"${value_escaped}\""
        fi
    done < "$ENV_FILE"
    
    ENV_VARS_JSON="${ENV_VARS_JSON}}"
    
    if [ "$ENV_VARS_JSON" != "{}" ]; then
        echo "✅ Loaded environment variables from $ENV_FILE"
        # Show which variables were loaded (without values)
        echo "   Variables: $(echo "$ENV_VARS_JSON" | jq -r 'keys | join(", ")' 2>/dev/null || echo "multiple")"
    else
        echo "⚠️  No environment variables found in $ENV_FILE"
        ENV_VARS_JSON="{}"
    fi
else
    echo "⚠️  Environment file $ENV_FILE not found. Skipping environment variables."
    echo "   Create a .env file with your API keys if needed:"
    echo "   OPENAI_API_KEY=your-key"
    echo "   ANTHROPIC_API_KEY=your-key"
fi
echo ""

# Get AWS account ID
echo "📋 Getting AWS account information..."
ACCOUNT_ID=$($AWS_CMD sts get-caller-identity --query Account --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ Failed to get AWS account ID. Please check your AWS credentials."
    echo "   Make sure your AWS profile is configured correctly."
    exit 1
fi

echo "✅ AWS Account ID: $ACCOUNT_ID"
echo ""

# Step 1: Create ECR repository if it doesn't exist
echo "📦 Step 1: Setting up ECR repository..."
ECR_REPO_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"

if $AWS_CMD ecr describe-repositories --repository-names $REPO_NAME --region $REGION &> /dev/null; then
    echo "✅ ECR repository already exists: $REPO_NAME"
else
    echo "Creating ECR repository..."
    $AWS_CMD ecr create-repository --repository-name $REPO_NAME --region $REGION
    echo "✅ Created ECR repository: $REPO_NAME"
fi

# Step 2: Login to ECR
echo ""
echo "🔐 Step 2: Logging into ECR..."
$AWS_CMD ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REPO_URI
echo "✅ Logged into ECR"

# Step 3: Build Docker image
echo ""
echo "🔨 Step 3: Building Docker image..."
docker buildx build --platform linux/amd64 -t $REPO_NAME:$IMAGE_TAG . --load
echo "✅ Docker image built"

# Step 4: Tag and push image
echo ""
echo "📤 Step 4: Tagging and pushing image to ECR..."
docker tag $REPO_NAME:$IMAGE_TAG $ECR_REPO_URI:$IMAGE_TAG
docker push $ECR_REPO_URI:$IMAGE_TAG
echo "✅ Image pushed to ECR: $ECR_REPO_URI:$IMAGE_TAG"

# Step 5: Create IAM role for App Runner (if needed)
echo ""
echo "🔑 Step 5: Setting up IAM role for App Runner..."
ROLE_NAME="AppRunnerECRAccessRole"

# Check if role exists
if $AWS_CMD iam get-role --role-name $ROLE_NAME &> /dev/null; then
    echo "✅ IAM role already exists: $ROLE_NAME"
else
    echo "Creating IAM role for App Runner..."
    
    # Trust policy for App Runner
    cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "build.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create role
    $AWS_CMD iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/trust-policy.json

    # Attach ECR access policy
    $AWS_CMD iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

    echo "✅ Created IAM role: $ROLE_NAME"
    rm /tmp/trust-policy.json
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# Step 6: Create App Runner service configuration
echo ""
echo "📝 Step 6: Creating App Runner service configuration..."

# Convert environment variables JSON to App Runner format (dictionary, not array)
ENV_VARS_DICT="{}"
if [ "$ENV_VARS_JSON" != "{}" ]; then
    # App Runner expects a simple dictionary: {"KEY": "value"}
    ENV_VARS_DICT="$ENV_VARS_JSON"
fi

# Check if service already exists
SERVICE_ARN_PREFIX="arn:aws:apprunner:${REGION}:${ACCOUNT_ID}:service/${SERVICE_NAME}"
if $AWS_CMD apprunner describe-service --service-arn "$SERVICE_ARN_PREFIX" --region $REGION &> /dev/null 2>&1; then
    echo "⚠️  App Runner service already exists. Checking service status..."
    
    # Get current service status
    SERVICE_STATUS=$($AWS_CMD apprunner describe-service \
        --service-arn "$SERVICE_ARN_PREFIX" \
        --region $REGION \
        --query 'Service.Status' \
        --output text 2>/dev/null || echo "")
    
    # Wait for service to be in a stable state if it's currently updating
    if [ "$SERVICE_STATUS" == "OPERATION_IN_PROGRESS" ] || [ "$SERVICE_STATUS" == "CREATE_FAILED" ] || [ "$SERVICE_STATUS" == "UPDATE_FAILED" ]; then
        echo "⏳ Service is in state: $SERVICE_STATUS. Waiting for stable state..."
        
        # Wait for service to be ready (up to 10 minutes)
        MAX_WAIT=600
        ELAPSED=0
        while [ $ELAPSED -lt $MAX_WAIT ]; do
            SERVICE_STATUS=$($AWS_CMD apprunner describe-service \
                --service-arn "$SERVICE_ARN_PREFIX" \
                --region $REGION \
                --query 'Service.Status' \
                --output text 2>/dev/null || echo "")
            
            if [ "$SERVICE_STATUS" == "RUNNING" ] || [ "$SERVICE_STATUS" == "OPERATION_SUCCESS" ]; then
                echo "✅ Service is now in stable state: $SERVICE_STATUS"
                break
            fi
            
            if [ "$SERVICE_STATUS" == "CREATE_FAILED" ] || [ "$SERVICE_STATUS" == "UPDATE_FAILED" ] || [ "$SERVICE_STATUS" == "DELETE_FAILED" ]; then
                echo "⚠️  Service is in failed state: $SERVICE_STATUS. Attempting to update anyway..."
                break
            fi
            
            echo "   Still waiting... (${ELAPSED}s elapsed, status: $SERVICE_STATUS)"
            sleep 10
            ELAPSED=$((ELAPSED + 10))
        done
        
        if [ $ELAPSED -ge $MAX_WAIT ]; then
            echo "⚠️  Timeout waiting for service to stabilize. Attempting update anyway..."
        fi
    fi
    
    echo "Updating service..."
    
    # Create source configuration with environment variables (separate from instance/health config)
    cat > /tmp/apprunner-source-config.json <<EOF
{
  "ImageRepository": {
    "ImageIdentifier": "${ECR_REPO_URI}:${IMAGE_TAG}",
    "ImageConfiguration": {
      "Port": "8501",
      "RuntimeEnvironmentVariables": $(echo "$ENV_VARS_DICT" | jq .)
    },
    "ImageRepositoryType": "ECR"
  },
  "AutoDeploymentsEnabled": true,
  "AuthenticationConfiguration": {
    "AccessRoleArn": "${ROLE_ARN}"
  }
}
EOF

    # Create instance configuration
    cat > /tmp/apprunner-instance-config.json <<EOF
{
  "Cpu": "1 vCPU",
  "Memory": "2 GB"
}
EOF

    # Create health check configuration
    cat > /tmp/apprunner-health-config.json <<EOF
{
  "Protocol": "HTTP",
  "Path": "/api/health",
  "Interval": 10,
  "Timeout": 5,
  "HealthyThreshold": 1,
  "UnhealthyThreshold": 5
}
EOF

    # Attempt to update service with retry logic
    MAX_RETRIES=3
    RETRY_COUNT=0
    UPDATE_SUCCESS=false
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        UPDATE_OUTPUT=$($AWS_CMD apprunner update-service \
            --service-arn "$SERVICE_ARN_PREFIX" \
            --source-configuration file:///tmp/apprunner-source-config.json \
            --instance-configuration file:///tmp/apprunner-instance-config.json \
            --health-check-configuration file:///tmp/apprunner-health-config.json \
            --region $REGION \
            --query 'Service.ServiceArn' \
            --output text 2>&1)
        
        if [ $? -eq 0 ]; then
            SERVICE_ARN=$UPDATE_OUTPUT
            UPDATE_SUCCESS=true
            break
        else
            # Check if error is due to invalid state
            if echo "$UPDATE_OUTPUT" | grep -q "InvalidStateException\|OPERATION_IN_PROGRESS"; then
                RETRY_COUNT=$((RETRY_COUNT + 1))
                if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                    echo "⚠️  Service is still updating. Waiting 30 seconds before retry ($RETRY_COUNT/$MAX_RETRIES)..."
                    sleep 30
                else
                    echo "❌ Service update failed after $MAX_RETRIES retries. Service may still be updating."
                    echo "   You can manually update the service later or wait for the current operation to complete."
                    echo "   Error: $UPDATE_OUTPUT"
                    exit 1
                fi
            else
                echo "❌ Failed to update service: $UPDATE_OUTPUT"
                rm /tmp/apprunner-source-config.json /tmp/apprunner-instance-config.json /tmp/apprunner-health-config.json
                exit 1
            fi
        fi
    done
    
    if [ "$UPDATE_SUCCESS" = true ]; then
        echo "✅ App Runner service update initiated successfully"
        echo "   Service ARN: $SERVICE_ARN"
        echo "   Note: The update will take a few minutes to complete."
    fi
    
    rm /tmp/apprunner-source-config.json /tmp/apprunner-instance-config.json /tmp/apprunner-health-config.json
else
    echo "Creating new App Runner service..."
    
    # Create service configuration with environment variables
    cat > /tmp/apprunner-service.json <<EOF
{
  "ServiceName": "${SERVICE_NAME}",
  "SourceConfiguration": {
    "ImageRepository": {
      "ImageIdentifier": "${ECR_REPO_URI}:${IMAGE_TAG}",
      "ImageConfiguration": {
        "Port": "8501",
        "RuntimeEnvironmentVariables": $(echo "$ENV_VARS_DICT" | jq .)
      },
      "ImageRepositoryType": "ECR"
    },
    "AutoDeploymentsEnabled": true,
    "AuthenticationConfiguration": {
      "AccessRoleArn": "${ROLE_ARN}"
    }
  },
  "InstanceConfiguration": {
    "Cpu": "1 vCPU",
    "Memory": "2 GB"
  },
  "HealthCheckConfiguration": {
    "Protocol": "HTTP",
    "Path": "/api/health",
    "Interval": 10,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }
}
EOF

    SERVICE_ARN=$($AWS_CMD apprunner create-service \
        --cli-input-json file:///tmp/apprunner-service.json \
        --region $REGION \
        --query 'Service.ServiceArn' \
        --output text)
    
    echo "✅ App Runner service created with environment variables"
    rm /tmp/apprunner-service.json
fi

echo "Service ARN: $SERVICE_ARN"

# Wait for service to be ready
echo ""
echo "⏳ Waiting for App Runner service to be ready (this may take a few minutes)..."
$AWS_CMD apprunner wait service-in-service --service-arn $SERVICE_ARN --region $REGION || true

# Get service URL
SERVICE_URL=$($AWS_CMD apprunner describe-service \
    --service-arn $SERVICE_ARN \
    --region $REGION \
    --query 'Service.ServiceUrl' \
    --output text)

# Ensure SERVICE_URL has https:// protocol prefix for API Gateway
if [[ ! "$SERVICE_URL" =~ ^https?:// ]]; then
    SERVICE_URL="https://${SERVICE_URL}"
fi

echo "✅ App Runner service is ready!"
echo "Service URL: $SERVICE_URL"
echo ""

# Step 7: Setup API Gateway
echo "🌐 Step 7: Setting up API Gateway with fixed URL..."

# Check if API Gateway already exists
EXISTING_API=$($AWS_CMD apigatewayv2 get-apis \
    --region $REGION \
    --query "Items[?Name=='safesim-api'].ApiId" \
    --output text)

if [ ! -z "$EXISTING_API" ] && [ "$EXISTING_API" != "None" ]; then
    echo "⚠️  API Gateway already exists. Checking integration..."
    API_ID=$EXISTING_API
    
    # Get existing integration
    INTEGRATION_ID=$($AWS_CMD apigatewayv2 get-integrations \
        --api-id $API_ID \
        --region $REGION \
        --query 'Items[0].IntegrationId' \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$INTEGRATION_ID" ] && [ "$INTEGRATION_ID" != "None" ]; then
        # Update existing integration
        echo "Updating existing integration..."
        $AWS_CMD apigatewayv2 update-integration \
            --api-id $API_ID \
            --integration-id $INTEGRATION_ID \
            --integration-uri "$SERVICE_URL" \
            --region $REGION \
            > /dev/null
        
        echo "✅ Updated API Gateway integration"
    else
        # Create new integration if it doesn't exist
        echo "No integration found. Creating new integration..."
        INTEGRATION_ID=$($AWS_CMD apigatewayv2 create-integration \
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
        
        echo "✅ Created new integration: $INTEGRATION_ID"
        
        # Create routes if they don't exist
        echo "Setting up routes..."
        
        # Check if default route exists
        DEFAULT_ROUTE=$($AWS_CMD apigatewayv2 get-routes \
            --api-id $API_ID \
            --region $REGION \
            --query "Items[?RouteKey=='\\$default'].RouteId" \
            --output text 2>/dev/null || echo "")
        
        if [ -z "$DEFAULT_ROUTE" ] || [ "$DEFAULT_ROUTE" == "None" ]; then
            $AWS_CMD apigatewayv2 create-route \
                --api-id $API_ID \
                --route-key '$default' \
                --target "integrations/$INTEGRATION_ID" \
                --region $REGION \
                > /dev/null
        fi
        
        # Check if API routes exist
        API_ROUTE=$($AWS_CMD apigatewayv2 get-routes \
            --api-id $API_ID \
            --region $REGION \
            --query "Items[?RouteKey=='GET /api/{proxy+}'].RouteId" \
            --output text 2>/dev/null || echo "")
        
        if [ -z "$API_ROUTE" ] || [ "$API_ROUTE" == "None" ]; then
            $AWS_CMD apigatewayv2 create-route \
                --api-id $API_ID \
                --route-key 'GET /api/{proxy+}' \
                --target "integrations/$INTEGRATION_ID" \
                --region $REGION \
                > /dev/null
            
            $AWS_CMD apigatewayv2 create-route \
                --api-id $API_ID \
                --route-key 'POST /api/{proxy+}' \
                --target "integrations/$INTEGRATION_ID" \
                --region $REGION \
                > /dev/null
            
            $AWS_CMD apigatewayv2 create-route \
                --api-id $API_ID \
                --route-key 'GET /api/health' \
                --target "integrations/$INTEGRATION_ID" \
                --region $REGION \
                > /dev/null
        fi
        
        echo "✅ Routes configured"
        
        # Check if stage exists and create if missing
        STAGE_EXISTS=$($AWS_CMD apigatewayv2 get-stage \
            --api-id $API_ID \
            --stage-name prod \
            --region $REGION \
            --query 'StageName' \
            --output text 2>/dev/null || echo "")

        if [ -z "$STAGE_EXISTS" ] || [ "$STAGE_EXISTS" == "None" ]; then
            echo "Creating production stage..."
            $AWS_CMD apigatewayv2 create-stage \
                --api-id $API_ID \
                --stage-name prod \
                --auto-deploy \
                --default-route-settings ThrottlingBurstLimit=5000,ThrottlingRateLimit=2000,DetailedMetricsEnabled=true \
                --region $REGION \
                > /dev/null
            echo "✅ Created production stage"
        else
            echo "✅ Stage 'prod' already exists"
        fi
    fi
else
    echo "Creating new API Gateway..."
    
    # Create HTTP API
    API_ID=$($AWS_CMD apigatewayv2 create-api \
        --name safesim-api \
        --protocol-type HTTP \
        --cors-configuration AllowOrigins="*",AllowMethods="GET,POST,PUT,DELETE,OPTIONS",AllowHeaders="*",MaxAge=300 \
        --region $REGION \
        --query 'ApiId' \
        --output text)
    
    echo "✅ Created API Gateway: $API_ID"
    
    # Create integration
    INTEGRATION_ID=$($AWS_CMD apigatewayv2 create-integration \
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
    
    echo "✅ Created integration: $INTEGRATION_ID"
    
    # Create routes
    echo "Creating routes..."
    
    # Default route (catch-all for Streamlit)
    $AWS_CMD apigatewayv2 create-route \
        --api-id $API_ID \
        --route-key '$default' \
        --target "integrations/$INTEGRATION_ID" \
        --region $REGION \
        > /dev/null
    
    # API routes
    $AWS_CMD apigatewayv2 create-route \
        --api-id $API_ID \
        --route-key 'GET /api/{proxy+}' \
        --target "integrations/$INTEGRATION_ID" \
        --region $REGION \
        > /dev/null
    
    $AWS_CMD apigatewayv2 create-route \
        --api-id $API_ID \
        --route-key 'POST /api/{proxy+}' \
        --target "integrations/$INTEGRATION_ID" \
        --region $REGION \
        > /dev/null
    
    # Health check route
    $AWS_CMD apigatewayv2 create-route \
        --api-id $API_ID \
        --route-key 'GET /api/health' \
        --target "integrations/$INTEGRATION_ID" \
        --region $REGION \
        > /dev/null
    
    echo "✅ Created routes"
    
    # Create stage
    $AWS_CMD apigatewayv2 create-stage \
        --api-id $API_ID \
        --stage-name prod \
        --auto-deploy \
        --default-route-settings ThrottlingBurstLimit=5000,ThrottlingRateLimit=2000,DetailedMetricsEnabled=true \
        --region $REGION \
        > /dev/null
    
    echo "✅ Created production stage"
fi

# Get API Gateway endpoint
API_ENDPOINT="https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🎉 SafeSim is now deployed!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📍 Fixed URL (API Gateway):"
echo "   $API_ENDPOINT"
echo ""
echo "🌐 Streamlit UI:"
echo "   $API_ENDPOINT"
echo ""
echo "🔌 API Endpoints:"
echo "   - API Docs:      $API_ENDPOINT/api/docs"
echo "   - Health Check:  $API_ENDPOINT/api/health"
echo "   - Simplify:      $API_ENDPOINT/api/simplify"
echo ""
echo "📋 Direct App Runner URL (for reference):"
echo "   $SERVICE_URL"
echo ""
if [ "$ENV_VARS_JSON" != "{}" ]; then
    echo "🔐 Environment Variables:"
    echo "   Loaded from $ENV_FILE and configured in App Runner"
fi
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "💡 Next steps:"
echo "1. Test the API: curl $API_ENDPOINT/api/health"
echo "2. Visit the UI: Open $API_ENDPOINT in your browser"
echo "3. (Optional) Set up custom domain in API Gateway console"
echo ""
echo "📝 To update the deployment:"
echo "   ./scripts/deploy-aws.sh --profile $AWS_PROFILE --region $REGION --service-name $SERVICE_NAME --env-file $ENV_FILE"
echo ""
