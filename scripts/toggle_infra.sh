#!/usr/bin/env bash
#
# Toggle infrastructure on/off to save costs, or dismantle entirely.
#
# Usage:
#   ./scripts/toggle_infra.sh --off          # Stop all instances (no cost except EBS/EIP)
#   ./scripts/toggle_infra.sh --on           # Start all instances
#   ./scripts/toggle_infra.sh --status       # Show current state
#   ./scripts/toggle_infra.sh --dismantle    # DESTROY everything (terraform destroy)
#
# Requires: AWS CLI with profile sebs-admin, terraform
#
set -euo pipefail

PROFILE="sebs-admin"
REGION="eu-north-1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SEBS_DIR="$(dirname "$SCRIPT_DIR")"

# Terraform directories
TF_BASELINE="$SEBS_DIR/integrations/baseline/aws"
TF_CLOUDBURST="$SEBS_DIR/integrations/cloudburst/aws"
TF_BOKI="$SEBS_DIR/integrations/boki/aws/EC2"
TF_RESTATE="$SEBS_DIR/integrations/restate/aws"

# ASG names
BOKI_ASG="boki-experimental-engines"
CB_ASG="master-sebs-cloudburst-executors"

aws_cmd() {
    aws --profile "$PROFILE" --region "$REGION" "$@"
}

get_all_instance_ids() {
    # Get all instances tagged with our project names
    aws_cmd ec2 describe-instances \
        --filters "Name=instance-state-name,Values=running,stopped" \
        --query 'Reservations[*].Instances[*].[InstanceId,Tags[?Key==`Name`].Value|[0],State.Name]' \
        --output text 2>/dev/null | grep -E "boki|cloudburst|sebs" | sort
}

status() {
    echo "=== Instance Status ==="
    get_all_instance_ids | while read -r id name state; do
        printf "  %-24s %-45s %s\n" "$id" "$name" "$state"
    done

    echo ""
    echo "=== ASG Status ==="
    for asg in "$BOKI_ASG" "$CB_ASG"; do
        result=$(aws_cmd autoscaling describe-auto-scaling-groups \
            --auto-scaling-group-names "$asg" \
            --query 'AutoScalingGroups[0].{Name:AutoScalingGroupName,Min:MinSize,Desired:DesiredCapacity,Max:MaxSize,Count:length(Instances)}' \
            --output text 2>/dev/null) || true
        if [ -n "$result" ]; then
            echo "  $result"
        fi
    done

    echo ""
    echo "=== ElastiCache ==="
    aws_cmd elasticache describe-replication-groups \
        --query 'ReplicationGroups[*].[ReplicationGroupId,Status]' \
        --output text 2>/dev/null | while read -r id status; do
        echo "  $id: $status"
    done
}

off() {
    echo "=== Stopping all infrastructure ==="
    echo ""

    # 1. Scale ASGs to 0
    echo "Scaling ASGs to 0..."
    for asg in "$BOKI_ASG" "$CB_ASG"; do
        aws_cmd autoscaling update-auto-scaling-group \
            --auto-scaling-group-name "$asg" \
            --min-size 0 --desired-capacity 0 2>/dev/null && \
            echo "  $asg → 0" || echo "  $asg: not found (skip)"
    done

    # 2. Stop all non-ASG instances
    echo ""
    echo "Stopping standalone instances..."
    INSTANCE_IDS=$(get_all_instance_ids | grep "running" | awk '{print $1}')
    if [ -n "$INSTANCE_IDS" ]; then
        # Wait for ASG to terminate its instances first
        sleep 10
        # Get remaining running instances (non-ASG ones)
        REMAINING=$(aws_cmd ec2 describe-instances \
            --filters "Name=instance-state-name,Values=running" \
            --query 'Reservations[*].Instances[*].[InstanceId,Tags[?Key==`Name`].Value|[0]]' \
            --output text 2>/dev/null | grep -E "boki|cloudburst|sebs" | awk '{print $1}')
        if [ -n "$REMAINING" ]; then
            echo "  Stopping: $REMAINING"
            aws_cmd ec2 stop-instances --instance-ids $REMAINING > /dev/null 2>&1
        fi
    fi
    echo "  Done"

    echo ""
    echo "Infrastructure stopped. Costs reduced to:"
    echo "  - EBS volumes (gp3 storage)"
    echo "  - ElastiCache (still running — stop manually if needed)"
    echo "  - Elastic IPs (if any)"
    echo ""
    echo "Restart with: $0 --on"
}

