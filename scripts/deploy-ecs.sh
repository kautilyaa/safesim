#!/bin/bash
# Simple ECS Deployment Script for SafeSim Streamlit
# Usage: ./scripts/deploy-ecs.sh [--profile PROFILE] [--region REGION] [--cluster CLUSTER] [--service SERVICE] [--env-file FILE]

set -e

# Default values
REGION="us-east-1"
CLUSTER_NAME="safesim-cluster"
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
        --cluster)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --service)
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
            echo "  --cluster CLUSTER     ECS cluster name (default: safesim-cluster)"
            echo "  --service SERVICE     ECS service name (default: safesim-service)"
            echo "  --env-file FILE       Path to .env file (default: .env)"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Prerequisites:"
            echo "  1. IAM roles: ecsTaskExecutionRole and ecsTaskRole"
            echo "  2. VPC, subnets, and security groups will be created automatically"
            echo ""
            echo "The script will automatically:"
            echo "  - Create VPC with public subnets (if they don't exist)"
            echo "  - Create Internet Gateway and route tables"
            echo "  - Create security groups for ECS and ALB"
            echo ""
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

echo "🚀 SafeSim ECS Deployment"
echo "Region: $REGION"
echo "Cluster: $CLUSTER_NAME"
echo "Service: $SERVICE_NAME"
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
ENV_VARS=()
if [ -f "$ENV_FILE" ]; then
    echo "📄 Loading environment variables from $ENV_FILE..."
    
    while IFS='=' read -r key value || [ -n "$key" ]; do
        # Skip empty lines and comments
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        
        # Remove leading/trailing whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        
        # Remove quotes if present
        value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")
        
        if [ ! -z "$key" ] && [ ! -z "$value" ]; then
            ENV_VARS+=("{\"name\":\"${key}\",\"value\":\"${value}\"}")
        fi
    done < "$ENV_FILE"
    
    if [ ${#ENV_VARS[@]} -gt 0 ]; then
        echo "✅ Loaded ${#ENV_VARS[@]} environment variables from $ENV_FILE"
    else
        echo "⚠️  No environment variables found in $ENV_FILE"
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

# Step 5: Create or update ECS task definition
echo ""
echo "📝 Step 5: Creating/updating ECS task definition..."

# Build environment variables JSON array
ENV_JSON="["
if [ ${#ENV_VARS[@]} -gt 0 ]; then
    ENV_JSON="${ENV_JSON}$(IFS=,; echo "${ENV_VARS[*]}")"
fi
ENV_JSON="${ENV_JSON}]"

# Create task definition JSON
TASK_DEF_JSON=$(cat <<EOF
{
  "family": "safesim",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "safesim",
      "image": "${ECR_REPO_URI}:${IMAGE_TAG}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8501,
          "protocol": "tcp"
        }
      ],
      "environment": $(echo "$ENV_JSON" | jq .),
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/safesim",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "curl -f http://localhost:8501/_stcore/health || exit 1"
        ],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
EOF
)

# Create CloudWatch log group if it doesn't exist
if ! $AWS_CMD logs describe-log-groups --log-group-name-prefix "/ecs/safesim" --region $REGION --query "logGroups[?logGroupName=='/ecs/safesim']" --output text | grep -q "/ecs/safesim"; then
    echo "Creating CloudWatch log group..."
    $AWS_CMD logs create-log-group --log-group-name "/ecs/safesim" --region $REGION 2>/dev/null || true
fi

# Register task definition
echo "$TASK_DEF_JSON" > /tmp/task-definition.json
TASK_DEF_ARN=$($AWS_CMD ecs register-task-definition \
    --cli-input-json file:///tmp/task-definition.json \
    --region $REGION \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo "✅ Task definition registered: $TASK_DEF_ARN"
rm /tmp/task-definition.json

# Step 6: Check if cluster exists
echo ""
echo "🔍 Step 6: Checking ECS cluster..."
if ! $AWS_CMD ecs describe-clusters --clusters $CLUSTER_NAME --region $REGION --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo "⚠️  Cluster '$CLUSTER_NAME' not found or not active."
    echo "   Creating cluster..."
    $AWS_CMD ecs create-cluster --cluster-name $CLUSTER_NAME --region $REGION
    echo "✅ Created cluster: $CLUSTER_NAME"
else
    echo "✅ Cluster exists: $CLUSTER_NAME"
fi

# Step 7: Create or find VPC configuration
echo ""
echo "🚀 Step 7: Setting up networking..."

VPC_NAME="safesim-vpc"
VPC_CIDR="10.0.0.0/16"

# Check if VPC already exists
VPC_ID=$($AWS_CMD ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=${VPC_NAME}" \
    --region $REGION \
    --query 'Vpcs[0].VpcId' \
    --output text 2>/dev/null || echo "")

if [ -z "$VPC_ID" ] || [ "$VPC_ID" == "None" ]; then
    echo "Creating VPC: $VPC_NAME..."
    
    # Create VPC
    VPC_ID=$($AWS_CMD ec2 create-vpc \
        --cidr-block $VPC_CIDR \
        --region $REGION \
        --query 'Vpc.VpcId' \
        --output text)
    
    # Tag VPC
    $AWS_CMD ec2 create-tags \
        --resources $VPC_ID \
        --tags "Key=Name,Value=${VPC_NAME}" \
        --region $REGION \
        > /dev/null
    
    # Enable DNS hostnames and DNS resolution
    $AWS_CMD ec2 modify-vpc-attribute \
        --vpc-id $VPC_ID \
        --enable-dns-hostnames \
        --region $REGION \
        > /dev/null
    
    $AWS_CMD ec2 modify-vpc-attribute \
        --vpc-id $VPC_ID \
        --enable-dns-support \
        --region $REGION \
        > /dev/null
    
    echo "✅ Created VPC: $VPC_ID"
    
    # Create Internet Gateway
    echo "Creating Internet Gateway..."
    IGW_ID=$($AWS_CMD ec2 create-internet-gateway \
        --region $REGION \
        --query 'InternetGateway.InternetGatewayId' \
        --output text)
    
    $AWS_CMD ec2 create-tags \
        --resources $IGW_ID \
        --tags "Key=Name,Value=${VPC_NAME}-igw" \
        --region $REGION \
        > /dev/null
    
    # Attach Internet Gateway to VPC
    $AWS_CMD ec2 attach-internet-gateway \
        --internet-gateway-id $IGW_ID \
        --vpc-id $VPC_ID \
        --region $REGION \
        > /dev/null
    
    echo "✅ Created and attached Internet Gateway: $IGW_ID"
    
    # Get availability zones
    AZS=($($AWS_CMD ec2 describe-availability-zones \
        --region $REGION \
        --query 'AvailabilityZones[?State==`available`].ZoneName' \
        --output text | head -2))
    
    if [ ${#AZS[@]} -lt 2 ]; then
        echo "⚠️  Warning: Need at least 2 availability zones. Using first available zone twice."
        AZS=(${AZS[0]} ${AZS[0]})
    fi
    
    # Create public subnets
    echo "Creating public subnets..."
    SUBNET_IDS=()
    for i in "${!AZS[@]}"; do
        AZ=${AZS[$i]}
        SUBNET_CIDR="10.0.$((i+1)).0/24"
        SUBNET_NAME="${VPC_NAME}-public-subnet-$((i+1))"
        
        SUBNET_ID=$($AWS_CMD ec2 create-subnet \
            --vpc-id $VPC_ID \
            --cidr-block $SUBNET_CIDR \
            --availability-zone $AZ \
            --region $REGION \
            --query 'Subnet.SubnetId' \
            --output text)
        
        $AWS_CMD ec2 create-tags \
            --resources $SUBNET_ID \
            --tags "Key=Name,Value=${SUBNET_NAME}" \
            --region $REGION \
            > /dev/null
        
        # Enable auto-assign public IP
        $AWS_CMD ec2 modify-subnet-attribute \
            --subnet-id $SUBNET_ID \
            --map-public-ip-on-launch \
            --region $REGION \
            > /dev/null
        
        SUBNET_IDS+=($SUBNET_ID)
        echo "✅ Created subnet: $SUBNET_ID ($AZ)"
    done
    
    # Create route table
    echo "Creating route table..."
    ROUTE_TABLE_ID=$($AWS_CMD ec2 create-route-table \
        --vpc-id $VPC_ID \
        --region $REGION \
        --query 'RouteTable.RouteTableId' \
        --output text)
    
    $AWS_CMD ec2 create-tags \
        --resources $ROUTE_TABLE_ID \
        --tags "Key=Name,Value=${VPC_NAME}-public-rt" \
        --region $REGION \
        > /dev/null
    
    # Add route to Internet Gateway
    $AWS_CMD ec2 create-route \
        --route-table-id $ROUTE_TABLE_ID \
        --destination-cidr-block 0.0.0.0/0 \
        --gateway-id $IGW_ID \
        --region $REGION \
        > /dev/null
    
    # Associate route table with subnets
    for SUBNET_ID in "${SUBNET_IDS[@]}"; do
        $AWS_CMD ec2 associate-route-table \
            --subnet-id $SUBNET_ID \
            --route-table-id $ROUTE_TABLE_ID \
            --region $REGION \
            > /dev/null
    done
    
    echo "✅ Created route table and associated with subnets"
    
    # Convert subnet IDs array to comma-separated string
    SUBNET_IDS=$(IFS=,; echo "${SUBNET_IDS[*]}")
    
else
    echo "✅ VPC already exists: $VPC_ID"
    
    # Get existing public subnets
    SUBNET_IDS=$($AWS_CMD ec2 describe-subnets \
        --filters "Name=vpc-id,Values=${VPC_ID}" "Name=tag:Name,Values=*public*" \
        --region $REGION \
        --query 'Subnets[].SubnetId' \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$SUBNET_IDS" ] || [ "$SUBNET_IDS" == "None" ]; then
        # If no tagged subnets, get any subnets in the VPC
        SUBNET_IDS=$($AWS_CMD ec2 describe-subnets \
            --filters "Name=vpc-id,Values=${VPC_ID}" \
            --region $REGION \
            --query 'Subnets[0:2].SubnetId' \
            --output text 2>/dev/null || echo "")
        
        if [ -z "$SUBNET_IDS" ] || [ "$SUBNET_IDS" == "None" ]; then
            echo "❌ No subnets found in VPC. Please create subnets manually or delete VPC to recreate."
            exit 1
        fi
    fi
    
    # Convert space-separated to comma-separated
    SUBNET_IDS=$(echo $SUBNET_IDS | tr ' ' ',')
    echo "✅ Found subnets: $SUBNET_IDS"
fi

# Create security group for ECS tasks
echo "Creating security group for ECS tasks..."
ECS_SG_NAME="safesim-ecs-sg"
SECURITY_GROUP_ID=$($AWS_CMD ec2 describe-security-groups \
    --filters "Name=group-name,Values=${ECS_SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
    --region $REGION \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || echo "")

if [ -z "$SECURITY_GROUP_ID" ] || [ "$SECURITY_GROUP_ID" == "None" ]; then
    SECURITY_GROUP_ID=$($AWS_CMD ec2 create-security-group \
        --group-name $ECS_SG_NAME \
        --description "Security group for SafeSim ECS tasks" \
        --vpc-id $VPC_ID \
        --region $REGION \
        --query 'GroupId' \
        --output text)
    
    echo "✅ Created ECS security group: $SECURITY_GROUP_ID"
else
    echo "✅ ECS security group already exists: $SECURITY_GROUP_ID"
fi

# Step 8: Create Application Load Balancer
echo ""
echo "⚖️  Step 8: Setting up Application Load Balancer..."

ALB_NAME="safesim-alb"
TARGET_GROUP_NAME="safesim-tg"

# Check if ALB already exists
ALB_ARN=$($AWS_CMD elbv2 describe-load-balancers \
    --region $REGION \
    --query "LoadBalancers[?LoadBalancerName=='${ALB_NAME}'].LoadBalancerArn" \
    --output text 2>/dev/null || echo "")

if [ ! -z "$ALB_ARN" ] && [ "$ALB_ARN" != "None" ]; then
    echo "✅ ALB already exists: $ALB_NAME"
    ALB_DNS=$($AWS_CMD elbv2 describe-load-balancers \
        --load-balancer-arns $ALB_ARN \
        --region $REGION \
        --query 'LoadBalancers[0].DNSName' \
        --output text)
    # Get ALB security group ID
    ALB_SG_ID=$($AWS_CMD elbv2 describe-load-balancers \
        --load-balancer-arns $ALB_ARN \
        --region $REGION \
        --query 'LoadBalancers[0].SecurityGroups[0]' \
        --output text)
else
    echo "Creating Application Load Balancer..."
    
    # Create security group for ALB (allow HTTP/HTTPS from internet)
    ALB_SG_NAME="safesim-alb-sg"
    ALB_SG_ID=$($AWS_CMD ec2 describe-security-groups \
        --filters "Name=group-name,Values=${ALB_SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
        --region $REGION \
        --query 'SecurityGroups[0].GroupId' \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$ALB_SG_ID" ] || [ "$ALB_SG_ID" == "None" ]; then
        echo "Creating security group for ALB..."
        ALB_SG_ID=$($AWS_CMD ec2 create-security-group \
            --group-name $ALB_SG_NAME \
            --description "Security group for SafeSim ALB" \
            --vpc-id $VPC_ID \
            --region $REGION \
            --query 'GroupId' \
            --output text)
        
        # Allow HTTP and HTTPS from anywhere
        $AWS_CMD ec2 authorize-security-group-ingress \
            --group-id $ALB_SG_ID \
            --protocol tcp \
            --port 80 \
            --cidr 0.0.0.0/0 \
            --region $REGION \
            > /dev/null 2>&1 || true
        
        $AWS_CMD ec2 authorize-security-group-ingress \
            --group-id $ALB_SG_ID \
            --protocol tcp \
            --port 443 \
            --cidr 0.0.0.0/0 \
            --region $REGION \
            > /dev/null 2>&1 || true
        
        echo "✅ Created ALB security group: $ALB_SG_ID"
    else
        echo "✅ ALB security group exists: $ALB_SG_ID"
    fi
    
    # Convert subnet IDs to array format for AWS CLI
    SUBNET_ARRAY=$(echo $SUBNET_IDS | tr ',' ' ')
    
    # Create ALB
    ALB_ARN=$($AWS_CMD elbv2 create-load-balancer \
        --name $ALB_NAME \
        --subnets $SUBNET_ARRAY \
        --security-groups $ALB_SG_ID \
        --scheme internet-facing \
        --type application \
        --ip-address-type ipv4 \
        --region $REGION \
        --query 'LoadBalancers[0].LoadBalancerArn' \
        --output text)
    
    echo "✅ Created ALB: $ALB_ARN"
    
    # Wait for ALB to be active
    echo "⏳ Waiting for ALB to be active..."
    $AWS_CMD elbv2 wait load-balancer-available \
        --load-balancer-arns $ALB_ARN \
        --region $REGION
    
    ALB_DNS=$($AWS_CMD elbv2 describe-load-balancers \
        --load-balancer-arns $ALB_ARN \
        --region $REGION \
        --query 'LoadBalancers[0].DNSName' \
        --output text)
fi

# Create target group
TARGET_GROUP_ARN=$($AWS_CMD elbv2 describe-target-groups \
    --region $REGION \
    --query "TargetGroups[?TargetGroupName=='${TARGET_GROUP_NAME}'].TargetGroupArn" \
    --output text 2>/dev/null || echo "")

if [ ! -z "$TARGET_GROUP_ARN" ] && [ "$TARGET_GROUP_ARN" != "None" ]; then
    echo "✅ Target group already exists: $TARGET_GROUP_NAME"
else
    echo "Creating target group..."
    TARGET_GROUP_ARN=$($AWS_CMD elbv2 create-target-group \
        --name $TARGET_GROUP_NAME \
        --protocol HTTP \
        --port 8501 \
        --vpc-id $VPC_ID \
        --target-type ip \
        --health-check-protocol HTTP \
        --health-check-path /_stcore/health \
        --health-check-interval-seconds 30 \
        --health-check-timeout-seconds 5 \
        --healthy-threshold-count 2 \
        --unhealthy-threshold-count 3 \
        --region $REGION \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text)
    
    echo "✅ Created target group: $TARGET_GROUP_ARN"
fi

# Create listener if it doesn't exist
LISTENER_EXISTS=$($AWS_CMD elbv2 describe-listeners \
    --load-balancer-arn $ALB_ARN \
    --region $REGION \
    --query 'Listeners[0].ListenerArn' \
    --output text 2>/dev/null || echo "")

if [ -z "$LISTENER_EXISTS" ] || [ "$LISTENER_EXISTS" == "None" ]; then
    echo "Creating ALB listener..."
    $AWS_CMD elbv2 create-listener \
        --load-balancer-arn $ALB_ARN \
        --protocol HTTP \
        --port 80 \
        --default-actions Type=forward,TargetGroupArn=$TARGET_GROUP_ARN \
        --region $REGION \
        > /dev/null
    echo "✅ Created ALB listener"
else
    echo "✅ ALB listener already exists"
fi

# Update ECS security group to allow traffic from ALB
if [ ! -z "$ALB_SG_ID" ] && [ "$ALB_SG_ID" != "None" ]; then
    echo "Updating ECS security group to allow traffic from ALB..."
    $AWS_CMD ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 8501 \
        --source-group $ALB_SG_ID \
        --region $REGION \
        > /dev/null 2>&1 || echo "   (Rule may already exist)"
fi

# Step 9: Create or update ECS service with load balancer
echo ""
echo "🚀 Step 9: Creating/updating ECS service with load balancer..."

# Check if service exists
SERVICE_EXISTS=$($AWS_CMD ecs describe-services \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --region $REGION \
    --query 'services[0].status' \
    --output text 2>/dev/null || echo "")

if [ ! -z "$SERVICE_EXISTS" ] && [ "$SERVICE_EXISTS" != "None" ] && [ "$SERVICE_EXISTS" != "INACTIVE" ]; then
    echo "Updating existing service..."
    $AWS_CMD ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --task-definition $TASK_DEF_ARN \
        --load-balancers targetGroupArn=$TARGET_GROUP_ARN,containerName=safesim,containerPort=8501 \
        --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SECURITY_GROUP_ID],assignPublicIp=ENABLED}" \
        --region $REGION \
        --force-new-deployment \
        > /dev/null
    echo "✅ Service update initiated"
else
    echo "Creating new service with load balancer..."
    $AWS_CMD ecs create-service \
        --cluster $CLUSTER_NAME \
        --service-name $SERVICE_NAME \
        --task-definition $TASK_DEF_ARN \
        --desired-count 1 \
        --launch-type FARGATE \
        --load-balancers targetGroupArn=$TARGET_GROUP_ARN,containerName=safesim,containerPort=8501 \
        --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SECURITY_GROUP_ID],assignPublicIp=ENABLED}" \
        --region $REGION \
        > /dev/null
    echo "✅ Service created: $SERVICE_NAME"
fi

echo ""
echo "⏳ Waiting for service to stabilize..."
sleep 15

# Step 10: Setup API Gateway
echo ""
echo "🌐 Step 10: Setting up API Gateway..."

ALB_URL="http://${ALB_DNS}"

# Check if API Gateway already exists
EXISTING_API=$($AWS_CMD apigatewayv2 get-apis \
    --region $REGION \
    --query "Items[?Name=='safesim-api'].ApiId" \
    --output text 2>/dev/null || echo "")

if [ ! -z "$EXISTING_API" ] && [ "$EXISTING_API" != "None" ]; then
    echo "⚠️  API Gateway already exists. Updating integration..."
    API_ID=$EXISTING_API
    
    # Get existing integration
    INTEGRATION_ID=$($AWS_CMD apigatewayv2 get-integrations \
        --api-id $API_ID \
        --region $REGION \
        --query 'Items[0].IntegrationId' \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$INTEGRATION_ID" ] && [ "$INTEGRATION_ID" != "None" ]; then
        # Update existing integration
        $AWS_CMD apigatewayv2 update-integration \
            --api-id $API_ID \
            --integration-id $INTEGRATION_ID \
            --integration-uri "$ALB_URL" \
            --region $REGION \
            > /dev/null
        echo "✅ Updated API Gateway integration"
    else
        # Create new integration
        INTEGRATION_ID=$($AWS_CMD apigatewayv2 create-integration \
            --api-id $API_ID \
            --integration-type HTTP_PROXY \
            --integration-uri "$ALB_URL" \
            --integration-method ANY \
            --payload-format-version "1.0" \
            --connection-type INTERNET \
            --timeout-in-millis 30000 \
            --region $REGION \
            --query 'IntegrationId' \
            --output text)
        
        # Create default route
        $AWS_CMD apigatewayv2 create-route \
            --api-id $API_ID \
            --route-key '$default' \
            --target "integrations/$INTEGRATION_ID" \
            --region $REGION \
            > /dev/null 2>&1 || true
        
        echo "✅ Created new integration"
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
        --integration-uri "$ALB_URL" \
        --integration-method ANY \
        --payload-format-version "1.0" \
        --connection-type INTERNET \
        --timeout-in-millis 30000 \
        --region $REGION \
        --query 'IntegrationId' \
        --output text)
    
    echo "✅ Created integration: $INTEGRATION_ID"
    
    # Create default route
    $AWS_CMD apigatewayv2 create-route \
        --api-id $API_ID \
        --route-key '$default' \
        --target "integrations/$INTEGRATION_ID" \
        --region $REGION \
        > /dev/null
    
    # Create health check route
    $AWS_CMD apigatewayv2 create-route \
        --api-id $API_ID \
        --route-key 'GET /_stcore/health' \
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

# Get service status
SERVICE_STATUS=$($AWS_CMD ecs describe-services \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --region $REGION \
    --query 'services[0].status' \
    --output text 2>/dev/null || echo "UNKNOWN")

echo ""
echo "✅ Deployment complete!"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🎉 SafeSim Streamlit is now deployed on ECS with API Gateway!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📍 Service Information:"
echo "   Cluster: $CLUSTER_NAME"
echo "   Service: $SERVICE_NAME"
echo "   Status: $SERVICE_STATUS"
echo "   Task Definition: $TASK_DEF_ARN"
echo ""
echo "🌐 Access URLs:"
echo ""
echo "   🎯 API Gateway (Primary - Use This!):"
echo "      $API_ENDPOINT"
echo ""
echo "   ⚖️  Application Load Balancer:"
echo "      $ALB_URL"
echo ""
echo "📋 Useful commands:"
echo "   View logs: $AWS_CMD logs tail /ecs/safesim --follow --region $REGION"
echo "   Service status: $AWS_CMD ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION"
echo "   Test health: curl $API_ENDPOINT/_stcore/health"
echo ""
echo "═══════════════════════════════════════════════════════════════"
