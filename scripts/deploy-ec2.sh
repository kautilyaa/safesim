#!/bin/bash
# Deploy SafeSim to EC2 instance
# Usage: ./scripts/deploy-ec2.sh <instance-ip> <key-file> [user]

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <instance-ip> <key-file> [user]"
    echo "Example: $0 54.123.45.67 ~/.ssh/my-key.pem ec2-user"
    exit 1
fi

INSTANCE_IP=$1
KEY_FILE=$2
USER=${3:-ec2-user}

echo "🚀 Deploying SafeSim to EC2 instance: $INSTANCE_IP"
echo ""

# Check if key file exists
if [ ! -f "$KEY_FILE" ]; then
    echo "❌ Key file not found: $KEY_FILE"
    exit 1
fi

# Set correct permissions on key file
chmod 400 "$KEY_FILE"

# Create deployment package
echo "📦 Creating deployment package..."
TEMP_DIR=$(mktemp -d)
tar --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.pytest_cache' --exclude='.venv' --exclude='venv' \
    --exclude='data' --exclude='result' --exclude='evaluation/results' \
    -czf "$TEMP_DIR/safesim.tar.gz" .

# Copy to EC2
echo "⬆️  Copying files to EC2..."
scp -i "$KEY_FILE" "$TEMP_DIR/safesim.tar.gz" "$USER@$INSTANCE_IP:/tmp/"

# Deploy script
cat > "$TEMP_DIR/deploy.sh" << 'DEPLOY_SCRIPT'
#!/bin/bash
set -e

cd /home/$USER || cd /home/ec2-user
mkdir -p safesim
cd safesim

echo "📦 Extracting files..."
tar -xzf /tmp/safesim.tar.gz

echo "🐍 Installing Python dependencies..."
python3.12 -m pip install --user -r requirements.txt || python3 -m pip install --user -r requirements.txt

echo "📥 Downloading spaCy model..."
python3.12 -m spacy download en_core_web_sm || python3 -m spacy download en_core_web_sm

echo "✅ Deployment complete!"
echo ""
echo "To run SafeSim:"
echo "  cd ~/safesim"
echo "  streamlit run src/ui/app.py --server.port=8501 --server.address=0.0.0.0"
DEPLOY_SCRIPT

scp -i "$KEY_FILE" "$TEMP_DIR/deploy.sh" "$USER@$INSTANCE_IP:/tmp/"

# Execute deployment
echo "🔧 Running deployment on EC2..."
ssh -i "$KEY_FILE" "$USER@$INSTANCE_IP" "chmod +x /tmp/deploy.sh && /tmp/deploy.sh"

# Cleanup
rm -rf "$TEMP_DIR"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. SSH into instance: ssh -i $KEY_FILE $USER@$INSTANCE_IP"
echo "2. Set environment variables (create ~/.env or export them)"
echo "3. Run: cd ~/safesim && streamlit run src/ui/app.py --server.port=8501 --server.address=0.0.0.0"
echo "4. Access at: http://$INSTANCE_IP:8501"
echo ""
echo "To set up as a systemd service, see AWS_DEPLOYMENT.md"

