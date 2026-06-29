from dataclasses import dataclass, field
from typing import List, Dict, Literal


SCOPE = Literal["CLOUDFRONT", "REGIONAL"]
IP_ADDRESS_VERSION = Literal["IPV4", "IPV6"]

@dataclass
class WafPatternProps:
    @dataclass
    class AclProps:
        acl_name: str
        scope: SCOPE

        ip_address_version: IP_ADDRESS_VERSION = "IPV4"
        acl_rules: List[str] = field(default_factory=lambda: [
            'AWSManagedRulesCommonRuleSet',
            'AWSManagedRulesKnownBadInputsRuleSet',
            'AWSManagedRulesSQLiRuleSet',
        ])

        allowlisted_addresses: List[str] = field(default_factory=list)

    resource_mappings: Dict[str, "WafPatternProps.AclProps"]
