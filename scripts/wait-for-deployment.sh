#!/bin/bash
# Wait for ECS deployment to complete
# Usage: ./scripts/wait-for-deployment.sh [--profile PROFILE] [--region REGION] [--cluster CLUSTER] [--service SERVICE]

set -e

REGION="us-east-1"
CLUSTER_NAME="safesim-cluster"
SERVICE_NAME="safesim-service"
AWS_PROFILE=""

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
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

AWS_CMD="aws"
if [ ! -z "$AWS_PROFILE" ]; then
    AWS_CMD="aws --profile $AWS_PROFILE"
fi

echo "⏳ Waiting for ECS deployment to complete..."
echo "   Cluster: $CLUSTER_NAME"
echo "   Service: $SERVICE_NAME"
echo ""

MAX_WAIT=900  # 15 minutes
ELAPSED=0
CHECK_INTERVAL=15

while [ $ELAPSED -lt $MAX_WAIT ]; do
    SERVICE_INFO=$($AWS_CMD ecs describe-services \
        --cluster $CLUSTER_NAME \
        --services $SERVICE_NAME \
        --region $REGION 2>/dev/null || echo "")
    
    if [ -z "$SERVICE_INFO" ]; then
        echo "❌ Service not found: $SERVICE_NAME"
        exit 1
    fi
    
    STATUS=$(echo "$SERVICE_INFO" | jq -r '.services[0].status // "UNKNOWN"')
    DESIRED=$(echo "$SERVICE_INFO" | jq -r '.services[0].desiredCount // 0')
    RUNNING=$(echo "$SERVICE_INFO" | jq -r '.services[0].runningCount // 0')
    PENDING=$(echo "$SERVICE_INFO" | jq -r '.services[0].pendingCount // 0')
    DEPLOYMENTS=$(echo "$SERVICE_INFO" | jq -r '.services[0].deployments | length // 0')
    
    echo "[${ELAPSED}s] Status: $STATUS | Desired: $DESIRED | Running: $RUNNING | Pending: $PENDING | Deployments: $DEPLOYMENTS"
    
    # Check if deployment is complete
    if [ "$DEPLOYMENTS" -eq 1 ] && [ "$RUNNING" -ge "$DESIRED" ] && [ "$PENDING" -eq 0 ]; then
        echo ""
        echo "✅ Deployment completed successfully!"
        echo "   Running tasks: $RUNNING/$DESIRED"
        
        # Check target health
        TARGET_GROUP_NAME="safesim-tg"
        TARGET_GROUP_ARN=$($AWS_CMD elbv2 describe-target-groups \
            --region $REGION \
            --query "TargetGroups[?TargetGroupName=='${TARGET_GROUP_NAME}'].TargetGroupArn" \
            --output text 2>/dev/null || echo "")
        
        if [ ! -z "$TARGET_GROUP_ARN" ] && [ "$TARGET_GROUP_ARN" != "None" ]; then
            HEALTHY=$($AWS_CMD elbv2 describe-target-health \
                --target-group-arn $TARGET_GROUP_ARN \
                --region $REGION \
                --query 'length([TargetHealthDescriptions[] | select(.TargetHealth.State == "healthy")])' \
                --output text 2>/dev/null || echo "0")
            
            echo "   Healthy targets: $HEALTHY"
            
            if [ "$HEALTHY" -gt 0 ]; then
                echo ""
                echo "🎉 Service is healthy and ready!"
            else
                echo ""
                echo "⚠️  Service is running but targets are not healthy yet."
                echo "   This may cause 503 errors. Check logs:"
                echo "   $AWS_CMD logs tail /ecs/safesim --follow --region $REGION"
            fi
        fi
        
        exit 0
    fi
    
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

echo ""
echo "⏱️  Timeout waiting for deployment (${MAX_WAIT}s)"
echo "   Check status manually:"
echo "   $AWS_CMD ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION"
exit 1
