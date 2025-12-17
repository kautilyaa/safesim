# AWS Deployment Guide for SafeSim

This guide provides multiple options for deploying SafeSim on AWS. Choose the option that best fits your needs.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Option 1: AWS App Runner (Recommended - Easiest)](#option-1-aws-app-runner-recommended---easiest)
3. [Option 2: AWS Elastic Beanstalk](#option-2-aws-elastic-beanstalk)
4. [Option 3: Amazon EC2](#option-3-amazon-ec2)
5. [Option 4: Amazon ECS/Fargate](#option-4-amazon-ecsfargate)
6. [Option 5: API Gateway (Recommended for Production)](#option-5-api-gateway-recommended-for-production)
7. [Environment Variables](#environment-variables)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured (`aws configure`)
- Docker installed (for containerized deployments)
- Git installed
- API keys for LLM backends (OpenAI, Anthropic) if needed

## Option 1: AWS App Runner (Recommended - Easiest)

AWS App Runner is the simplest way to deploy containerized applications on AWS.

### Steps:

1. **Build and push Docker image to Amazon ECR:**

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repository
aws ecr create-repository --repository-name safesim --region us-east-1

# Build Docker image
docker build -t safesim .

# Tag image
docker tag safesim:latest <YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/safesim:latest

# Push image
docker push <YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/safesim:latest
```

2. **Create App Runner service:**

Use the AWS Console or create `apprunner-config.yaml`:

```yaml
version: 1.0
runtime: docker
build:
  commands:
    build:
      - echo "No build commands needed"
run:
  runtime-version: latest
  command: streamlit run src/ui/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
  network:
    port: 8501
    env: PORT
  env:
    - name: OPENAI_API_KEY
      value: "your-openai-key"
    - name: ANTHROPIC_API_KEY
      value: "your-anthropic-key"
```

3. **Deploy via AWS Console:**
   - Go to AWS App Runner console
   - Click "Create service"
   - Select "Container registry" → "Amazon ECR"
   - Choose your repository and image
   - Configure service settings
   - Add environment variables
   - Deploy

**Cost:** ~$0.007/hour (~$5/month for minimal usage)

## Option 2: AWS Elastic Beanstalk

Elastic Beanstalk provides a platform-as-a-service for Python applications.

### Steps:

1. **Install EB CLI:**

```bash
pip install awsebcli
```

2. **Initialize Elastic Beanstalk:**

```bash
cd /path/to/safesim
eb init -p "Docker" safesim-app --region us-east-1
```

3. **Create environment configuration file `.ebextensions/01_streamlit.config`:**

```yaml
option_settings:
  aws:elasticbeanstalk:container:docker:
    staticfiles: /app/static
  aws:elasticbeanstalk:application:environment:
    PORT: 8501
```

4. **Create `Dockerrun.aws.json`:**

```json
{
  "AWSEBDockerrunVersion": "1",
  "Image": {
    "Name": "<YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/safesim:latest",
    "Update": "true"
  },
  "Ports": [
    {
      "ContainerPort": "8501"
    }
  ],
  "Environment": [
    {
      "Name": "OPENAI_API_KEY",
      "Value": "your-openai-key"
    },
    {
      "Name": "ANTHROPIC_API_KEY",
      "Value": "your-anthropic-key"
    }
  ]
}
```

5. **Create and deploy:**

```bash
eb create safesim-env
eb deploy
```

**Cost:** ~$0.10/hour (~$72/month) + EC2 instance costs

## Option 3: Amazon EC2

Deploy directly on an EC2 instance for maximum control.

### Steps:

1. **Launch EC2 Instance:**

   - AMI: Amazon Linux 2023 or Ubuntu 22.04 LTS
   - Instance Type: t3.medium or larger (for ML models)
   - Security Group: Allow inbound on port 8501

2. **SSH into instance:**

```bash
ssh -i your-key.pem ec2-user@your-instance-ip
```

3. **Install dependencies:**

```bash
# Update system
sudo yum update -y  # Amazon Linux
# or
sudo apt update && sudo apt upgrade -y  # Ubuntu

# Install Python 3.12
sudo yum install -y python3.12 python3.12-pip git

# Install Docker (optional, for containerized deployment)
sudo yum install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user
```

4. **Clone and setup:**

```bash
git clone https://github.com/yourusername/safesim.git
cd safesim
pip3.12 install -r requirements.txt
python3.12 -m spacy download en_core_web_sm
```

5. **Create systemd service (`/etc/systemd/system/safesim.service`):**

```ini
[Unit]
Description=SafeSim Streamlit App
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/safesim
Environment="OPENAI_API_KEY=your-key"
Environment="ANTHROPIC_API_KEY=your-key"
ExecStart=/usr/local/bin/streamlit run src/ui/app.py --server.port=8501 --server.address=0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

6. **Start service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable safesim
sudo systemctl start safesim
```

7. **Access your application:**

Your SafeSim app will be available at:
```
http://<your-instance-ip>:8501
```

**Note:** For HTTPS and custom domain support, use API Gateway (Option 5) or Application Load Balancer with ACM certificate.

**Cost:** ~$0.05-0.10/hour depending on instance type (~$36-72/month)

## Option 4: Amazon ECS/Fargate

Deploy as a containerized service with auto-scaling.

### Steps:

1. **Build and push Docker image to ECR** (same as Option 1)

2. **Create ECS Task Definition** (`ecs-task-definition.json`):

```json
{
  "family": "safesim",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "safesim",
      "image": "<YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/safesim:latest",
      "portMappings": [
        {
          "containerPort": 8501,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "OPENAI_API_KEY",
          "value": "your-openai-key"
        },
        {
          "name": "ANTHROPIC_API_KEY",
          "value": "your-anthropic-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/safesim",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

3. **Register task definition:**

```bash
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
```

4. **Create ECS Service:**

```bash
aws ecs create-service \
  --cluster safesim-cluster \
  --service-name safesim-service \
  --task-definition safesim \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

5. **Create Application Load Balancer** (for public access):

See AWS Console → EC2 → Load Balancers

**Cost:** ~$0.04/vCPU-hour + $0.004/GB-hour (~$30-50/month)

## Option 5: API Gateway (Recommended for Production)

Deploy Streamlit backend behind API Gateway for a single public endpoint with built-in security and monitoring.

### Steps:

1. **Deploy Streamlit backend** (using any of the options above)

2. **Setup API Gateway:**

```bash
# Use the provided script
./scripts/setup-api-gateway.sh <your-backend-url>

# Example for App Runner:
./scripts/setup-api-gateway.sh https://your-app-runner-url.us-east-1.awsapprunner.com

# Example for EC2:
./scripts/setup-api-gateway.sh http://ec2-54-123-45-67.compute-1.amazonaws.com:8501
```

3. **Access your application:**

The script will output your API Gateway endpoint URL. Your app will be available at:
```
https://<api-id>.execute-api.<region>.amazonaws.com/prod
```

**Benefits:**
- Single public endpoint
- Built-in DDoS protection
- Request throttling and rate limiting
- CloudWatch monitoring
- Custom domain support with SSL
- Cost-effective ($3.50 per million requests)

**Cost:** ~$0.35/month for 100K requests

For detailed API Gateway setup instructions, see [API_GATEWAY_DEPLOYMENT.md](./API_GATEWAY_DEPLOYMENT.md).

## Environment Variables

Set these environment variables for your deployment:

- `OPENAI_API_KEY`: Your OpenAI API key (optional)
- `ANTHROPIC_API_KEY`: Your Anthropic API key (optional)
- `PORT`: Port for Streamlit (default: 8501)

### Using AWS Systems Manager Parameter Store (Recommended):

```bash
# Store secrets securely
aws ssm put-parameter --name "/safesim/openai-api-key" --value "sk-..." --type "SecureString"
aws ssm put-parameter --name "/safesim/anthropic-api-key" --value "sk-ant-..." --type "SecureString"
```

Then reference in your deployment configuration.

## Quick Deploy Scripts

### Deploy to App Runner (Quickest)

```bash
# 1. Build and push to ECR
./scripts/deploy-apprunner.sh

# 2. Create App Runner service via console or CLI
aws apprunner create-service --cli-input-json file://apprunner-service.json
```

### Deploy to EC2

```bash
# Use the provided script
./scripts/deploy-ec2.sh <instance-ip> <key-file>
```

## Security Considerations

1. **Use AWS Secrets Manager** or **Parameter Store** for API keys
2. **Enable HTTPS** using AWS Certificate Manager (ACM)
3. **Restrict security groups** to specific IPs if possible
4. **Use IAM roles** instead of hardcoding credentials
5. **Enable CloudWatch logging** for monitoring

## Monitoring and Logs

- **CloudWatch Logs**: View application logs
- **CloudWatch Metrics**: Monitor CPU, memory, requests
- **AWS X-Ray**: Trace requests (optional)

## Troubleshooting

### Application won't start

- Check CloudWatch logs
- Verify environment variables are set
- Ensure port 8501 is accessible
- Check security group rules

### High memory usage

- Consider using larger instance types
- Enable swap space on EC2
- Use Fargate with more memory allocation

### API rate limits

- Implement request throttling
- Use API key rotation
- Monitor usage in CloudWatch

## Cost Optimization

1. **Use App Runner** for lowest cost (~$5/month)
2. **Use EC2 Spot Instances** for development (~$10-20/month)
3. **Auto-scale down** during off-hours
4. **Use CloudFront** for caching static assets

## Next Steps

1. Set up CI/CD pipeline with GitHub Actions or AWS CodePipeline
2. Configure custom domain with Route 53
3. Set up monitoring alerts
4. Implement auto-scaling policies

For detailed instructions on any option, refer to the AWS documentation or contact support.

