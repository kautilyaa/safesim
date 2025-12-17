#!/bin/bash
# Troubleshooting script for ECS deployment
# Usage: ./scripts/troubleshoot-ecs.sh [--profile PROFILE] [--region REGION] [--cluster CLUSTER] [--service SERVICE]

set -e

# Default values
REGION="us-east-1"
CLUSTER_NAME="safesim-cluster"
SERVICE_NAME="safesim-service"
AWS_PROFILE=""

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
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --profile PROFILE     AWS profile to use"
            echo "  --region REGION       AWS region (default: us-east-1)"
            echo "  --cluster CLUSTER     ECS cluster name (default: safesim-cluster)"
            echo "  --service SERVICE     ECS service name (default: safesim-service)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build AWS CLI command prefix
AWS_CMD="aws"
if [ ! -z "$AWS_PROFILE" ]; then
    AWS_CMD="aws --profile $AWS_PROFILE"
fi

echo "🔍 SafeSim ECS Troubleshooting"
echo "Region: $REGION"
echo "Cluster: $CLUSTER_NAME"
echo "Service: $SERVICE_NAME"
echo ""

# 1. Check ECS Service Status
echo "═══════════════════════════════════════════════════════════════"
echo "1️⃣  Checking ECS Service Status"
echo "═══════════════════════════════════════════════════════════════"

SERVICE_INFO=$($AWS_CMD ecs describe-services \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --region $REGION 2>/dev/null || echo "")

