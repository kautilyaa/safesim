#!/bin/bash
# Cleanup script to delete all AWS resources created by deploy-ecs.sh
# Usage: ./scripts/cleanup-ecs.sh [--profile PROFILE] [--region REGION] [--cluster CLUSTER] [--service SERVICE] [--delete-iam]

# Don't exit on error - we want to continue even if some resources don't exist
set +e

# Default values
REGION="us-east-1"
CLUSTER_NAME="safesim-cluster"
SERVICE_NAME="safesim-service"
REPO_NAME="safesim"
AWS_PROFILE=""
DELETE_IAM=false
SKIP_CONFIRM=false

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
        --delete-iam)
            DELETE_IAM=true
            shift
            ;;
        --yes|-y)
            SKIP_CONFIRM=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --profile PROFILE     AWS profile to use (default: default)"
            echo "  --region REGION       AWS region (default: us-east-1)"
            echo "  --cluster CLUSTER     ECS cluster name (default: safesim-cluster)"
            echo "  --service SERVICE     ECS service name (default: safesim-service)"
            echo "  --delete-iam          Also delete IAM roles (default: false)"
            echo "  --yes, -y             Skip confirmation prompt"
            echo "  -h, --help           Show this help message"
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

echo "🗑️  SafeSim ECS Resource Cleanup"
echo "Region: $REGION"
echo "Cluster: $CLUSTER_NAME"
echo "Service: $SERVICE_NAME"
echo ""

# Check prerequisites
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first."
    exit 1
fi