on() {
    echo "=== Starting all infrastructure ==="
    echo ""

    # 1. Start all stopped instances
    echo "Starting stopped instances..."
    STOPPED=$(aws_cmd ec2 describe-instances \
        --filters "Name=instance-state-name,Values=stopped" \
        --query 'Reservations[*].Instances[*].[InstanceId,Tags[?Key==`Name`].Value|[0]]' \
        --output text 2>/dev/null | grep -E "boki|cloudburst|sebs")
    if [ -n "$STOPPED" ]; then
        IDS=$(echo "$STOPPED" | awk '{print $1}')
        echo "$STOPPED" | while read -r id name; do
            echo "  Starting $name ($id)"
        done
        aws_cmd ec2 start-instances --instance-ids $IDS > /dev/null 2>&1
    else
        echo "  No stopped instances found"
    fi

    # 2. Scale ASGs back up
    echo ""
    echo "Scaling ASGs to desired capacity..."
    aws_cmd autoscaling update-auto-scaling-group \
        --auto-scaling-group-name "$BOKI_ASG" \
        --min-size 1 --desired-capacity 2 --max-size 4 2>/dev/null && \
        echo "  $BOKI_ASG → 1/2/4" || echo "  $BOKI_ASG: not found (skip)"

    aws_cmd autoscaling update-auto-scaling-group \
        --auto-scaling-group-name "$CB_ASG" \
        --min-size 1 --desired-capacity 2 --max-size 4 2>/dev/null && \
        echo "  $CB_ASG → 1/2/4" || echo "  $CB_ASG: not found (skip)"

    echo ""
    echo "Infrastructure starting. Wait ~3 min for full bootstrap."
    echo "NOTE: After restart you may need to:"
    echo "  - Restart Cloudburst scheduler/executors (processes don't auto-start on stop/start)"
    echo "  - Restart Cloudburst HTTP gateway"
    echo "  - Deploy Boki stateful_bench binary to new engine instances"
    echo "  - Public IPs will change — update files containing public IPs"
}

dismantle() {
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  WARNING: This will DESTROY all infrastructure  ║"
    echo "║  All data, instances, and resources deleted.     ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    read -p "Type 'DESTROY' to confirm: " confirm
    if [ "$confirm" != "DESTROY" ]; then
        echo "Aborted."
        exit 1
    fi

    echo ""
    echo "=== Destroying Boki ==="
    if [ -d "$TF_BOKI" ]; then
        cd "$TF_BOKI" && AWS_PROFILE="$PROFILE" terraform destroy -auto-approve 2>&1 | tail -5
    else
        echo "  No Terraform dir found"
    fi

    echo ""
    echo "=== Destroying Cloudburst ==="
    if [ -d "$TF_CLOUDBURST" ]; then
        cd "$TF_CLOUDBURST" && AWS_PROFILE="$PROFILE" terraform destroy -auto-approve 2>&1 | tail -5
    else
        echo "  No Terraform dir found"
    fi

    echo ""
    echo "=== Destroying Baseline (Lambda + Redis) ==="
    if [ -d "$TF_BASELINE" ]; then
        cd "$TF_BASELINE" && AWS_PROFILE="$PROFILE" terraform destroy -auto-approve 2>&1 | tail -5
    else
        echo "  No Terraform dir found"
    fi

    echo ""
    echo "=== Destroying Restate ==="
    if [ -d "$TF_RESTATE" ]; then
        cd "$TF_RESTATE" && AWS_PROFILE="$PROFILE" terraform destroy -auto-approve 2>&1 | tail -5
    else
        echo "  No Terraform dir found"
    fi

    echo ""
    echo "All infrastructure destroyed."
}

# Main
case "${1:---status}" in
    --off)       off ;;
    --on)        on ;;
    --status)    status ;;
    --dismantle) dismantle ;;
    *)
        echo "Usage: $0 [--on|--off|--status|--dismantle]"
        echo ""
        echo "  --off       Stop instances, scale ASGs to 0 (save costs)"
        echo "  --on        Start instances, scale ASGs to desired capacity"
        echo "  --status    Show current infrastructure state"
        echo "  --dismantle DESTROY all infrastructure (terraform destroy)"
        exit 1
        ;;
esac
