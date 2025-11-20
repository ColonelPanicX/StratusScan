# StratusScan IAM Permissions Guide

This directory contains IAM policy documents for StratusScan, a defensive AWS security auditing tool that performs read-only resource scanning and exports across your AWS environment.

## Overview

StratusScan requires specific AWS IAM permissions to scan and export resource information from your AWS accounts. We provide two policy documents to support different levels of functionality:

- **stratusscan-required-permissions.json** - Core permissions for basic StratusScan functionality
- **stratusscan-optional-permissions.json** - Advanced features (Security Hub, Cost Optimization, Trusted Advisor, etc.)

## Quick Start

### Option 1: For IAM Users/Roles (Recommended for most users)

1. **Check your current permissions**:
   ```bash
   python configure.py --perms
   ```

2. **Copy the required policy**:
   - Open `stratusscan-required-permissions.json`
   - Copy the entire JSON content

3. **Create a custom IAM policy**:
   - Go to [IAM Policies Console](https://console.aws.amazon.com/iam/home#/policies)
   - Click "Create policy" > "JSON" tab
   - Paste the policy JSON
   - Click "Next: Tags" > "Next: Review"
   - Name it: `StratusScanRequiredPermissions`
   - Click "Create policy"

4. **Attach the policy to your IAM user or role**:
   - Go to [IAM Users](https://console.aws.amazon.com/iam/home#/users) or [IAM Roles](https://console.aws.amazon.com/iam/home#/roles)
   - Select your user/role
   - Click "Add permissions" > "Attach policies directly"
   - Search for `StratusScanRequiredPermissions`
   - Click "Add permissions"

5. **Optional: Add advanced features**:
   - Repeat steps 2-4 with `stratusscan-optional-permissions.json`
   - Name it: `StratusScanOptionalPermissions`

### Option 2: For AWS IAM Identity Center (SSO) Users

1. **Check your current permissions**:
   ```bash
   python configure.py --perms
   ```

2. **Create custom permission sets**:
   - Go to [IAM Identity Center Console](https://console.aws.amazon.com/singlesignon/home)
   - Click "Permission sets" > "Create permission set"
   - Select "Create a custom permission set"
   - Click "Next"

3. **Add inline policy for required permissions**:
   - In "Inline policy" section, click "Create inline policy"
   - Switch to JSON editor
   - Copy and paste contents of `stratusscan-required-permissions.json`
   - Click "Next"
   - Name the permission set: `StratusScanRequired`
   - Set session duration (recommended: 8-12 hours)
   - Click "Create"

4. **Optional: Create permission set for advanced features**:
   - Repeat steps 2-3 with `stratusscan-optional-permissions.json`
   - Name it: `StratusScanOptional`

5. **Assign permission sets to users/groups**:
   - Go to "AWS accounts" in Identity Center
   - Select your account
   - Click "Assign users or groups"
   - Select your user/group
   - Select the permission sets you created
   - Click "Submit"

### Option 3: Use AWS Managed Policies (Simpler but broader permissions)

If you prefer using AWS-managed policies instead of custom policies:

**Recommended managed policy**:
- `ReadOnlyAccess` - Provides comprehensive read-only access to most AWS services

**Alternative managed policies** (more granular, require multiple attachments):
- `AmazonEC2ReadOnlyAccess`
- `AmazonS3ReadOnlyAccess`
- `AmazonRDSReadOnlyAccess`
- `AmazonVPCReadOnlyAccess`
- `IAMReadOnlyAccess`
- `CloudWatchReadOnlyAccess`
- `AWSCloudTrailReadOnlyAccess`
- `SecurityAudit`

**For optional features**:
- `AWSSupportAccess` (for Trusted Advisor)
- `AWSBillingReadOnlyAccess` (for Cost Explorer)
- `AWSSSOReadOnly` (for Identity Center)

**Note**: Managed policies may grant broader permissions than strictly necessary. For production environments, consider using the custom policies provided in this directory for least-privilege access.

## Policy Details

### Required Permissions Policy

**File**: `stratusscan-required-permissions.json`

**Coverage**: This policy covers the core StratusScan functionality for 100+ export scripts across:

- **Compute**: EC2, ECS, EKS, Lambda, Auto Scaling, Elastic Beanstalk
- **Storage**: S3, EBS, EFS, FSx, Glacier, Storage Gateway, Backup
- **Database**: RDS, DynamoDB, ElastiCache, Redshift, Neptune, DocumentDB, MemoryDB
- **Network**: VPC, Load Balancers, Route 53, CloudFront, Direct Connect, Global Accelerator, Network Firewall
- **IAM & Security**: IAM, KMS, Secrets Manager, ACM, WAF, Shield, GuardDuty, CloudTrail, Config, Access Analyzer, Detective, Macie
- **Monitoring**: CloudWatch, CloudWatch Logs, X-Ray
- **Applications**: API Gateway, AppSync, App Runner, Cognito, SNS, SQS, EventBridge, Step Functions
- **DevOps**: CodeCommit, CodeBuild, CodeDeploy, CodePipeline
- **Data Analytics**: Glue, Athena, Lake Formation, OpenSearch
- **ML/AI**: SageMaker, Bedrock, Comprehend, Rekognition
- **Management**: CloudFormation, Systems Manager, Service Catalog, Image Builder, DataSync, Transfer Family
- **Organizations**: AWS Organizations
- **Other**: SES, Pinpoint, License Manager, Marketplace, Verified Access, IAM Roles Anywhere

**Total Permissions**: ~250 read-only actions across 80+ AWS services

**Actions Included**: All actions use read-only patterns:
- `Get*` - Retrieve individual resource details
- `List*` - List resources
- `Describe*` - Get resource descriptions
- `BatchGet*` - Batch retrieve resources

**No Write Permissions**: This policy contains ZERO write, modify, or delete actions. It is safe for audit and compliance use cases.

### Optional Permissions Policy

**File**: `stratusscan-optional-permissions.json`

**Coverage**: Advanced features that are optional or may not be available in all AWS environments:

- **Security Hub**: Full Security Hub findings and compliance status
- **Cost Management**: Cost Explorer, Cost Optimization Hub, Budgets, Cost & Usage Reports, Savings Plans
- **Trusted Advisor**: AWS Support API for Trusted Advisor recommendations (requires Business/Enterprise Support)
- **Compute Optimizer**: ML-powered optimization recommendations
- **Identity Center**: AWS IAM Identity Center (SSO) users, groups, and permission sets
- **Health**: AWS Health Dashboard and Personal Health Dashboard
- **Reserved Instances**: Reserved capacity across EC2, RDS, ElastiCache, Redshift, OpenSearch
- **Capacity Reservations**: EC2 Capacity Reservations and Dedicated Hosts

**Total Permissions**: ~60 read-only actions across 8+ AWS services

**Why Optional**:
- Some services require additional AWS support plans (e.g., Trusted Advisor requires Business/Enterprise)
- Some services are only available in AWS Commercial (not GovCloud)
- Some organizations may not use these services

## Permission Checking

StratusScan includes a built-in permission checker to validate your IAM permissions:

```bash
# Check permissions only
python configure.py --perms
```

The permission checker will:
1. Identify your AWS identity (user/role)
2. Test required permissions by calling AWS APIs
3. Test optional permissions
4. Display missing permissions grouped by category
5. Provide guidance on which policy file to use

**Sample Output**:
```
===================================================
AWS PERMISSIONS CHECK
===================================================
Testing AWS permissions for StratusScan operations...

AWS Identity: arn:aws:iam::123456789012:user/security-auditor
Account ID: 123456789012

Testing individual permissions...

Permission Test Results:
--------------------------------------------------
[OK] sts:GetCallerIdentity (REQUIRED)
    Service: AWS Security Token Service
    Purpose: Basic AWS authentication verification

[OK] ec2:DescribeInstances (REQUIRED)
    Service: Amazon EC2
    Purpose: List EC2 instances for compute resource scanning

[DENIED] ce:GetDimensionValues (OPTIONAL)
    Service: AWS Cost Explorer
    Purpose: Access cost data for comprehensive service discovery
    Error: AccessDenied

===================================================
PERMISSIONS SUMMARY
===================================================
Required permissions: 6/6 passed
Optional permissions: 2/4 passed

[SUCCESS] All required permissions are available!
[INFO] 2 optional permissions are missing.
Some advanced features may not be available.

[OPTIONS] Permissions Management Options:
1. Show AWS managed policy recommendations
2. Re-test permissions (after applying policies)
3. Continue with current permissions
4. Show detailed permission test results
```

## GovCloud Considerations

Both policy documents are designed for AWS Commercial but are compatible with AWS GovCloud with these caveats:

**Services NOT available in GovCloud**:
- AWS Trusted Advisor (Business/Enterprise Support API)
- AWS Cost Optimization Hub
- Some AWS Marketplace services
- Some newer AI/ML services

**Services with different ARN formats in GovCloud**:
- All ARNs use `aws-us-gov` partition instead of `aws`
- StratusScan automatically detects and handles partition differences

**Recommendations for GovCloud**:
1. Use the required permissions policy as-is
2. For optional permissions, remove Trusted Advisor and Cost Optimization Hub sections if needed
3. Validate service availability using `python configure.py --perms`

## Security Best Practices

1. **Least Privilege**: These policies follow AWS least-privilege principles by granting only read-only access
2. **No Secrets in Exports**: StratusScan automatically sanitizes sensitive data in exports (see `utils.sanitize_for_export()`)
3. **Audit Regularly**: Review IAM policies quarterly and remove unused permissions
4. **Use IAM Roles**: For EC2-based deployments, use IAM instance roles instead of IAM users
5. **MFA Protection**: Enable MFA for IAM users with these permissions
6. **Session Duration**: For Identity Center, set appropriate session durations (4-12 hours recommended)

## Troubleshooting

### "Access Denied" errors during scanning

**Symptom**: Scripts fail with `AccessDenied` or `UnauthorizedOperation` errors

**Solutions**:
1. Run `python configure.py --perms` to identify missing permissions
2. Verify the policy is attached to your IAM user/role
3. Check if SCPs (Service Control Policies) are blocking access at the organization level
4. Verify you're using the correct AWS profile: `aws sts get-caller-identity`

### "No credentials found" errors

**Symptom**: `NoCredentialsError: Unable to locate credentials`

**Solutions**:
1. Configure AWS credentials:
   ```bash
   # For IAM users
   aws configure

   # For IAM Identity Center
   aws configure sso
   aws sso login
   ```
2. Set AWS profile environment variable:
   ```bash
   export AWS_PROFILE=your-profile-name
   ```

### Trusted Advisor checks fail

**Symptom**: `SubscriptionRequiredException` when running Trusted Advisor scripts

**Cause**: Trusted Advisor API requires AWS Business or Enterprise Support plan

**Solutions**:
1. Upgrade to Business/Enterprise Support (if needed for your use case)
2. Skip Trusted Advisor scripts (they're in the optional permissions)
3. Use AWS Console for basic Trusted Advisor checks (available on free tier)

### Identity Center permission errors

**Symptom**: `AccessDenied` when scanning Identity Center resources

**Cause**: Identity Center permissions require both `sso-admin` and `identitystore` actions

**Solutions**:
1. Ensure `stratusscan-optional-permissions.json` is attached
2. Verify you have access to the Identity Center instance
3. Confirm the Identity Center instance exists in your account

### Region-specific errors

**Symptom**: Service not available in selected region

**Solutions**:
1. Some services are only available in specific regions (e.g., Trusted Advisor in us-east-1)
2. Check service availability: https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/
3. Update `config.json` with correct regions for each service

## IAM Policy Maintenance

### When to update policies

Update your IAM policies when:
- New StratusScan scripts are added (check release notes)
- AWS introduces new services or APIs
- Your security requirements change
- Permission errors occur during scanning

### How to update policies

1. Pull latest StratusScan code:
   ```bash
   git pull origin main
   ```

2. Review updated policy files in `policies/` directory

3. Update your custom IAM policies:
   - Go to IAM Policies Console
   - Select your custom policy
   - Click "Edit policy" > "JSON"
   - Replace with updated policy content
   - Click "Review policy" > "Save changes"

4. Re-test permissions:
   ```bash
   python configure.py --perms
   ```

## Support and Resources

- **StratusScan Documentation**: See `CLAUDE.md` in project root
- **AWS IAM Documentation**: https://docs.aws.amazon.com/IAM/latest/UserGuide/
- **AWS IAM Identity Center**: https://docs.aws.amazon.com/singlesignon/latest/userguide/
- **AWS Policy Simulator**: https://policysim.aws.amazon.com/

## License

These IAM policies are part of the StratusScan project and are provided as-is for AWS security auditing and compliance purposes.
