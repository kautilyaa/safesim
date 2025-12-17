#!/bin/bash
# Cleanup script to delete all AWS resources created by deploy-aws.sh
# Usage: ./scripts/cleanup-aws.sh [--profile PROFILE] [--region REGION] [--service-name NAME] [--delete-iam]

# Don't exit on error - we want to continue even if some resources don't exist
set +e

# Default values
REGION="us-east-1"
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
        --service-name)
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
            echo "  --service-name NAME   App Runner service name (default: safesim-service)"
            echo "  --delete-iam          Also delete IAM role (default: false, keeps IAM role)"
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

echo "🗑️  SafeSim AWS Resource Cleanup"
echo "Region: $REGION"
echo "Service Name: $SERVICE_NAME"
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
echo "   - App Runner service: $SERVICE_NAME"
echo "   - ECR repository: $REPO_NAME (and all images)"
if [ "$DELETE_IAM" = true ]; then
    echo "   - IAM role: AppRunnerECRAccessRole"
else
    echo "   - IAM role: AppRunnerECRAccessRole (will be kept)"
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

# Step 2: Delete App Runner service
echo "🚀 Step 2: Deleting App Runner service..."
SERVICE_ARN_PREFIX="arn:aws:apprunner:${REGION}:${ACCOUNT_ID}:service/${SERVICE_NAME}"
if $AWS_CMD apprunner describe-service --service-arn "$SERVICE_ARN_PREFIX" --region $REGION &> /dev/null 2>&1; then
    echo "   Found App Runner service: $SERVICE_NAME"
    
    # Get current service status
    SERVICE_STATUS=$($AWS_CMD apprunner describe-service \
        --service-arn "$SERVICE_ARN_PREFIX" \
        --region $REGION \
        --query 'Service.Status' \
        --output text 2>/dev/null || echo "")
    
    if [ "$SERVICE_STATUS" == "OPERATION_IN_PROGRESS" ]; then
        echo "   ⏳ Service is currently updating. Waiting for it to finish..."
        MAX_WAIT=600
        ELAPSED=0
        while [ $ELAPSED -lt $MAX_WAIT ]; do
            SERVICE_STATUS=$($AWS_CMD apprunner describe-service \
                --service-arn "$SERVICE_ARN_PREFIX" \
                --region $REGION \
                --query 'Service.Status' \
                --output text 2>/dev/null || echo "")
            
            if [ "$SERVICE_STATUS" == "RUNNING" ] || [ "$SERVICE_STATUS" == "OPERATION_SUCCESS" ]; then
                echo "   ✅ Service is now in stable state"
                break
            fi
            
            echo "   Still waiting... (${ELAPSED}s elapsed, status: $SERVICE_STATUS)"
            sleep 10
            ELAPSED=$((ELAPSED + 10))
        done
    fi
    
    echo "   Deleting App Runner service..."
    $AWS_CMD apprunner delete-service \
        --service-arn "$SERVICE_ARN_PREFIX" \
        --region $REGION \
        > /dev/null 2>&1 || true
    
    echo "   ⏳ Waiting for service deletion to complete..."
    # Wait for deletion (App Runner doesn't have a wait command for deletion, so we'll poll)
    MAX_WAIT=300
    ELAPSED=0
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        if ! $AWS_CMD apprunner describe-service --service-arn "$SERVICE_ARN_PREFIX" --region $REGION &> /dev/null 2>&1; then
            echo "✅ App Runner service deleted"
            break
        fi
        echo "   Still deleting... (${ELAPSED}s elapsed)"
        sleep 10
        ELAPSED=$((ELAPSED + 10))
    done
    
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo "⚠️  Service deletion is taking longer than expected. It may still be deleting."
    fi
else
    echo "⚠️  No App Runner service found"
fi
echo ""

# Step 3: Delete ECR repository and images
echo "📦 Step 3: Deleting ECR repository..."
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

# Step 4: Delete IAM role (optional)
if [ "$DELETE_IAM" = true ]; then
    echo "🔑 Step 4: Deleting IAM role..."
    ROLE_NAME="AppRunnerECRAccessRole"
    ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
    
    if $AWS_CMD iam get-role --role-name "$ROLE_NAME" &> /dev/null 2>&1; then
        echo "   Found IAM role: $ROLE_NAME"
        
        # Detach policies
        echo "   Detaching policies..."
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
        echo "   Deleting IAM role..."
        $AWS_CMD iam delete-role \
            --role-name "$ROLE_NAME" \
            > /dev/null 2>&1 || true
        echo "✅ IAM role deleted"
    else
        echo "⚠️  No IAM role found"
    fi
    echo ""
else
    echo "🔑 Step 4: Skipping IAM role deletion (use --delete-iam to delete)"
    echo ""
fi

echo "═══════════════════════════════════════════════════════════════"
echo "✅ Cleanup complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "All resources have been deleted (or were not found)."
if [ "$DELETE_IAM" = false ]; then
    echo ""
    echo "Note: IAM role 'AppRunnerECRAccessRole' was kept."
    echo "      To delete it, run: $0 --delete-iam [other options]"
fi

