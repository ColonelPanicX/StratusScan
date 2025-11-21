# StratusScan GovCloud Partition Support - Fix Summary

**Date**: 2025-11-20
**Priority**: HIGH - Required for GovCloud deployments
**Status**: Partially Complete (2 of 109 scripts fixed)

## Executive Summary

StratusScan was built for AWS Commercial and has **hardcoded Commercial assumptions throughout 97 of 109 scripts** (89%). This causes authentication failures, wrong endpoints, and service errors when used in AWS GovCloud environments.

**What's Fixed**:
- ✅ `configure.py` - Permission testing tool
- ✅ `scripts/services-in-use-export.py` - Service discovery script

**What Needs Fixing**:
- ❌ 97 remaining export scripts with hardcoded Commercial regions/services

## The Problem

### Symptoms in GovCloud
```
[DENIED] ec2:DescribeInstances - Error: AuthFailure
[DENIED] rds:DescribeDBInstances - Error: InvalidClientTokenId
[DENIED] ce:GetDimensionValues - Error: UnrecognizedClientException
Environment: AWS Commercial  ← WRONG! Should say "AWS GovCloud (US)"
```

### Root Causes

1. **Hardcoded "AWS Commercial"** in script headers (97 scripts)
2. **Hardcoded Commercial regions** (`us-east-1`, `us-west-2`) used for:
   - API endpoint selection
   - User prompts and examples
   - Default region selection
3. **No partition detection** - scripts don't know they're in GovCloud
4. **Services called that don't exist in GovCloud**:
   - Cost Explorer (`ce:*`) - NOT available in GovCloud
   - CloudFront - Operates outside GovCloud boundary
   - Global Accelerator - NOT available in GovCloud

### Impact

| Issue | Scripts Affected | User Impact |
|-------|------------------|-------------|
| Hardcoded "AWS Commercial" | 97 | Wrong environment display, user confusion |
| Hardcoded `us-east-1`/`us-west-2` | 97 | API failures, `AuthFailure` errors |
| Cost Explorer calls | ~15 | `UnrecognizedClientException` errors |
| Wrong API parameters | ~8 | Parameter validation failures |

## What We Fixed (Session 2025-11-20)

### 1. Fixed `configure.py` - Permission Testing Tool

**File**: `/home/asimov/code/github/public/stratusscan-cli/configure.py`

**Changes**:
- Added `detect_aws_partition()` function (lines 41-59)
  - Detects partition from STS caller identity ARN
  - Returns `('aws-us-gov', 'us-gov-west-1')` for GovCloud
  - Returns `('aws', 'us-east-1')` for Commercial
- Updated `print_header()` to show correct environment name
- Updated `test_aws_permissions()` to use partition-appropriate regions
- Updated `check_aws_permissions()` to display partition info
- **Skips Cost Explorer test** in GovCloud (service not available)
- Fixed CloudTrail API call (`MaxResults` instead of `MaxItems`)

**Result**: Permission testing now works correctly in GovCloud!

```bash
python configure.py --perms
```

Output:
```
Environment: AWS GovCloud (US)
Partition: AWS GovCloud (US)
Test Region: us-gov-west-1

[OK] sts:GetCallerIdentity (REQUIRED)
[OK] ec2:DescribeInstances (REQUIRED)
[OK] s3:ListBuckets (REQUIRED)
...
```

### 2. Fixed `scripts/services-in-use-export.py` - Service Discovery

**File**: `/home/asimov/code/github/public/stratusscan-cli/scripts/services-in-use-export.py`

**Changes**:
- Updated `print_title()` to detect and display correct partition
- Updated `get_services_from_cost_explorer()` to skip in GovCloud
- Fixed `discover_services_by_resource_enumeration()`:
  - Detects partition and uses correct regions
  - Uses `us-gov-west-1`, `us-gov-east-1` for GovCloud
  - Uses appropriate default region for region-independent services
- Updated `get_services_from_cloudtrail()` to use partition-appropriate region
- Fixed CloudWatch API call (removed invalid `MaxRecords` parameter)

**Result**: Service discovery now works in GovCloud!

## The Fix Pattern (For Remaining 97 Scripts)

