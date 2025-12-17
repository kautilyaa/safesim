#!/bin/bash
# Deploy SafeSim to AWS App Runner
# Usage: ./scripts/deploy-apprunner.sh [region] [account-id]

set -e

REGION=${1:-us-east-1}
ACCOUNT_ID=${2:-$(aws sts get-caller-identity --query Account --output text)}
REPO_NAME="safesim"
IMAGE_TAG="latest"

echo "🚀 Deploying SafeSim to AWS App Runner"
echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install it first."
    exit 1
fi

# Login to ECR
echo "📦 Logging into Amazon ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Check if repository exists, create if not
echo "🔍 Checking for ECR repository..."
if ! aws ecr describe-repositories --repository-names $REPO_NAME --region $REGION &> /dev/null; then
    echo "📝 Creating ECR repository..."
    aws ecr create-repository --repository-name $REPO_NAME --region $REGION
else
    echo "✅ Repository already exists"
fi

# Build Docker image
echo "🔨 Building Docker image..."
docker build -t $REPO_NAME:$IMAGE_TAG .

# Tag image
echo "🏷️  Tagging image..."
docker tag $REPO_NAME:$IMAGE_TAG $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG

# Push image
echo "⬆️  Pushing image to ECR..."
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG

echo ""
echo "✅ Image pushed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Go to AWS App Runner console: https://console.aws.amazon.com/apprunner/"
echo "2. Click 'Create service'"
echo "3. Select 'Container registry' → 'Amazon ECR'"
echo "4. Choose repository: $REPO_NAME"
echo "5. Choose image: $IMAGE_TAG"
echo "6. Configure service settings and environment variables"
echo "7. Deploy!"
echo ""
echo "Or use the AWS CLI:"
echo "aws apprunner create-service --cli-input-json file://apprunner-service.json"

