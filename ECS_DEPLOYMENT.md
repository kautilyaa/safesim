# ECS Deployment Guide - Streamlit Only with API Gateway

Simple deployment of SafeSim Streamlit app on AWS ECS Fargate with API Gateway for easy access.

## Architecture

```
Internet → API Gateway → Application Load Balancer → ECS Fargate (Streamlit)
```

**Benefits:**
- ✅ Fixed API Gateway URL (never changes)
- ✅ Automatic load balancing
- ✅ Health checks and auto-recovery
- ✅ Built-in DDoS protection via API Gateway
- ✅ CloudWatch monitoring

## Prerequisites

1. **AWS CLI** installed and configured
2. **Docker** installed
3. **jq** installed (`brew install jq` on macOS, `apt-get install jq` on Ubuntu)
4. **IAM Roles** (must be created manually):
   - `ecsTaskExecutionRole` (for pulling images from ECR)
   - `ecsTaskRole` (for task execution)

**Note:** VPC, subnets, security groups, and networking will be created automatically by the script!

## Quick Deploy

```bash
# 1. Set up environment variables (optional)
echo "OPENAI_API_KEY=your-key" > .env
echo "ANTHROPIC_API_KEY=your-key" >> .env

# 2. Run deployment script - that's it!
./scripts/deploy-ecs.sh --region us-east-1

# The script will automatically:
# - Create VPC with public subnets
# - Create Internet Gateway and route tables
# - Create security groups
# - Build and push Docker image
# - Deploy to ECS with ALB and API Gateway
```

## What the Script Does

1. ✅ Creates VPC with public subnets (if needed)
2. ✅ Creates Internet Gateway and route tables
3. ✅ Creates security groups for ECS and ALB
4. ✅ Creates ECR repository (if needed)
5. ✅ Builds Docker image
6. ✅ Pushes image to ECR
7. ✅ Creates/updates ECS task definition
8. ✅ Creates ECS cluster (if needed)
9. ✅ Creates Application Load Balancer
10. ✅ Creates target group and registers ECS service
11. ✅ Creates API Gateway HTTP API
12. ✅ Connects API Gateway to ALB
13. ✅ Outputs your fixed API Gateway URL

## Accessing Your Application

### Primary: API Gateway URL (Use This!)

The script outputs a fixed API Gateway URL that never changes:

```
https://<api-id>.execute-api.<region>.amazonaws.com/prod
```

**This is your permanent URL** - bookmark it! It will work even if ECS tasks restart.

### Alternative: Application Load Balancer

The ALB URL is also provided, but the API Gateway URL is recommended for:
- Fixed endpoint
- Built-in throttling and monitoring
- Easier custom domain setup

## Environment Variables

The script automatically loads environment variables from `.env` file:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Or pass them directly to the task definition via AWS Console.

## Monitoring

View logs in CloudWatch:

```bash
aws logs tail /ecs/safesim --follow --region us-east-1
```

## Updating Deployment

Simply run the script again - it will:
- Build new Docker image
- Push to ECR
- Update task definition
- Force new deployment of service

```bash
./scripts/deploy-ecs.sh --region us-east-1
```

## Cost Estimate

- **ECS Fargate**: ~$0.04/vCPU-hour + $0.004/GB-hour
- **1 vCPU, 2GB RAM**: ~$0.048/hour (~$35/month)
- **Application Load Balancer**: ~$0.0225/hour (~$16/month)
- **API Gateway**: $3.50 per million requests (first million free)
- **ECR**: Free (first 500MB/month)
- **CloudWatch Logs**: First 5GB/month free

**Total**: ~$50-55/month for minimal usage (24/7)

## Troubleshooting

### Service won't start
- Check CloudWatch logs: `aws logs tail /ecs/safesim --follow`
- Verify security group allows inbound port 8501
- Check task definition has correct IAM roles

### Can't access application
- Ensure subnet has `assignPublicIp=ENABLED`
- Verify security group allows inbound from your IP
- Check task is running: `aws ecs describe-services --cluster safesim-cluster --services safesim-service`

### Image pull errors
- Verify ECR repository exists
- Check `ecsTaskExecutionRole` has ECR permissions
- Ensure image tag matches task definition

## Cleanup

```bash
# Delete service
aws ecs update-service \
  --cluster safesim-cluster \
  --service safesim-service \
  --desired-count 0 \
  --region us-east-1

aws ecs delete-service \
  --cluster safesim-cluster \
  --service safesim-service \
  --region us-east-1

# Delete cluster (optional)
aws ecs delete-cluster --cluster safesim-cluster --region us-east-1

# Delete ECR images (optional)
aws ecr batch-delete-image \
  --repository-name safesim \
  --image-ids imageTag=latest \
  --region us-east-1
```