if [ -z "$SERVICE_INFO" ]; then
    echo "❌ Service not found: $SERVICE_NAME"
    echo ""
    echo "💡 Trying to find services in cluster..."
    ALL_SERVICES=$($AWS_CMD ecs list-services \
        --cluster $CLUSTER_NAME \
        --region $REGION \
        --query 'serviceArns[]' \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$ALL_SERVICES" ] && [ "$ALL_SERVICES" != "None" ]; then
        echo "   Found services:"
        for SVC_ARN in $ALL_SERVICES; do
            SVC_NAME=$(echo $SVC_ARN | awk -F'/' '{print $NF}')
            echo "   - $SVC_NAME"
        done
        echo ""
        echo "   Run with: --service <service-name>"
    fi
    exit 1
fi

SERVICE_STATUS=$(echo "$SERVICE_INFO" | jq -r '.services[0].status // "UNKNOWN"')
DESIRED_COUNT=$(echo "$SERVICE_INFO" | jq -r '.services[0].desiredCount // 0')
RUNNING_COUNT=$(echo "$SERVICE_INFO" | jq -r '.services[0].runningCount // 0')
PENDING_COUNT=$(echo "$SERVICE_INFO" | jq -r '.services[0].pendingCount // 0')
DEPLOYMENTS=$(echo "$SERVICE_INFO" | jq -r '.services[0].deployments | length // 0')

echo "   Status: $SERVICE_STATUS"
echo "   Desired Tasks: $DESIRED_COUNT"
echo "   Running Tasks: $RUNNING_COUNT"
echo "   Pending Tasks: $PENDING_COUNT"
echo "   Active Deployments: $DEPLOYMENTS"

# Check if deployment is in progress
if [ "$DEPLOYMENTS" -gt 1 ]; then
    echo ""
    echo "   ⚠️  Deployment in progress..."
    echo "$SERVICE_INFO" | jq -r '.services[0].deployments[] | "      Deployment: \(.status) - Desired: \(.desiredCount), Running: \(.runningCount), Pending: \(.pendingCount)"'
    echo ""
    echo "   ⏳ Waiting for deployment to stabilize (this may take a few minutes)..."
    
    MAX_WAIT=600
    ELAPSED=0
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        sleep 10
        ELAPSED=$((ELAPSED + 10))
        
        CURRENT_INFO=$($AWS_CMD ecs describe-services \
            --cluster $CLUSTER_NAME \
            --services $SERVICE_NAME \
            --region $REGION 2>/dev/null || echo "")
        
        CURRENT_DEPLOYMENTS=$(echo "$CURRENT_INFO" | jq -r '.services[0].deployments | length // 0')
        CURRENT_RUNNING=$(echo "$CURRENT_INFO" | jq -r '.services[0].runningCount // 0')
        
        if [ "$CURRENT_DEPLOYMENTS" -eq 1 ] && [ "$CURRENT_RUNNING" -ge "$DESIRED_COUNT" ]; then
            echo "   ✅ Deployment completed!"
            SERVICE_INFO=$CURRENT_INFO
            RUNNING_COUNT=$CURRENT_RUNNING
            break
        fi
        
        echo "   Still deploying... (${ELAPSED}s elapsed, Running: $CURRENT_RUNNING/$DESIRED_COUNT)"
    done
    
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo "   ⚠️  Deployment taking longer than expected"
    fi
fi

if [ "$RUNNING_COUNT" -eq 0 ]; then
    echo ""
    echo "   ⚠️  WARNING: No tasks are running!"
    echo "   This is likely causing the 503 error."
fi
echo ""

# 2. Check Task Status
echo "═══════════════════════════════════════════════════════════════"
echo "2️⃣  Checking Task Status"
echo "═══════════════════════════════════════════════════════════════"

TASK_ARNS=$($AWS_CMD ecs list-tasks \
    --cluster $CLUSTER_NAME \
    --service-name $SERVICE_NAME \
    --region $REGION \
    --query 'taskArns[]' \
    --output text 2>/dev/null || echo "")

if [ -z "$TASK_ARNS" ] || [ "$TASK_ARNS" == "None" ]; then
    echo "   ❌ No tasks found"
else
    for TASK_ARN in $TASK_ARNS; do
        echo "   Task: $TASK_ARN"
        
        TASK_INFO=$($AWS_CMD ecs describe-tasks \
            --cluster $CLUSTER_NAME \
            --tasks $TASK_ARN \
            --region $REGION 2>/dev/null || echo "")
        
        if [ ! -z "$TASK_INFO" ]; then
            TASK_STATUS=$(echo "$TASK_INFO" | jq -r '.tasks[0].lastStatus // "UNKNOWN"')
            HEALTH_STATUS=$(echo "$TASK_INFO" | jq -r '.tasks[0].healthStatus // "UNKNOWN"')
            STOPPED_REASON=$(echo "$TASK_INFO" | jq -r '.tasks[0].stoppedReason // "N/A"')
            
            echo "      Status: $TASK_STATUS"
            echo "      Health: $HEALTH_STATUS"
            
            # Check container status
            CONTAINER_STATUS=$(echo "$TASK_INFO" | jq -r '.tasks[0].containers[0].lastStatus // "UNKNOWN"')
            EXIT_CODE=$(echo "$TASK_INFO" | jq -r '.tasks[0].containers[0].exitCode // "N/A"')
            REASON=$(echo "$TASK_INFO" | jq -r '.tasks[0].containers[0].reason // "N/A"')
            
            echo "      Container Status: $CONTAINER_STATUS"
            
            if [ "$EXIT_CODE" != "null" ] && [ "$EXIT_CODE" != "N/A" ]; then
                echo "      ❌ Container Exit Code: $EXIT_CODE"
                echo "      Reason: $REASON"
            fi
            
            if [ "$TASK_STATUS" == "STOPPED" ]; then
                echo "      ❌ Task Stopped: $STOPPED_REASON"
            fi
        fi
        echo ""
    done
fi
echo ""

# 3. Check Target Group Health
echo "═══════════════════════════════════════════════════════════════"
echo "3️⃣  Checking Target Group Health"
echo "═══════════════════════════════════════════════════════════════"

TARGET_GROUP_NAME="safesim-tg"
TARGET_GROUP_ARN=$($AWS_CMD elbv2 describe-target-groups \
    --region $REGION \
    --query "TargetGroups[?TargetGroupName=='${TARGET_GROUP_NAME}'].TargetGroupArn" \
    --output text 2>/dev/null || echo "")

if [ -z "$TARGET_GROUP_ARN" ] || [ "$TARGET_GROUP_ARN" == "None" ]; then
    echo "   ⚠️  Target group not found: $TARGET_GROUP_NAME"
else
    echo "   Target Group: $TARGET_GROUP_ARN"
    
    HEALTH_INFO=$($AWS_CMD elbv2 describe-target-health \
        --target-group-arn $TARGET_GROUP_ARN \
        --region $REGION 2>/dev/null || echo "")
    
    if [ ! -z "$HEALTH_INFO" ]; then
        HEALTHY_COUNT=$(echo "$HEALTH_INFO" | jq '[.TargetHealthDescriptions[] | select(.TargetHealth.State == "healthy")] | length')
        UNHEALTHY_COUNT=$(echo "$HEALTH_INFO" | jq '[.TargetHealthDescriptions[] | select(.TargetHealth.State == "unhealthy")] | length')
        DRAINING_COUNT=$(echo "$HEALTH_INFO" | jq '[.TargetHealthDescriptions[] | select(.TargetHealth.State == "draining")] | length')
        
        echo "   Healthy Targets: $HEALTHY_COUNT"
        echo "   Unhealthy Targets: $UNHEALTHY_COUNT"
        echo "   Draining Targets: $DRAINING_COUNT"
        
        if [ "$UNHEALTHY_COUNT" -gt 0 ]; then
            echo ""
            echo "   ⚠️  Unhealthy Targets:"
            echo "$HEALTH_INFO" | jq -r '.TargetHealthDescriptions[] | select(.TargetHealth.State == "unhealthy") | "      Target: \(.Target.Id):\(.Target.Port) - Reason: \(.TargetHealth.Reason) - Description: \(.TargetHealth.Description)"'
        fi
        
        if [ "$HEALTHY_COUNT" -eq 0 ] && [ "$UNHEALTHY_COUNT" -gt 0 ]; then
            echo ""
            echo "   ❌ No healthy targets! This is likely causing the 503 error."
        fi
    fi
fi
echo ""

# 4. Check Recent Logs
echo "═══════════════════════════════════════════════════════════════"
echo "4️⃣  Checking Recent CloudWatch Logs"
echo "═══════════════════════════════════════════════════════════════"

LOG_GROUP="/ecs/safesim"
LOG_STREAMS=$($AWS_CMD logs describe-log-streams \
    --log-group-name $LOG_GROUP \
    --order-by LastEventTime \
    --descending \
    --max-items 3 \
    --region $REGION \
    --query 'logStreams[].logStreamName' \
    --output text 2>/dev/null || echo "")

if [ -z "$LOG_STREAMS" ] || [ "$LOG_STREAMS" == "None" ]; then
    echo "   ⚠️  No log streams found. Tasks may not have started yet."
else
    echo "   Recent log streams:"
    for STREAM in $LOG_STREAMS; do
        echo "   - $STREAM"
        echo ""
        echo "   Last 20 lines:"
        $AWS_CMD logs get-log-events \
            --log-group-name $LOG_GROUP \
            --log-stream-name "$STREAM" \
            --limit 20 \
            --region $REGION \
            --query 'events[].message' \
            --output text 2>/dev/null | tail -20 | sed 's/^/      /' || echo "      (No logs)"
        echo ""
    done
fi
echo ""

# 5. Check Security Groups
echo "═══════════════════════════════════════════════════════════════"
echo "5️⃣  Checking Security Groups"
echo "═══════════════════════════════════════════════════════════════"

# Get VPC ID from service
VPC_ID=$(echo "$SERVICE_INFO" | jq -r '.services[0].networkConfiguration.awsvpcConfiguration.subnets[0] // ""' | head -c 8)
if [ ! -z "$VPC_ID" ]; then
    VPC_ID=$($AWS_CMD ec2 describe-subnets \
        --subnet-ids $(echo "$SERVICE_INFO" | jq -r '.services[0].networkConfiguration.awsvpcConfiguration.subnets[0]') \
        --region $REGION \
        --query 'Subnets[0].VpcId' \
        --output text 2>/dev/null || echo "")
fi

if [ ! -z "$VPC_ID" ] && [ "$VPC_ID" != "None" ]; then
    ECS_SG_ID=$(echo "$SERVICE_INFO" | jq -r '.services[0].networkConfiguration.awsvpcConfiguration.securityGroups[0] // ""')
    ALB_SG_NAME="safesim-alb-sg"
    ALB_SG_ID=$($AWS_CMD ec2 describe-security-groups \
        --filters "Name=group-name,Values=${ALB_SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
        --region $REGION \
        --query 'SecurityGroups[0].GroupId' \
        --output text 2>/dev/null || echo "")
    
    echo "   VPC: $VPC_ID"
    echo "   ECS Security Group: $ECS_SG_ID"
    echo "   ALB Security Group: $ALB_SG_ID"
    
    if [ ! -z "$ECS_SG_ID" ] && [ "$ECS_SG_ID" != "None" ]; then
        echo ""
        echo "   ECS Security Group Rules:"
        $AWS_CMD ec2 describe-security-groups \
            --group-ids $ECS_SG_ID \
            --region $REGION \
            --query 'SecurityGroups[0].IpPermissions[]' \
            --output json 2>/dev/null | jq -r '.[] | "      \(.IpProtocol) Port \(.FromPort)-\(.ToPort) from \(.UserIdGroupPairs[0].GroupId // "any")"' || echo "      (Could not retrieve rules)"
    fi
else
    echo "   ⚠️  Could not determine VPC ID"
fi
echo ""

# 6. Recommendations
echo "═══════════════════════════════════════════════════════════════"
echo "6️⃣  Recommendations"
echo "═══════════════════════════════════════════════════════════════"

if [ "$RUNNING_COUNT" -eq 0 ]; then
    echo "   ❌ No tasks running. Check:"
    echo "      1. View full logs: $AWS_CMD logs tail /ecs/safesim --follow --region $REGION"
    echo "      2. Check task definition: $AWS_CMD ecs describe-task-definition --task-definition safesim --region $REGION"
    echo "      3. Verify IAM roles exist: ecsTaskExecutionRole and ecsTaskRole"
    echo "      4. Check if image exists in ECR"
fi

if [ "$UNHEALTHY_COUNT" -gt 0 ]; then
    echo "   ❌ Unhealthy targets detected. Common causes:"
    echo "      1. Container not listening on port 8501"
    echo "      2. Health check failing (check logs above)"
    echo "      3. Security group blocking traffic from ALB"
    echo "      4. Application crashing on startup"
fi

echo ""
echo "   📋 Useful Commands:"
echo "      View logs: $AWS_CMD logs tail /ecs/safesim --follow --region $REGION"
echo "      Service details: $AWS_CMD ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION"
echo "      Restart service: $AWS_CMD ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --force-new-deployment --region $REGION"
echo ""
