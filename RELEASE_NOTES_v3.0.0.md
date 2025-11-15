# StratusScan-CLI v3.0.0 Release Notes

**Release Date:** November 14, 2025
**Release Type:** Major Release (v2.2.0 → v3.0.0)
**Git Tag:** `v3.0.0`
**Commit:** `c9b5438`

---

## 🌟 Headline Features

### 1. Multi-Partition Support - MAJOR FEATURE ✨

StratusScan-CLI now **seamlessly supports both AWS Commercial and AWS GovCloud environments** with automatic partition detection and **zero configuration required**.

**How it works:**
- Automatically detects your partition from AWS credentials (STS ARN)
- Commercial credentials → uses `aws` partition and commercial regions
- GovCloud credentials → uses `aws-us-gov` partition and GovCloud regions
- No config files to edit, no flags to set - it just works!

**What you get:**
- ✅ Partition-aware region selection
- ✅ Correct ARN formatting (`arn:aws:...` vs `arn:aws-us-gov:...`)
- ✅ Service availability warnings (e.g., TrustedAdvisor not available in GovCloud)
- ✅ User-friendly partition logging
- ✅ Future-ready for `aws-cn` (China) partition support

**Example:**
```bash
# AWS Commercial
$ python stratusscan.py
# → Automatically scans: us-east-1, us-west-2, us-west-1, eu-west-1
# → ARNs: arn:aws:service:region:account:resource

# AWS GovCloud
$ python stratusscan.py
# → Automatically scans: us-gov-west-1, us-gov-east-1
# → ARNs: arn:aws-us-gov:service:region:account:resource
```

### 2. Comprehensive Service Coverage - 109 Scripts 📦

Reached **~95% coverage of useful AWS services** with the addition of 8 final high-value services:

**New Services:**
1. **Service Discovery / Cloud Map** - Service registry for microservices
2. **X-Ray** - Distributed tracing and performance analysis
3. **SES & Pinpoint** - Email service and marketing automation
4. **Network Manager** - SD-WAN and global network topology
5. **Glacier Vaults** - Archive storage management (separate from S3 Glacier)
6. **AWS Connect** - Contact center platform
7. **AWS Marketplace** - Subscription and procurement management
8. **Verified Permissions** - Cedar-based authorization engine

---

## 📊 Statistics

| Metric | Value |
|--------|-------|
| **Total Scripts** | 109 (105 individual + 4 combined reports) |
| **Service Coverage** | ~95% of useful AWS services |
| **Partitions Supported** | AWS Commercial, AWS GovCloud |
| **Lines Added** | +400 lines (partition detection) |
| **New Functions** | 6 new partition-aware utility functions |

---

## 🔧 Technical Changes

### utils.py (v1.1.0 → v3.0.0)

**New Functions:**
- `detect_partition(region_name=None)` - Auto-detect AWS partition
- `get_partition_regions(partition='aws')` - Get regions for specific partition
- `is_service_available_in_partition(service, partition='aws')` - Check service availability
- `log_partition_info(partition, regions)` - Log partition info for users

**Enhanced Functions:**
- `get_default_regions(partition=None)` - Now partition-aware with auto-detection
- `prompt_region_selection()` - Added `service_name` and `default_to_all` parameters, partition-aware prompts
- `build_arn()` - Already partition-aware, now fully integrated with detection

**Service Availability Tracking:**
- GovCloud unavailable services: TrustedAdvisor, AppStream, Chime, GameLift, RoboMaker
- GovCloud limited services: Marketplace (limited API), Organizations (different features)

### stratusscan.py (v2.2.0 → v3.0.0)

**Menu Updates:**
- Updated header to display detected partition ("AWS Commercial" or "AWS GovCloud (US)")
- Multi-partition support messaging in header
- Menu descriptions updated for partition awareness
- Version bumped to v3.0.0