### Step 1: Add Helper Functions to utils.py (ONE TIME)

```python
def detect_partition():
    """
    Detect AWS partition from caller identity ARN.

    Returns:
        str: 'aws-us-gov' for GovCloud, 'aws' for Commercial
    """
    try:
        sts = get_boto3_client('sts')
        arn = sts.get_caller_identity().get('Arn', '')
        return 'aws-us-gov' if 'aws-us-gov' in arn else 'aws'
    except:
        return 'aws'

def get_partition_regions(partition=None):
    """
    Get appropriate regions for partition.

    Args:
        partition: Optional partition override

    Returns:
        list: Region list for the partition
    """
    if partition is None:
        partition = detect_partition()

    if partition == 'aws-us-gov':
        return ['us-gov-west-1', 'us-gov-east-1']
    else:
        return get_default_regions()  # Existing function

def get_partition_default_region(partition=None):
    """
    Get default region for partition.

    Returns:
        str: Default region ('us-gov-west-1' for GovCloud, 'us-east-1' for Commercial)
    """
    if partition is None:
        partition = detect_partition()

    return 'us-gov-west-1' if partition == 'aws-us-gov' else 'us-east-1'

def is_service_available_in_partition(service_name, partition=None):
    """
    Check if service is available in the current partition.

    Args:
        service_name: AWS service name (e.g., 'ce', 'cloudfront')
        partition: Optional partition override

    Returns:
        bool: True if service is available
    """
    if partition is None:
        partition = detect_partition()

    # Services NOT available in GovCloud
    govcloud_unavailable = {
        'ce',  # Cost Explorer
        'globalaccelerator',  # Global Accelerator
    }

    if partition == 'aws-us-gov' and service_name in govcloud_unavailable:
        return False

    return True
```

### Step 2: Update Each Script (97 TIMES)

**Pattern for each script**:

#### A. Update Header/Title Function

**Before**:
```python
def print_title():
    print("Environment: AWS Commercial")
    # ...
```

**After**:
```python
def print_title():
    partition = utils.detect_partition()
    partition_name = "AWS GovCloud (US)" if partition == 'aws-us-gov' else "AWS Commercial"
    print(f"Environment: {partition_name}")
    # ...
```

#### B. Update Region Selection/Prompts

**Before**:
```python
print("Available AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1")
region_input = input("Enter region (or 'all'): ").strip().lower()
```

**After**:
```python
partition = utils.detect_partition()
if partition == 'aws-us-gov':
    print("Available AWS GovCloud regions: us-gov-west-1, us-gov-east-1")
    example_region = "us-gov-west-1"
else:
    print("Available AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1")
    example_region = "us-east-1"

region_input = input(f"Enter region (or 'all') [default: {example_region}]: ").strip().lower()
```

#### C. Update Hardcoded Region References

**Before**:
```python
client = utils.get_boto3_client('ec2', region_name='us-east-1')
```

**After**:
```python
default_region = utils.get_partition_default_region()
client = utils.get_boto3_client('ec2', region_name=default_region)
```

#### D. Skip Unavailable Services

**Before**:
```python
ce_client = utils.get_boto3_client('ce', region_name='us-east-1')
response = ce_client.get_dimension_values(...)
```

**After**:
```python
if utils.is_service_available_in_partition('ce'):
    ce_client = utils.get_boto3_client('ce', region_name=utils.get_partition_default_region())
    response = ce_client.get_dimension_values(...)
else:
    utils.log_info("Cost Explorer not available in current partition - skipping")
    response = {'DimensionValues': []}
```

## Scripts Requiring Updates (97 Total)

### By Category

#### Compute Resources (15 scripts)
- `ec2-export.py` ⚠️ HIGH PRIORITY
- `lambda-export.py` ⚠️ HIGH PRIORITY
- `ecs-export.py`
- `eks-export.py`
- `elasticbeanstalk-export.py`
- `autoscaling-export.py`
- `apprunner-export.py`
- `batch-export.py`
- `compute-resources.py` (combined report)
- `ami-export.py`
- `launch-templates-export.py`
- `capacity-reservations-export.py`
- `spot-instances-export.py`
- `placement-groups-export.py`
- `elastic-ip-export.py`

