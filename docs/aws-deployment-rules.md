# AWS Deployment Rules

## Deployment identity

- Local AWS CLI profile: `baseball-scouting`
- Local authentication: AWS IAM Identity Center
- GitHub Actions authentication: GitHub OIDC
- Permanent AWS access keys are prohibited.
- The AWS root user is reserved for account-level tasks only.

## Region and naming

- Primary AWS Region: `us-east-1`
- Resource prefix: `baseball-video-scouting-`
- CloudFormation/SAM stack name: `baseball-video-scouting-portfolio`

Examples:

- `baseball-video-scouting-backend`
- `baseball-video-scouting-api`
- `baseball-video-scouting-frontend`
- `baseball-video-scouting-database`

S3 bucket names may require an additional unique suffix because S3 names are globally unique.

## Required tags

Every supported resource must receive:

- `Project = baseball-video-scouting`
- `Environment = portfolio`
- `Owner = bdrisc`
- `ManagedBy = sam`

Tag names and values are case-sensitive.

## Cost controls

- Maintain the $10 monthly AWS budget and alerts.
- Do not create RDS until Step 30.
- Do not create NAT Gateways for this portfolio project without reviewing their cost.
- Delete unused test resources promptly.
- Review AWS Billing after each deployment phase.

## Secrets

- Never commit passwords, access keys, secret keys, session tokens, or private keys.
- Local development secrets belong in ignored `.env` files.
- Deployed application secrets belong in AWS Secrets Manager or another approved AWS secret-management service.
- GitHub deployments will use OIDC instead of stored AWS keys.

## Infrastructure management

Use AWS SAM and CloudFormation wherever possible so related resources can be managed as a stack.

Expected cleanup command for the backend stack:

`sam delete --stack-name baseball-video-scouting-portfolio --profile baseball-scouting --region us-east-1`

The exact command must be reviewed before it is run.

## Cleanup checklist

Before considering the AWS deployment removed, verify deletion of:

1. CloudFront distribution
2. S3 frontend bucket, objects, and object versions
3. API Gateway API
4. Lambda function and published versions
5. ECR container images and repository
6. CloudWatch log groups
7. PostgreSQL database and unwanted snapshots
8. Secrets Manager secrets
9. IAM deployment roles and policies
10. Remaining CloudFormation stacks

The RDS database is the primary recurring-cost risk and will not be created until Step 30.