**Integration:**
- 8 new scripts integrated into menu system
- Service Discovery → Integration & Messaging (9.4)
- X-Ray → Monitoring & Operations (10.3)
- SES & Pinpoint → Integration & Messaging (9.5)
- Network Manager → Network Resources (4.13)
- Glacier Vaults → Storage Resources (3.11)
- AWS Connect → Application Services (13.5)
- AWS Marketplace → Management & Governance (17.5)
- Verified Permissions → Advanced Security & Identity (14.5)

---

## 📦 New Scripts

### servicediscovery-export.py
**Purpose:** Export AWS Service Discovery (Cloud Map) resources
**Worksheets:** 6 sheets (Summary, Namespaces, DNS Namespaces, HTTP Namespaces, Services, Instances)
**Features:**
- DNS and HTTP namespace support
- Service registration with health checks
- Instance discovery and attributes
- VPC and Route 53 integration tracking

### xray-export.py
**Purpose:** Export AWS X-Ray distributed tracing configuration
**Worksheets:** 6 sheets (Summary, Encryption Config, Sampling Rules, Custom Rules, Groups, Insights)
**Features:**
- Encryption configuration
- Sampling rules (default and custom)
- Group definitions
- Insights enablement tracking

### ses-pinpoint-export.py
**Purpose:** Export SES email and Pinpoint marketing resources
**Worksheets:** 10 sheets (Summary, SES Account, Identities, Config Sets, Templates, Pinpoint Apps, Campaigns, Segments, etc.)
**Features:**
- SES identity verification (domains and emails)
- DKIM configuration tracking
- Email sending quotas
- Pinpoint application campaigns
- Customer segmentation analysis

### network-manager-export.py
**Purpose:** Export AWS Network Manager SD-WAN topology
**Worksheets:** 10 sheets (Summary, Global Networks, Sites, Links, Devices, Connections, TGW Registrations, etc.)
**Features:**
- Global network topology
- Site and link management
- Device configurations
- Transit Gateway Network Manager integration
- Customer Gateway associations

### glacier-export.py
**Purpose:** Export AWS Glacier vault resources
**Worksheets:** 6 sheets (Summary, All Vaults, Vaults with Policies, Locks, Notifications, Tags)
**Features:**
- Vault inventory and metadata
- Access policy analysis
- Vault lock policy compliance
- SNS notification configurations
- Archive count and size tracking

### connect-export.py
**Purpose:** Export AWS Connect contact center resources
**Worksheets:** 9 sheets (Summary, Instances, Hours of Operation, Queues, Contact Flows, Phone Numbers, Users, etc.)
**Features:**
- Contact center instances
- Queue configurations
- IVR/contact flow designs (metadata)
- Phone number inventory
- User and permissions tracking

### marketplace-export.py
**Purpose:** Export AWS Marketplace subscription configuration
**Worksheets:** 3 sheets (Summary, Configuration, Procurement Policies)
**Features:**
- Private Marketplace settings
- Procurement policy tracking (limited API access)
- Guidance for console-based management

**Note:** AWS Marketplace has limited API access for buyer accounts. This script exports available configuration; full subscription details require AWS Console access.

### verifiedpermissions-export.py
**Purpose:** Export AWS Verified Permissions Cedar policies
**Worksheets:** 7 sheets (Summary, Policy Stores, Policies, Static, Template-Linked, Templates, Identity Sources)
**Features:**
- Policy store configurations
- Static and template-linked policies
- Policy template management
- Identity source integration (Cognito User Pools, OIDC)
- Validation mode tracking

---

## 🎯 Phase Completion

### Phase 4 Tier 5: Final 8 Useful Services ✅ COMPLETE
All 8 remaining high-value services implemented:
- ✅ Service Discovery / Cloud Map
- ✅ X-Ray
- ✅ SES & Pinpoint
- ✅ Network Manager
- ✅ Glacier Vaults
- ✅ AWS Connect
- ✅ AWS Marketplace
- ✅ Verified Permissions

### Phase 4A: Multi-Partition Support ✅ COMPLETE
Comprehensive partition detection and compatibility:
- ✅ Automatic partition detection
- ✅ GovCloud service availability tracking
- ✅ Partition-aware region selection
- ✅ Partition-aware ARN building
- ✅ User-facing partition logging
- ✅ Zero-configuration operation

