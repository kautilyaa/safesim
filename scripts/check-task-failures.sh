#!/bin/bash
# Check why ECS tasks are failing
# Usage: ./scripts/check-task-failures.sh [--profile PROFILE] [--region REGION] [--cluster CLUSTER] [--service SERVICE]

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
            exit 1
            ;;
    esac
done

AWS_CMD="aws"
if [ ! -z "$AWS_PROFILE" ]; then
    AWS_CMD="aws --profile $AWS_PROFILE"
fi

echo "🔍 Checking Task Failures"
echo ""

# Get stopped tasks
echo "═══════════════════════════════════════════════════════════════"
echo "Stopped Tasks (Last 10)"
echo "═══════════════════════════════════════════════════════════════"

STOPPED_TASKS=$($AWS_CMD ecs list-tasks \
    --cluster $CLUSTER_NAME \
    --service-name $SERVICE_NAME \
    --desired-status STOPPED \
    --region $REGION \
    --max-items 10 \
    --query 'taskArns[]' \
    --output text 2>/dev/null || echo "")

if [ -z "$STOPPED_TASKS" ] || [ "$STOPPED_TASKS" == "None" ]; then
    echo "   No stopped tasks found"
else
    for TASK_ARN in $STOPPED_TASKS; do
        TASK_INFO=$($AWS_CMD ecs describe-tasks \
            --cluster $CLUSTER_NAME \
            --tasks $TASK_ARN \
            --region $REGION 2>/dev/null || echo "")
        
        if [ ! -z "$TASK_INFO" ]; then
            STOPPED_REASON=$(echo "$TASK_INFO" | jq -r '.tasks[0].stoppedReason // "N/A"')
            STOP_CODE=$(echo "$TASK_INFO" | jq -r '.tasks[0].stopCode // "N/A"')
            EXIT_CODE=$(echo "$TASK_INFO" | jq -r '.tasks[0].containers[0].exitCode // "N/A"')
            REASON=$(echo "$TASK_INFO" | jq -r '.tasks[0].containers[0].reason // "N/A"')
            
            echo ""
            echo "   Task: $(echo $TASK_ARN | awk -F'/' '{print $NF}')"
            echo "   Stop Code: $STOP_CODE"
            echo "   Stopped Reason: $STOPPED_REASON"
            
            if [ "$EXIT_CODE" != "null" ] && [ "$EXIT_CODE" != "N/A" ]; then
                echo "   Exit Code: $EXIT_CODE"
                echo "   Reason: $REASON"
            fi
        fi
    done
fi
echo ""

# Check task definition
echo "═══════════════════════════════════════════════════════════════"
echo "Task Definition"
echo "═══════════════════════════════════════════════════════════════"

SERVICE_INFO=$($AWS_CMD ecs describe-services \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --region $REGION 2>/dev/null || echo "")

TASK_DEF_ARN=$(echo "$SERVICE_INFO" | jq -r '.services[0].taskDefinition // "N/A"')

if [ "$TASK_DEF_ARN" != "N/A" ] && [ ! -z "$TASK_DEF_ARN" ]; then
    echo "   Task Definition: $TASK_DEF_ARN"
    
    TASK_DEF=$($AWS_CMD ecs describe-task-definition \
        --task-definition $TASK_DEF_ARN \
        --region $REGION 2>/dev/null || echo "")
    
    if [ ! -z "$TASK_DEF" ]; then
        IMAGE=$(echo "$TASK_DEF" | jq -r '.taskDefinition.containerDefinitions[0].image // "N/A"')
        EXEC_ROLE=$(echo "$TASK_DEF" | jq -r '.taskDefinition.executionRoleArn // "N/A"')
        TASK_ROLE=$(echo "$TASK_DEF" | jq -r '.taskDefinition.taskRoleArn // "N/A"')
        
        echo "   Image: $IMAGE"
        echo "   Execution Role: $EXEC_ROLE"
        echo "   Task Role: $TASK_ROLE"
        
        # Check if roles exist
        echo ""
        echo "   Checking IAM Roles..."
        
        EXEC_ROLE_NAME=$(echo $EXEC_ROLE | awk -F'/' '{print $NF}')
        if $AWS_CMD iam get-role --role-name "$EXEC_ROLE_NAME" &> /dev/null 2>&1; then
            echo "   ✅ Execution role exists: $EXEC_ROLE_NAME"
        else
            echo "   ❌ Execution role NOT found: $EXEC_ROLE_NAME"
            echo "      This is likely causing task failures!"
        fi
        
        TASK_ROLE_NAME=$(echo $TASK_ROLE | awk -F'/' '{print $NF}')
        if $AWS_CMD iam get-role --role-name "$TASK_ROLE_NAME" &> /dev/null 2>&1; then
            echo "   ✅ Task role exists: $TASK_ROLE_NAME"
        else
            echo "   ⚠️  Task role NOT found: $TASK_ROLE_NAME (may be optional)"
        fi
        
        # Check if ECR image exists
        echo ""
        echo "   Checking ECR Image..."
        if [[ "$IMAGE" == *".dkr.ecr."* ]]; then
            REPO_NAME=$(echo $IMAGE | sed 's/.*\/\([^:]*\):.*/\1/')
            IMAGE_TAG=$(echo $IMAGE | sed 's/.*:\(.*\)/\1/')
            ACCOUNT_ID=$(echo $IMAGE | sed 's/\([0-9]*\)\.dkr\.ecr.*/\1/')
            
            if $AWS_CMD ecr describe-images \
                --repository-name "$REPO_NAME" \
                --image-ids imageTag="$IMAGE_TAG" \
                --region $REGION &> /dev/null 2>&1; then
                echo "   ✅ Image exists in ECR: $REPO_NAME:$IMAGE_TAG"
            else
                echo "   ❌ Image NOT found in ECR: $REPO_NAME:$IMAGE_TAG"
                echo "      This is likely causing task failures!"
            fi
        fi
    fi
else
    echo "   ❌ Could not get task definition"
fi
echo ""

# Check service events
echo "═══════════════════════════════════════════════════════════════"
echo "Service Events (Last 10)"
echo "═══════════════════════════════════════════════════════════════"

if [ ! -z "$SERVICE_INFO" ]; then
    echo "$SERVICE_INFO" | jq -r '.services[0].events[0:10] | .[] | "   [\(.createdAt)] \(.message)"' || echo "   No events found"
fi
echo ""

echo "💡 Common fixes:"
echo "   1. If IAM role missing: Create ecsTaskExecutionRole with ECR access"
echo "   2. If image missing: Run deployment script to build and push image"
echo "   3. If task failing: Check stopped task reasons above"
