#!/bin/bash
# Run once from Codespace: bash setup.sh
# Requires: aws cli configured + gh cli authenticated

set -e

# ── Config — change these ─────────────────────────────────────────────────────
GITHUB_REPO="hyukaisthecutest-lab/mint"   # e.g. "johndoe/mint"
AWS_REGION="us-east-1"
INSTANCE_TYPE="t3.small"
KEY_NAME="mint-key"
# ─────────────────────────────────────────────────────────────────────────────

echo "==> Creating EC2 key pair..."
aws ec2 create-key-pair \
  --key-name $KEY_NAME \
  --region $AWS_REGION \
  --query 'KeyMaterial' \
  --output text > mint-key.pem
chmod 400 mint-key.pem

echo "==> Getting default VPC and subnet..."
VPC_ID=$(aws ec2 describe-vpcs \
  --region $AWS_REGION \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' --output text)

SUBNET_ID=$(aws ec2 describe-subnets \
  --region $AWS_REGION \
  --filters "Name=vpcId,Values=$VPC_ID" \
  --query 'Subnets[0].SubnetId' --output text)

echo "==> Creating security group..."
SG_ID=$(aws ec2 create-security-group \
  --region $AWS_REGION \
  --group-name mint-sg \
  --description "Mint app" \
  --vpc-id $VPC_ID \
  --query 'GroupId' --output text)

aws ec2 authorize-security-group-ingress --region $AWS_REGION --group-id $SG_ID --protocol tcp --port 22   --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --region $AWS_REGION --group-id $SG_ID --protocol tcp --port 5173 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --region $AWS_REGION --group-id $SG_ID --protocol tcp --port 8000 --cidr 0.0.0.0/0

echo "==> Getting latest Ubuntu 22.04 AMI..."
AMI_ID=$(aws ec2 describe-images \
  --region $AWS_REGION \
  --owners 099720109477 \
  --filters \
    "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

echo "==> Writing user-data (runs automatically on EC2 first boot)..."
SECRET_KEY=$(openssl rand -hex 32)

cat > /tmp/user-data.sh << USERDATA
#!/bin/bash
exec > /var/log/mint-setup.log 2>&1
set -e

apt-get update -y
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu
apt-get install -y docker-compose-plugin git

sudo -u ubuntu git clone https://github.com/${GITHUB_REPO}.git /home/ubuntu/mint
cd /home/ubuntu/mint
sudo -u ubuntu cp .env.example .env
sudo -u ubuntu sed -i "s/your-super-secret-key-change-in-production/${SECRET_KEY}/" .env

sudo -u ubuntu docker compose up -d --build

# Wait for postgres to be ready then run migrations
sleep 45
sudo -u ubuntu docker compose exec -T backend alembic upgrade head

echo "MINT SETUP COMPLETE"
USERDATA

echo "==> Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
  --region $AWS_REGION \
  --image-id $AMI_ID \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME \
  --security-group-ids $SG_ID \
  --subnet-id $SUBNET_ID \
  --user-data file:///tmp/user-data.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=mint-v0}]' \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "   Instance: $INSTANCE_ID"
echo "==> Waiting for instance to be running..."
aws ec2 wait instance-running --region $AWS_REGION --instance-ids $INSTANCE_ID

echo "==> Allocating Elastic IP..."
ALLOCATION_ID=$(aws ec2 allocate-address \
  --region $AWS_REGION \
  --domain vpc \
  --query 'AllocationId' --output text)

ELASTIC_IP=$(aws ec2 describe-addresses \
  --region $AWS_REGION \
  --allocation-ids $ALLOCATION_ID \
  --query 'Addresses[0].PublicIp' --output text)

aws ec2 associate-address \
  --region $AWS_REGION \
  --instance-id $INSTANCE_ID \
  --allocation-id $ALLOCATION_ID > /dev/null

echo "   Elastic IP: $ELASTIC_IP"

echo "==> Setting GitHub Actions secrets..."
gh secret set EC2_HOST  --body "$ELASTIC_IP"   --repo $GITHUB_REPO
gh secret set EC2_USER  --body "ubuntu"         --repo $GITHUB_REPO
gh secret set EC2_SSH_KEY --body "$(cat mint-key.pem)" --repo $GITHUB_REPO

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  All done!"
echo ""
echo "  EC2 is booting + installing (~3 min)"
echo "  Watch progress:"
echo "  ssh -i mint-key.pem ubuntu@$ELASTIC_IP 'tail -f /var/log/mint-setup.log'"
echo ""
echo "  Frontend : http://$ELASTIC_IP:5173"
echo "  API docs : http://$ELASTIC_IP:8000/docs"
echo ""
echo "  From now on: git push origin main → auto deploy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