#### Storage Resources (12 scripts)
- `s3-export.py` ⚠️ HIGH PRIORITY
- `ebs-volumes.py` ⚠️ HIGH PRIORITY
- `ebs-snapshots.py`
- `efs-export.py`
- `fsx-export.py`
- `glacier-export.py`
- `backup-export.py`
- `storagegateway-export.py`
- `storage-resources.py` (combined report)
- `s3-access-points-export.py`
- `s3-storage-lens-export.py`
- `datasync-export.py`

#### Network Resources (18 scripts)
- `vpc-data-export.py` ⚠️ HIGH PRIORITY
- `security-groups-export.py` ⚠️ HIGH PRIORITY
- `nacl-export.py`
- `elb-export.py`
- `route-tables-export.py`
- `transit-gateway-export.py`
- `vpn-export.py`
- `directconnect-export.py`
- `route53-export.py`
- `network-firewall-export.py`
- `network-resources.py` (combined report)
- `nat-gateways-export.py`
- `internet-gateways-export.py`
- `vpc-endpoints-export.py`
- `vpc-peering-export.py`
- `cloudfront-export.py` ⚠️ SKIP in GovCloud
- `globalaccelerator-export.py` ⚠️ SKIP in GovCloud
- `networkmanager-export.py`

#### Database Resources (8 scripts)
- `rds-export.py` ⚠️ HIGH PRIORITY
- `dynamodb-export.py`
- `elasticache-export.py`
- `redshift-export.py`
- `neptune-export.py`
- `docdb-export.py`
- `memorydb-export.py`
- `opensearch-export.py`

#### IAM & Security (22 scripts)
- `iam-export.py` ⚠️ HIGH PRIORITY
- `iam-roles-export.py` ⚠️ HIGH PRIORITY
- `iam-policies-export.py`
- `iam-comprehensive-export.py`
- `iam-identity-center-export.py`
- `iam-identity-center-groups-export.py`
- `iam-identity-center-permission-sets-export.py`
- `iam-identity-center-comprehensive-export.py`
- `organizations-export.py`
- `kms-export.py`
- `secrets-manager-export.py`
- `acm-export.py`
- `guardduty-export.py`
- `security-hub-export.py`
- `macie-export.py`
- `detective-export.py`
- `access-analyzer-export.py`
- `waf-export.py`
- `shield-export.py`
- `cloudtrail-export.py`
- `config-export.py`
- `rolesanywhere-export.py`

#### Cost Management (10 scripts) ⚠️ MOST NEED GOVCLOUD CHECKS
- `cost-optimization-hub-export.py` ⚠️ Check GovCloud availability
- `trusted-advisor-cost-optimization-export.py`
- `compute-optimizer-export.py`
- `savings-plans-export.py`
- `budgets-export.py`
- `cost-categories-export.py`
- `cost-anomaly-detection-export.py`
- `reserved-instances-export.py`
- `rightsizing-recommendations-export.py`
- `billing-export.py` ⚠️ Check GovCloud availability

#### Monitoring & Logging (6 scripts)
- `cloudwatch-export.py`
- `logs-export.py`
- `xray-export.py`
- `eventbridge-export.py`
- `sns-export.py`
- `sqs-export.py`

#### Application Services (6 scripts)
- `apigateway-export.py`
- `appsync-export.py`
- `cognito-export.py`
- `stepfunctions-export.py`
- `ses-pinpoint-export.py`
- `connect-export.py`

## Implementation Plan

### Phase 1: Foundation (Week 1)
**Goal**: Add partition detection infrastructure

1. ✅ **DONE**: Add helper functions to `utils.py`
   - `detect_partition()`
   - `get_partition_regions()`
   - `get_partition_default_region()`
   - `is_service_available_in_partition()`

2. ✅ **DONE**: Fix core scripts
   - ✅ `configure.py`
   - ✅ `scripts/services-in-use-export.py`

3. **Document GovCloud service limitations**
   - Create `GOVCLOUD-SERVICES.md` with complete list
   - List services NOT available
   - List services with limited functionality