# Get AWS account ID
echo "📋 Getting AWS account information..."
ACCOUNT_ID=$($AWS_CMD sts get-caller-identity --query Account --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ Failed to get AWS account ID. Please check your AWS credentials."
    exit 1
fi
echo "✅ AWS Account ID: $ACCOUNT_ID"
echo ""

# Confirmation prompt
echo "⚠️  WARNING: This will delete the following resources:"
echo "   - API Gateway (HTTP API)"
echo "   - Application Load Balancer: safesim-alb"
echo "   - Target Group: safesim-tg"
echo "   - ECS Service: $SERVICE_NAME"
echo "   - ECS Cluster: $CLUSTER_NAME (if empty)"
echo "   - ECR repository: $REPO_NAME (and all images)"
echo "   - CloudWatch Log Group: /ecs/safesim"
if [ "$DELETE_IAM" = true ]; then
    echo "   - IAM roles: ecsTaskExecutionRole, ecsTaskRole"
else
    echo "   - IAM roles: ecsTaskExecutionRole, ecsTaskRole (will be kept)"
fi
echo ""

if [ "$SKIP_CONFIRM" = false ]; then
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "❌ Cleanup cancelled."
        exit 0
    fi
else
    echo "⏭️  Skipping confirmation (--yes flag provided)"
fi
echo ""

# Step 1: Delete API Gateway
echo "🌐 Step 1: Deleting API Gateway..."
API_ID=$($AWS_CMD apigatewayv2 get-apis \
    --region $REGION \
    --query "Items[?Name=='safesim-api'].ApiId" \
    --output text 2>/dev/null || echo "")

if [ ! -z "$API_ID" ] && [ "$API_ID" != "None" ]; then
    echo "   Found API Gateway: $API_ID"
    
    # Delete all stages first
    STAGES=$($AWS_CMD apigatewayv2 get-stages \
        --api-id $API_ID \
        --region $REGION \
        --query 'Items[].StageName' \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$STAGES" ]; then
        for STAGE in $STAGES; do
            echo "   Deleting stage: $STAGE"
            $AWS_CMD apigatewayv2 delete-stage \
                --api-id $API_ID \
                --stage-name "$STAGE" \
                --region $REGION \
                2>/dev/null || true
        done
    fi
    
    # Delete the API
    echo "   Deleting API Gateway..."
    $AWS_CMD apigatewayv2 delete-api \
        --api-id $API_ID \
        --region $REGION \
        > /dev/null 2>&1 || true
    echo "✅ API Gateway deleted"
else
    echo "⚠️  No API Gateway found"
fi
echo ""

# Step 2: Delete ECS Service
echo "🚀 Step 2: Deleting ECS service..."
SERVICE_EXISTS=$($AWS_CMD ecs describe-services \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --region $REGION \
    --query 'services[0].status' \
    --output text 2>/dev/null || echo "")

if [ ! -z "$SERVICE_EXISTS" ] && [ "$SERVICE_EXISTS" != "None" ] && [ "$SERVICE_EXISTS" != "INACTIVE" ]; then
    echo "   Found ECS service: $SERVICE_NAME"
    
    # Scale down to 0 tasks first
    echo "   Scaling service down to 0 tasks..."
    $AWS_CMD ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --desired-count 0 \
        --region $REGION \
        > /dev/null 2>&1 || true
    
    # Wait a bit for tasks to stop
    echo "   ⏳ Waiting for tasks to stop..."
    sleep 10
    
    # Delete the service
    echo "   Deleting ECS service..."
    $AWS_CMD ecs delete-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --force \
        --region $REGION \
        > /dev/null 2>&1 || true
    
    echo "   ⏳ Waiting for service deletion..."
    MAX_WAIT=300
    ELAPSED=0
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        SERVICE_STATUS=$($AWS_CMD ecs describe-services \
            --cluster $CLUSTER_NAME \
            --services $SERVICE_NAME \
            --region $REGION \
            --query 'services[0].status' \
            --output text 2>/dev/null || echo "INACTIVE")
        
        if [ "$SERVICE_STATUS" == "INACTIVE" ] || [ -z "$SERVICE_STATUS" ] || [ "$SERVICE_STATUS" == "None" ]; then
            echo "✅ ECS service deleted"
            break
        fi
        echo "   Still deleting... (${ELAPSED}s elapsed)"
        sleep 10
        ELAPSED=$((ELAPSED + 10))
    done
else
    echo "⚠️  No ECS service found"
fi
echo ""

# Step 3: Delete Application Load Balancer
echo "⚖️  Step 3: Deleting Application Load Balancer..."
ALB_NAME="safesim-alb"
ALB_ARN=$($AWS_CMD elbv2 describe-load-balancers \
    --region $REGION \
    --query "LoadBalancers[?LoadBalancerName=='${ALB_NAME}'].LoadBalancerArn" \
    --output text 2>/dev/null || echo "")

if [ ! -z "$ALB_ARN" ] && [ "$ALB_ARN" != "None" ]; then
    echo "   Found ALB: $ALB_NAME"
    
    # Delete listeners first
    LISTENERS=$($AWS_CMD elbv2 describe-listeners \
        --load-balancer-arn $ALB_ARN \
        --region $REGION \
        --query 'Listeners[].ListenerArn' \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$LISTENERS" ]; then
        for LISTENER_ARN in $LISTENERS; do
            echo "   Deleting listener: $LISTENER_ARN"
            $AWS_CMD elbv2 delete-listener \
                --listener-arn $LISTENER_ARN \
                --region $REGION \
                > /dev/null 2>&1 || true
        done
    fi
    
    # Delete target group
    TARGET_GROUP_NAME="safesim-tg"
    TARGET_GROUP_ARN=$($AWS_CMD elbv2 describe-target-groups \
        --region $REGION \
        --query "TargetGroups[?TargetGroupName=='${TARGET_GROUP_NAME}'].TargetGroupArn" \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$TARGET_GROUP_ARN" ] && [ "$TARGET_GROUP_ARN" != "None" ]; then
        echo "   Deleting target group: $TARGET_GROUP_NAME"
        $AWS_CMD elbv2 delete-target-group \
            --target-group-arn $TARGET_GROUP_ARN \
            --region $REGION \
            > /dev/null 2>&1 || true
        echo "   ✅ Target group deleted"
    fi
    
    # Delete the load balancer
    echo "   Deleting ALB..."
    $AWS_CMD elbv2 delete-load-balancer \
        --load-balancer-arn $ALB_ARN \
        --region $REGION \
        > /dev/null 2>&1 || true
    
    echo "   ⏳ Waiting for ALB deletion..."
    $AWS_CMD elbv2 wait load-balancers-deleted \
        --load-balancer-arns $ALB_ARN \
        --region $REGION \
        2>/dev/null || true
    echo "✅ ALB deleted"
else
    echo "⚠️  No ALB found"
fi
echo ""

# Step 4: Delete ALB Security Group
echo "🔒 Step 4: Deleting ALB security group..."
ALB_SG_NAME="safesim-alb-sg"
VPC_ID=$($AWS_CMD ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=*" \
    --region $REGION \
    --query 'Vpcs[0].VpcId' \
    --output text 2>/dev/null || echo "")

if [ ! -z "$VPC_ID" ] && [ "$VPC_ID" != "None" ]; then
    ALB_SG_ID=$($AWS_CMD ec2 describe-security-groups \
        --filters "Name=group-name,Values=${ALB_SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
        --region $REGION \
        --query 'SecurityGroups[0].GroupId' \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$ALB_SG_ID" ] && [ "$ALB_SG_ID" != "None" ]; then
        echo "   Found ALB security group: $ALB_SG_ID"
        $AWS_CMD ec2 delete-security-group \
            --group-id $ALB_SG_ID \
            --region $REGION \
            > /dev/null 2>&1 || true
        echo "✅ ALB security group deleted"
    else
        echo "⚠️  No ALB security group found"
    fi
else
    echo "⚠️  Could not determine VPC ID, skipping ALB security group deletion"
fi
echo ""

# Step 5: Delete ECS Cluster (if empty)
echo "📦 Step 5: Checking ECS cluster..."
CLUSTER_EXISTS=$($AWS_CMD ecs describe-clusters \
    --clusters $CLUSTER_NAME \
    --region $REGION \
    --query 'clusters[0].status' \
    --output text 2>/dev/null || echo "")

if [ ! -z "$CLUSTER_EXISTS" ] && [ "$CLUSTER_EXISTS" != "None" ]; then
    # Check if cluster has any services
    REMAINING_SERVICES=$($AWS_CMD ecs list-services \
        --cluster $CLUSTER_NAME \
        --region $REGION \
        --query 'serviceArns' \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$REMAINING_SERVICES" ] || [ "$REMAINING_SERVICES" == "None" ]; then
        echo "   Cluster is empty, deleting..."
        $AWS_CMD ecs delete-cluster \
            --cluster $CLUSTER_NAME \
            --region $REGION \
            > /dev/null 2>&1 || true
        echo "✅ ECS cluster deleted"
    else
        echo "⚠️  Cluster still has services, keeping it"
    fi
else
    echo "⚠️  No ECS cluster found"
fi
echo ""

# Step 6: Delete ECR repository and images
echo "📦 Step 6: Deleting ECR repository..."
ECR_REPO_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"
if $AWS_CMD ecr describe-repositories --repository-names "$REPO_NAME" --region $REGION &> /dev/null 2>&1; then
    echo "   Found ECR repository: $REPO_NAME"
    
    # List and delete all images
    echo "   Deleting all images..."
    IMAGE_IDS=$($AWS_CMD ecr list-images \
        --repository-name "$REPO_NAME" \
        --region $REGION \
        --query 'imageIds[*]' \
        --output json 2>/dev/null || echo "[]")
    
    if [ "$IMAGE_IDS" != "[]" ] && [ ! -z "$IMAGE_IDS" ]; then
        $AWS_CMD ecr batch-delete-image \
            --repository-name "$REPO_NAME" \
            --image-ids "$IMAGE_IDS" \
            --region $REGION \
            > /dev/null 2>&1 || true
        echo "   ✅ All images deleted"
    fi
    
    # Delete the repository
    echo "   Deleting repository..."
    $AWS_CMD ecr delete-repository \
        --repository-name "$REPO_NAME" \
        --force \
        --region $REGION \
        > /dev/null 2>&1 || true
    echo "✅ ECR repository deleted"
else
    echo "⚠️  No ECR repository found"
fi
echo ""

# Step 7: Delete CloudWatch Log Group
echo "📊 Step 7: Deleting CloudWatch log group..."
LOG_GROUP="/ecs/safesim"
if $AWS_CMD logs describe-log-groups \
    --log-group-name-prefix "$LOG_GROUP" \
    --region $REGION \
    --query "logGroups[?logGroupName=='${LOG_GROUP}'].logGroupName" \
    --output text 2>/dev/null | grep -q "$LOG_GROUP"; then
    echo "   Found log group: $LOG_GROUP"
    $AWS_CMD logs delete-log-group \
        --log-group-name "$LOG_GROUP" \
        --region $REGION \
        > /dev/null 2>&1 || true
    echo "✅ CloudWatch log group deleted"
else
    echo "⚠️  No CloudWatch log group found"
fi
echo ""

# Step 8: Delete IAM roles (optional)
if [ "$DELETE_IAM" = true ]; then
    echo "🔑 Step 8: Deleting IAM roles..."
    
    for ROLE_NAME in "ecsTaskExecutionRole" "ecsTaskRole"; do
        ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
        
        if $AWS_CMD iam get-role --role-name "$ROLE_NAME" &> /dev/null 2>&1; then
            echo "   Found IAM role: $ROLE_NAME"
            
            # Detach policies
            POLICIES=$($AWS_CMD iam list-attached-role-policies \
                --role-name "$ROLE_NAME" \
                --query 'AttachedPolicies[].PolicyArn' \
                --output text 2>/dev/null || echo "")
            
            if [ ! -z "$POLICIES" ]; then
                for POLICY_ARN in $POLICIES; do
                    echo "   Detaching policy: $POLICY_ARN"
                    $AWS_CMD iam detach-role-policy \
                        --role-name "$ROLE_NAME" \
                        --policy-arn "$POLICY_ARN" \
                        2>/dev/null || true
                done
            fi
            
            # Delete inline policies
            INLINE_POLICIES=$($AWS_CMD iam list-role-policies \
                --role-name "$ROLE_NAME" \
                --query 'PolicyNames' \
                --output text 2>/dev/null || echo "")
            
            if [ ! -z "$INLINE_POLICIES" ]; then
                for POLICY_NAME in $INLINE_POLICIES; do
                    echo "   Deleting inline policy: $POLICY_NAME"
                    $AWS_CMD iam delete-role-policy \
                        --role-name "$ROLE_NAME" \
                        --policy-name "$POLICY_NAME" \
                        2>/dev/null || true
                done
            fi
            
            # Delete the role
            echo "   Deleting IAM role: $ROLE_NAME"
            $AWS_CMD iam delete-role \
                --role-name "$ROLE_NAME" \
                > /dev/null 2>&1 || true
            echo "   ✅ IAM role deleted: $ROLE_NAME"
        else
            echo "   ⚠️  No IAM role found: $ROLE_NAME"
        fi
    done
    echo ""
else
    echo "🔑 Step 8: Skipping IAM role deletion (use --delete-iam to delete)"
    echo ""
fi

echo "═══════════════════════════════════════════════════════════════"
echo "✅ Cleanup complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "All ECS resources have been deleted (or were not found)."
if [ "$DELETE_IAM" = false ]; then
    echo ""
    echo "Note: IAM roles were kept."
    echo "      To delete them, run: $0 --delete-iam [other options]"
fi
