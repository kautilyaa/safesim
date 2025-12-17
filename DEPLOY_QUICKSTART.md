# Quick Start: Deploy SafeSim to AWS

Choose your deployment method:

## 🌐 Option 0: API Gateway + Backend (Recommended for Production)

**Best for:** Production deployments, single public endpoint, security, monitoring

```bash
# 1. Deploy backend (App Runner, EC2, or ECS)
./scripts/deploy-apprunner.sh us-east-1

# 2. Setup API Gateway
./scripts/setup-api-gateway.sh <your-backend-url>

# 3. Access via API Gateway endpoint
```

**Cost:** ~$5-35/month (backend) + $0.35/month (API Gateway for 100K requests)

See [API_GATEWAY_DEPLOYMENT.md](./API_GATEWAY_DEPLOYMENT.md) for details.

## 🚀 Option 1: AWS App Runner (Fastest - 5 minutes)

**Best for:** Quick deployment, automatic scaling, managed service

```bash
# 1. Build and push Docker image
./scripts/deploy-apprunner.sh us-east-1

# 2. Update apprunner-service.json with your account ID and API keys
# 3. Create service via AWS Console or CLI:
aws apprunner create-service --cli-input-json file://apprunner-service.json
```

**Cost:** ~$5/month

## 🖥️ Option 2: EC2 Instance (Most Control)

**Best for:** Full control, custom configurations, cost optimization

```bash
# 1. Launch EC2 instance (t3.medium or larger)
# 2. Deploy using script:
./scripts/deploy-ec2.sh <instance-ip> <key-file.pem>

# 3. SSH and run:
ssh -i <key-file.pem> ec2-user@<instance-ip>
cd ~/safesim
streamlit run src/ui/app.py --server.port=8501 --server.address=0.0.0.0
```

**Cost:** ~$30-70/month

## 📦 Option 3: Docker + ECS Fargate

**Best for:** Container orchestration, auto-scaling, production workloads

```bash
# 1. Build and push to ECR (same as App Runner)
./scripts/deploy-apprunner.sh us-east-1

# 2. Update ecs-task-definition.json with your account ID
# 3. Register task definition:
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# 4. Create ECS service (see AWS_DEPLOYMENT.md for details)
```

**Cost:** ~$30-50/month

## 🔐 Environment Variables

Set these before deploying:

```bash
# Option 1: Export in shell
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Option 2: Use AWS Systems Manager Parameter Store (Recommended)
aws ssm put-parameter --name "/safesim/openai-api-key" --value "sk-..." --type "SecureString"
aws ssm put-parameter --name "/safesim/anthropic-api-key" --value "sk-ant-..." --type "SecureString"

# Option 3: Create .env file (for EC2)
echo "OPENAI_API_KEY=sk-..." > .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

## 📋 Prerequisites Checklist

- [ ] AWS Account created
- [ ] AWS CLI installed (`aws --version`)
- [ ] AWS CLI configured (`aws configure`)
- [ ] Docker installed (for containerized deployments)
- [ ] API keys ready (OpenAI/Anthropic)

## 🆘 Need Help?

See [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md) for detailed instructions.

## 🎯 Recommended for First-Time Users

**Start with AWS App Runner** - it's the easiest and fastest way to get started!

1. Run: `./scripts/deploy-apprunner.sh`
2. Follow the prompts
3. Access your app via the App Runner URL

That's it! 🎉