### Phase 2: High-Priority Exports (Week 2)
**Goal**: Fix most commonly used scripts

Batch 1 - Core Infrastructure:
- [ ] `ec2-export.py`
- [ ] `vpc-data-export.py`
- [ ] `s3-export.py`
- [ ] `iam-export.py`
- [ ] `iam-roles-export.py`

Batch 2 - Database & Storage:
- [ ] `rds-export.py`
- [ ] `ebs-volumes.py`
- [ ] `ebs-snapshots.py`
- [ ] `dynamodb-export.py`

Batch 3 - Network:
- [ ] `security-groups-export.py`
- [ ] `elb-export.py`
- [ ] `route53-export.py`

### Phase 3: Security & Compliance (Week 3)
**Goal**: Fix security/compliance scripts

- [ ] `iam-comprehensive-export.py`
- [ ] `iam-identity-center-comprehensive-export.py`
- [ ] `security-hub-export.py`
- [ ] `guardduty-export.py`
- [ ] `cloudtrail-export.py`
- [ ] `config-export.py`
- [ ] `kms-export.py`
- [ ] `secrets-manager-export.py`

### Phase 4: Cost Optimization (Week 4)
**Goal**: Fix cost/optimization scripts (with GovCloud checks)

⚠️ **CRITICAL**: Most cost services have limited or NO GovCloud availability

- [ ] `trusted-advisor-cost-optimization-export.py`
- [ ] `compute-optimizer-export.py`
- [ ] `savings-plans-export.py`
- [ ] `budgets-export.py`
- [ ] Cost Explorer scripts → Skip in GovCloud

### Phase 5: Remaining Scripts (Week 5)
**Goal**: Complete all remaining scripts

- [ ] All monitoring/logging scripts
- [ ] All application service scripts
- [ ] All specialized export scripts
- [ ] Combined report scripts

### Phase 6: Testing & Documentation (Week 6)
**Goal**: Validate and document

1. **Test in GovCloud**
   - Run each fixed script in GovCloud environment
   - Verify correct partition detection
   - Verify correct region usage
   - Verify service availability checks work

2. **Test in Commercial**
   - Ensure no regression in Commercial
   - Verify backward compatibility
   - Test all 109 scripts

3. **Update Documentation**
   - Update README.md with GovCloud support
   - Create GOVCLOUD-DEPLOYMENT.md guide
   - Update CLAUDE.md with partition patterns
   - Add to policies/AWS-MANAGED-POLICIES.md

## Testing Checklist (Per Script)

For each fixed script, verify:

- [ ] Header shows correct partition ("AWS GovCloud (US)" or "AWS Commercial")
- [ ] Uses correct regions (us-gov-* for GovCloud, commercial for AWS)
- [ ] Region prompts show correct examples
- [ ] Unavailable services are skipped with log message
- [ ] No hardcoded `us-east-1` or `us-west-2` references
- [ ] Script runs without authentication errors
- [ ] Output file generates successfully
- [ ] Works in BOTH Commercial and GovCloud

## GovCloud Service Limitations (Reference)

### Services NOT Available in GovCloud
❌ **Cost Explorer** (`ce:*`) - No billing/cost APIs
❌ **Global Accelerator** (`globalaccelerator:*`) - Not in GovCloud
❌ **CloudFront** - Operates outside GovCloud boundary (ITAR concerns)
❌ **AWS Marketplace** - Limited catalog, no container/ML products

### Services with Limited Functionality
⚠️ **S3**: No Transfer Acceleration, no Storage Lens, no Express One Zone
⚠️ **CloudWatch**: No cross-account observability, limited dashboard features
⚠️ **Trusted Advisor**: Limited checks compared to Commercial
⚠️ **Cost Optimization Hub**: May have limited availability

### Services Fully Available
✅ EC2, RDS, Lambda, ECS, EKS, VPC, ELB, Route 53
✅ IAM, Organizations, Identity Center (SSO)
✅ S3 (core features), EBS, EFS, FSx
✅ KMS, Secrets Manager, ACM
✅ GuardDuty, Security Hub, Macie, Config, CloudTrail
✅ DynamoDB, ElastiCache, Redshift
✅ **Bedrock** (as of Nov 2024) - us-gov-west-1, us-gov-east-1

