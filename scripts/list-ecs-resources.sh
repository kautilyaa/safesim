#!/bin/bash
# List ECS resources to find service names
# Usage: ./scripts/list-ecs-resources.sh [--profile PROFILE] [--region REGION]

set -e

REGION="us-east-1"
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

echo "🔍 Listing ECS Resources"
echo "Region: $REGION"
echo ""

# List clusters
echo "═══════════════════════════════════════════════════════════════"
echo "📦 ECS Clusters"
echo "═══════════════════════════════════════════════════════════════"
CLUSTERS=$($AWS_CMD ecs list-clusters --region $REGION --query 'clusterArns[]' --output text 2>/dev/null || echo "")

if [ -z "$CLUSTERS" ] || [ "$CLUSTERS" == "None" ]; then
    echo "   No clusters found"
else
    for CLUSTER_ARN in $CLUSTERS; do
        CLUSTER_NAME=$(echo $CLUSTER_ARN | awk -F'/' '{print $NF}')
        echo "   - $CLUSTER_NAME"
        
        # List services in this cluster
        SERVICES=$($AWS_CMD ecs list-services --cluster $CLUSTER_NAME --region $REGION --query 'serviceArns[]' --output text 2>/dev/null || echo "")
        if [ ! -z "$SERVICES" ] && [ "$SERVICES" != "None" ]; then
            echo "     Services:"
            for SERVICE_ARN in $SERVICES; do
                SERVICE_NAME=$(echo $SERVICE_ARN | awk -F'/' '{print $NF}')
                SERVICE_STATUS=$($AWS_CMD ecs describe-services \
                    --cluster $CLUSTER_NAME \
                    --services $SERVICE_NAME \
                    --region $REGION \
                    --query 'services[0].status' \
                    --output text 2>/dev/null || echo "UNKNOWN")
                echo "       - $SERVICE_NAME (Status: $SERVICE_STATUS)"
            done
        else
            echo "     (No services)"
        fi
        echo ""
    done
fi

# List ALBs
echo "═══════════════════════════════════════════════════════════════"
echo "⚖️  Application Load Balancers"
echo "═══════════════════════════════════════════════════════════════"
ALBS=$($AWS_CMD elbv2 describe-load-balancers --region $REGION --query 'LoadBalancers[].{Name:LoadBalancerName,DNS:DNSName,State:State.Code}' --output text 2>/dev/null || echo "")

if [ -z "$ALBS" ] || [ "$ALBS" == "None" ]; then
    echo "   No load balancers found"
else
    echo "$ALBS" | while read -r line; do
        if [ ! -z "$line" ]; then
            echo "   $line"
        fi
    done
fi
echo ""

# List API Gateways
echo "═══════════════════════════════════════════════════════════════"
echo "🌐 API Gateways"
echo "═══════════════════════════════════════════════════════════════"
APIS=$($AWS_CMD apigatewayv2 get-apis --region $REGION --query 'Items[].{Name:Name,Id:ApiId}' --output text 2>/dev/null || echo "")

if [ -z "$APIS" ] || [ "$APIS" == "None" ]; then
    echo "   No API Gateways found"
else
    echo "$APIS" | while read -r line; do
        if [ ! -z "$line" ]; then
            echo "   $line"
        fi
    done
fi
echo ""

echo "💡 To troubleshoot a specific service, run:"
echo "   ./scripts/troubleshoot-ecs.sh --profile $AWS_PROFILE --region $REGION --cluster <cluster-name> --service <service-name>"