---

## 🔗 Commits Since v2.2.0

| Commit | Date | Description |
|--------|------|-------------|
| `8f7b619` | Nov 14 | Add final useful services batch 1: Service Discovery & X-Ray |
| `295f2e3` | Nov 14 | Add final useful services batch 2: SES/Pinpoint & Network Manager |
| `1d6930e` | Nov 14 | Add final useful services batch 3: Glacier Vaults & AWS Connect |
| `863bc8a` | Nov 14 | Add final useful services batch 4: Marketplace & Verified Permissions |
| `adf03f1` | Nov 14 | Add Phase 4A: Multi-Partition Support for AWS GovCloud |
| `c9b5438` | Nov 14 | Release v3.0.0: Multi-Partition Support & Comprehensive Service Coverage |

---

## ⚠️ Breaking Changes

**None** - This release is 100% backward compatible.

All existing scripts work unchanged in AWS Commercial environments. GovCloud support is purely additive and does not affect existing Commercial deployments.

---

## 📝 Usage Examples

### AWS Commercial (Automatic Detection)
```bash
# Configure AWS CLI with commercial credentials
aws configure

# Run any script - automatically uses commercial partition
python scripts/ec2-export.py
# Output:
# AWS PARTITION: AWS Commercial (aws)
# REGIONS: us-east-1, us-west-2, us-west-1, eu-west-1
# Scanning EC2 instances...
```

### AWS GovCloud (Automatic Detection)
```bash
# Configure AWS CLI with GovCloud credentials
aws configure

# Run any script - automatically uses GovCloud partition
python scripts/ec2-export.py
# Output:
# AWS PARTITION: AWS GovCloud (aws-us-gov)
# REGIONS: us-gov-west-1, us-gov-east-1
# NOTE: GovCloud has different service availability
# Scanning EC2 instances...
```

### Service Availability Checking
```python
import utils

# Check if a service is available in current partition
if utils.is_service_available_in_partition('trustedadvisor'):
    # Run Trusted Advisor export
    pass
else:
    print("Trusted Advisor not available in this partition")
```

---

## 🚀 Migration Guide

**For existing users:** No migration needed! Just pull the latest code and continue using StratusScan as before.

**For GovCloud users:** Simply configure your AWS CLI with GovCloud credentials and run StratusScan - partition detection is automatic.

**For developers:** If you've created custom scripts, you can now use:
- `utils.detect_partition()` for partition detection
- `utils.get_partition_regions()` for partition-specific region lists
- `utils.is_service_available_in_partition()` for service availability checks
- `utils.log_partition_info()` for user-facing partition messaging

---

## 🎉 What's Next?

With comprehensive service coverage and multi-partition support complete, future development will focus on:

### Phase 4B: Performance Optimization
- Concurrent API calls for multi-region exports
- Caching for frequently accessed data
- Optimized pagination strategies

### Phase 4C: Enhanced Reporting
- Cross-account aggregation reports
- Trend analysis (compare exports over time)
- Executive summary dashboards
- Security posture scoring

### Phase 4D: Advanced Features
- Tag-based filtering across all exports
- Resource dependency mapping
- Cost attribution by tag/resource

---

## 🙏 Acknowledgments

This release represents a major milestone for StratusScan-CLI. The combination of comprehensive AWS service coverage with seamless multi-partition support creates a truly enterprise-grade AWS auditing tool.

Thank you to all users and contributors who have provided feedback and suggestions throughout the development process.

---

## 📞 Support & Feedback

- **Issues:** https://github.com/ColonelPanicX/StratusScan-CLI/issues
- **Documentation:** See README.md and CLAUDE.md
- **Questions:** Open a GitHub discussion or issue

---

**🤖 Generated with Claude Code (https://claude.com/claude-code)**

**Co-Authored-By:** Claude <noreply@anthropic.com>