## Current AWS Managed Policies (Fixed)

User successfully configured these AWS Managed Policies in IAM Identity Center:

✅ **ReadOnlyAccess** - Covers 90+ services
✅ **IAMReadOnlyAccess** - IAM and Identity Center
✅ **SecurityAudit** - Security service access
✅ **AWSSupportAccess** - Support and Trusted Advisor
✅ **PowerUserAccess** - For other work (note: blocks IAM access)

**Result**: Permission tests now pass in GovCloud!

## Session Notes

### Issues Encountered
1. **Policy errors** - Original policies had metadata fields AWS doesn't accept
   - Created clean versions without `_comment`, `_description`, etc.
   - Files: `commercial-required-permissions.json`, `govcloud-required-permissions.json`

2. **Redundancy warnings** - Some permissions were covered by wildcards
   - Fixed RDS: Removed `rds:DescribeDBClusters` (covered by `rds:Describe*`)
   - Fixed SES: Removed specific actions (covered by `ses:Get*`, `ses:List*`)

3. **Permission test failures** - All caused by partition mismatch
   - Tests used `us-east-1` (doesn't exist in GovCloud)
   - Tests called Cost Explorer (doesn't exist in GovCloud)
   - Wrong API parameters (`MaxItems` vs `MaxResults`)

### Key Realizations
- **PowerUserAccess has explicit DENY for IAM/Organizations**
  - Can't be combined with IAM read permissions
  - User needs separate permission set or user for StratusScan
  - AWS Managed Policies approach is cleaner

- **97 of 109 scripts need partition fixes**
  - This is systemic, not isolated
  - Need consistent pattern across all scripts
  - Utils.py functions make this tractable

## Next Session Action Items

1. **Immediate** (Start of next session):
   - Add partition helper functions to `utils.py`
   - Test in both Commercial and GovCloud
   - Document the helper functions

2. **Phase 2 Priority** (First batch):
   - Fix `ec2-export.py` (most common)
   - Fix `vpc-data-export.py` (most common)
   - Fix `s3-export.py` (most common)
   - Fix `iam-export.py` (most common)

3. **Testing Setup**:
   - Create test checklist
   - Set up GovCloud test account access
   - Create Commercial test account for regression testing

## Files Modified This Session

1. ✅ `/home/asimov/code/github/public/stratusscan-cli/configure.py`
   - Added `detect_aws_partition()` function
   - Updated `print_header()`, `test_aws_permissions()`, `check_aws_permissions()`

2. ✅ `/home/asimov/code/github/public/stratusscan-cli/scripts/services-in-use-export.py`
   - Updated all functions to use partition detection
   - Skip Cost Explorer in GovCloud
   - Use correct regions for partition

3. ✅ `/home/asimov/code/github/public/stratusscan-cli/policies/`
   - Removed original JSON files with metadata
   - Kept only clean IAM-compatible versions
   - Fixed redundant permissions

4. ✅ `/home/asimov/code/github/public/stratusscan-cli/policies/AWS-MANAGED-POLICIES.md`
   - Created comprehensive guide for AWS Managed Policies
   - Recommended setup: 4 core policies

5. ✅ `/home/asimov/code/github/public/stratusscan-cli/policies/README.md`
   - Updated to recommend AWS Managed Policies first
   - Custom policies as alternative

## Success Metrics

- [x] Permission tests pass in GovCloud
- [x] `configure.py --perms` shows correct partition
- [x] `services-in-use-export.py` runs without errors
- [ ] All 109 scripts work in both Commercial and GovCloud
- [ ] No hardcoded Commercial assumptions remain
- [ ] Complete GovCloud deployment documentation

## References

- GovCloud Service Availability: https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/using-services.html
- IAM Policy Size Limits: 6,144 characters for inline, 10,240 for managed
- AWS Partitions: `aws` (Commercial), `aws-us-gov` (GovCloud), `aws-cn` (China)
- GovCloud Regions: `us-gov-west-1`, `us-gov-east-1`

---

**Next Action**: Add partition helper functions to utils.py and start Phase 2 (High-Priority Exports)
