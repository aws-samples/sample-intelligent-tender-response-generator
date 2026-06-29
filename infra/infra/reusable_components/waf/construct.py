from aws_cdk import (
    aws_wafv2 as wafv2
)
from constructs import Construct
from .props import WafPatternProps


class WafPattern(Construct):
    def __init__(self, scope: Construct, construct_id: str, props: WafPatternProps) -> None:
        super().__init__(scope, construct_id)

        self.web_acls = dict()

        for index, (resource_arn, props) in enumerate(props.resource_mappings.items()):
            # If an IP allowlist rule needs to be created, give it the highest priority
            priority_offset = 1 if props.allowlisted_addresses else 0

            acl_rules = [
                self.__configure_acl_rule_property(rule, i + priority_offset)
                for i, rule in enumerate(props.acl_rules)
            ]

            if props.allowlisted_addresses:
                acl_rules.append(self.__configure_allowlist_ipset_rule_property(0, props))

            acl = self.__create_acl(props, acl_rules)
            self.web_acls[resource_arn] = acl.attr_arn

            wafv2.CfnWebACLAssociation(
                self, f"WafAssoc-{index}",
                resource_arn=resource_arn,
                web_acl_arn=acl.attr_arn
            )

            index += 1

    @staticmethod
    def __configure_acl_rule_property(name: str, priority: int):
        return wafv2.CfnWebACL.RuleProperty(
            name=name,
            priority=priority,
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=name.lower(),
                sampled_requests_enabled=True,
            ),
            override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name='AWS',
                    name=name
                )
            ),
        )

    def __configure_allowlist_ipset_rule_property(self, priority, props):
        ipset = wafv2.CfnIPSet(
            self, "AllowIps",
            addresses=props.allowlisted_addresses,
            ip_address_version=props.ip_address_version,
            scope="CLOUDFRONT",
            name=f"{props.acl_name}-allowlist"
        )

        return wafv2.CfnWebACL.RuleProperty(
            name="AllowKnownIps",
            priority=priority,
            action=wafv2.CfnWebACL.RuleActionProperty(allow={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                ip_set_reference_statement=wafv2.CfnWebACL.IPSetReferenceStatementProperty(
                    arn=ipset.attr_arn
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                sampled_requests_enabled=True,
                metric_name="allow-known-ips"
            )
        )

    def __create_acl(self, props, acl_rules):
        # If there aren't allow-listed ips, allow public access to the site
        action = {'allow': {}} if not props.allowlisted_addresses else {'block': {}}

        return wafv2.CfnWebACL(
            self, props.acl_name,
            default_action=wafv2.CfnWebACL.DefaultActionProperty(**action),
            scope=props.scope,
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=f"{props.acl_name}-waf",
                sampled_requests_enabled=True,
            ),
            rules=acl_rules,
            name=props.acl_name
        )
