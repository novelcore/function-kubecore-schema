"""Insights Generation Engine for KubeCore Platform Context Function.

This module implements intelligent insights and recommendations generation
based on platform context and resource relationships.
"""

from __future__ import annotations

import logging
from typing import Any

from .schema_registry import SchemaRegistry


class InsightsEngine:
    """Generates intelligent insights and recommendations for platform resources."""

    def __init__(self, schema_registry: SchemaRegistry):
        """Initialize the insights engine.
        
        Args:
            schema_registry: Registry for schema information
        """
        self.schema_registry = schema_registry
        self.logger = logging.getLogger(__name__)

    def generate_insights(
        self,
        platform_context: dict[str, Any],
        resource_type: str,
    ) -> dict[str, Any]:
        """Generate insights and recommendations for a resource type.
        
        Args:
            platform_context: Platform context data
            resource_type: Type of resource to generate insights for
            
        Returns:
            Dictionary containing insights, recommendations, and suggestions
        """
        insights = {
            "suggestedReferences": [],
            "validationRules": [],
            "recommendations": []
        }
        
        # Generate resource-type-specific insights
        if resource_type == "XApp":
            insights.update(self._generate_app_insights(platform_context))
        elif resource_type == "XKubeSystem":
            insights.update(self._generate_kubesystem_insights(platform_context))
        elif resource_type == "XKubEnv":
            insights.update(self._generate_kubenv_insights(platform_context))
        else:
            insights.update(self._generate_generic_insights(platform_context))
        
        # Add cross-cutting insights
        insights.update(self._generate_cross_cutting_insights(platform_context, resource_type))
        
        self.logger.debug(f"Generated {len(insights['recommendations'])} recommendations for {resource_type}")
        
        return insights

    def _generate_app_insights(self, platform_context: dict[str, Any]) -> dict[str, Any]:
        """Generate XApp-specific insights and recommendations."""
        insights = {
            "suggestedReferences": [],
            "validationRules": [],
            "recommendations": []
        }
        
        # Analyze available schemas for XApp context
        available_schemas = platform_context.get("availableSchemas", {})
        
        # Resource optimization recommendations
        insights["recommendations"].extend([
            {
                "category": "resource-optimization",
                "suggestion": "Consider overriding memory requests for Python applications",
                "impact": "medium",
                "rationale": "Python applications often require more memory than default allocations"
            },
            {
                "category": "resource-optimization", 
                "suggestion": "Enable CPU limits for consistent performance",
                "impact": "low",
                "rationale": "CPU limits prevent resource contention in shared environments"
            }
        ])
        
        # Security recommendations
        insights["recommendations"].extend([
            {
                "category": "security",
                "suggestion": "Enable network policies in production environments",
                "impact": "high",
                "rationale": "Network policies provide micro-segmentation and reduce attack surface"
            },
            {
                "category": "security",
                "suggestion": "Configure security contexts with non-root user",
                "impact": "high",
                "rationale": "Non-root containers reduce privilege escalation risks"
            }
        ])
        
        # Environment-specific recommendations
        if "kubEnv" in available_schemas:
            for instance in available_schemas["kubEnv"].get("instances", []):
                env_type = instance.get("summary", {}).get("environmentType")
                if env_type == "prod":
                    insights["recommendations"].append({
                        "category": "reliability",
                        "suggestion": f"Enable health checks for production environment {instance.get('name')}",
                        "impact": "high",
                        "rationale": "Health checks enable automatic recovery and improve availability"
                    })
                elif env_type == "dev":
                    insights["recommendations"].append({
                        "category": "development",
                        "suggestion": f"Consider enabling debug mode for development environment {instance.get('name')}",
                        "impact": "low",
                        "rationale": "Debug mode provides better troubleshooting capabilities"
                    })
        
        # Validation rules
        insights["validationRules"].extend([
            {
                "rule": "image-tag-required",
                "description": "Container images must specify explicit tags (not 'latest')",
                "severity": "warning"
            },
            {
                "rule": "resource-limits-required",
                "description": "All containers must specify resource limits",
                "severity": "error"
            }
        ])
        
        # Suggested references
        insights["suggestedReferences"].extend([
            {
                "type": "kubEnv",
                "purpose": "deployment-targets",
                "description": "Reference environments where this app can be deployed"
            },
            {
                "type": "githubProject",
                "purpose": "source-code",
                "description": "Reference to the source code repository"
            }
        ])
        
        return insights

    def _generate_kubesystem_insights(self, platform_context: dict[str, Any]) -> dict[str, Any]:
        """Generate XKubeSystem-specific insights and recommendations."""
        insights = {
            "suggestedReferences": [],
            "validationRules": [],
            "recommendations": []
        }
        
        available_schemas = platform_context.get("availableSchemas", {})
        
        # Infrastructure recommendations
        insights["recommendations"].extend([
            {
                "category": "infrastructure",
                "suggestion": "Enable cluster autoscaling for dynamic workloads",
                "impact": "medium",
                "rationale": "Autoscaling optimizes resource utilization and reduces costs"
            },
            {
                "category": "monitoring",
                "suggestion": "Deploy comprehensive monitoring stack",
                "impact": "high",
                "rationale": "Monitoring enables proactive issue detection and resolution"
            }
        ])
        
        # Security recommendations for system components
        insights["recommendations"].extend([
            {
                "category": "security",
                "suggestion": "Enable Pod Security Standards at cluster level",
                "impact": "high",
                "rationale": "Pod Security Standards provide baseline security configurations"
            },
            {
                "category": "security",
                "suggestion": "Configure RBAC with least privilege principle",
                "impact": "high",
                "rationale": "RBAC limits access based on actual requirements"
            }
        ])
        
        # Cluster-specific recommendations
        if "kubeCluster" in available_schemas:
            for instance in available_schemas["kubeCluster"].get("instances", []):
                cluster_version = instance.get("summary", {}).get("version", "")
                if cluster_version and cluster_version < "1.27.0":
                    insights["recommendations"].append({
                        "category": "maintenance",
                        "suggestion": f"Upgrade cluster {instance.get('name')} to supported Kubernetes version",
                        "impact": "high",
                        "rationale": "Older versions may have security vulnerabilities and missing features"
                    })
        
        # Validation rules for system components
        insights["validationRules"].extend([
            {
                "rule": "system-component-health",
                "description": "All system components must pass health checks",
                "severity": "error"
            },
            {
                "rule": "backup-configuration",
                "description": "Backup strategies must be configured for persistent data",
                "severity": "warning"
            }
        ])
        
        # Suggested references
        insights["suggestedReferences"].extend([
            {
                "type": "kubeCluster",
                "purpose": "infrastructure",
                "description": "Reference to the underlying cluster infrastructure"
            },
            {
                "type": "kubEnv",
                "purpose": "hosted-environments",
                "description": "Reference environments hosted by this system"
            }
        ])
        
        return insights

    def _generate_kubenv_insights(self, platform_context: dict[str, Any]) -> dict[str, Any]:
        """Generate XKubEnv-specific insights and recommendations."""
        insights = {
            "suggestedReferences": [],
            "validationRules": [],
            "recommendations": []
        }
        
        available_schemas = platform_context.get("availableSchemas", {})
        requestor = platform_context.get("requestor", {})
        env_name = requestor.get("name", "unknown")
        
        # Environment configuration recommendations
        insights["recommendations"].extend([
            {
                "category": "configuration",
                "suggestion": "Define environment-specific resource quotas",
                "impact": "medium",
                "rationale": "Resource quotas prevent resource exhaustion and ensure fair allocation"
            },
            {
                "category": "configuration",
                "suggestion": "Configure environment-specific network policies",
                "impact": "medium",
                "rationale": "Network policies provide environment isolation and security"
            }
        ])
        
        # Quality gate recommendations
        if "qualityGate" in available_schemas:
            insights["recommendations"].append({
                "category": "quality-assurance",
                "suggestion": "Ensure all required quality gates are configured",
                "impact": "high",
                "rationale": "Quality gates maintain deployment standards and prevent issues"
            })
        else:
            insights["recommendations"].append({
                "category": "quality-assurance",
                "suggestion": "Configure quality gates for deployment validation",
                "impact": "high",
                "rationale": "Quality gates are essential for maintaining deployment quality"
            })
        
        # Environment type specific recommendations
        # Note: This would typically analyze the actual environment type from resolved resources
        insights["recommendations"].extend([
            {
                "category": "monitoring",
                "suggestion": "Enable application performance monitoring (APM)",
                "impact": "medium",
                "rationale": "APM provides visibility into application behavior in the environment"
            },
            {
                "category": "backup",
                "suggestion": "Configure automated backup for persistent volumes",
                "impact": "high",
                "rationale": "Automated backups protect against data loss"
            }
        ])
        
        # Validation rules
        insights["validationRules"].extend([
            {
                "rule": "environment-type-consistency",
                "description": "Environment type must match deployment requirements",
                "severity": "error"
            },
            {
                "rule": "resource-limits-defined",
                "description": "Environment must define resource limits and quotas",
                "severity": "warning"
            }
        ])
        
        # Suggested references
        insights["suggestedReferences"].extend([
            {
                "type": "kubeCluster",
                "purpose": "infrastructure",
                "description": "Reference to the cluster hosting this environment"
            },
            {
                "type": "qualityGate",
                "purpose": "validation",
                "description": "Reference quality gates applied to this environment"
            }
        ])
        
        return insights

    def _generate_generic_insights(self, platform_context: dict[str, Any]) -> dict[str, Any]:
        """Generate generic insights for other resource types."""
        insights = {
            "suggestedReferences": [],
            "validationRules": [],
            "recommendations": []
        }
        
        # Generic best practices
        insights["recommendations"].extend([
            {
                "category": "documentation",
                "suggestion": "Maintain comprehensive resource documentation",
                "impact": "low",
                "rationale": "Documentation improves maintainability and knowledge sharing"
            },
            {
                "category": "monitoring",
                "suggestion": "Implement basic health checks and monitoring",
                "impact": "medium",
                "rationale": "Monitoring enables proactive issue detection"
            }
        ])
        
        return insights

    def _generate_cross_cutting_insights(
        self,
        platform_context: dict[str, Any],
        resource_type: str,
    ) -> dict[str, Any]:
        """Generate cross-cutting insights that apply across resource types."""
        insights = {
            "suggestedReferences": [],
            "validationRules": [],
            "recommendations": []
        }
        
        available_schemas = platform_context.get("availableSchemas", {})
        relationships = platform_context.get("relationships", {})
        
        # Relationship-based insights
        direct_relationships = relationships.get("direct", [])
        
        # If there are missing expected relationships, suggest them
        expected_relationships = self._get_expected_relationships(resource_type)
        for expected_rel in expected_relationships:
            if not any(rel.get("type") == expected_rel for rel in direct_relationships):
                insights["recommendations"].append({
                    "category": "architecture",
                    "suggestion": f"Consider establishing relationship with {expected_rel}",
                    "impact": "medium",
                    "rationale": f"Relationship with {expected_rel} can provide additional context and capabilities"
                })
        
        # Schema availability insights
        if len(available_schemas) == 0:
            insights["recommendations"].append({
                "category": "context",
                "suggestion": "No related schemas available - consider adding references",
                "impact": "low",
                "rationale": "Related schemas provide valuable context for operations"
            })
        
        # Compliance recommendations
        insights["recommendations"].append({
            "category": "compliance",
            "suggestion": "Ensure resource follows organizational naming conventions",
            "impact": "low",
            "rationale": "Consistent naming improves discoverability and management"
        })
        
        return insights

    def _get_expected_relationships(self, resource_type: str) -> list[str]:
        """Get expected relationships for a resource type."""
        relationships_map = {
            "XApp": ["kubEnv", "githubProject"],
            "XKubeSystem": ["kubeCluster", "kubEnv"],
            "XKubEnv": ["kubeCluster", "qualityGate"],
            "XKubeCluster": ["kubeNet", "githubProject"],
            "XGitHubProject": ["githubProvider"],
        }
        
        return relationships_map.get(resource_type, [])

    def analyze_security_implications(
        self,
        platform_context: dict[str, Any],
        resource_type: str,
    ) -> list[dict[str, Any]]:
        """Analyze security implications and generate security-focused insights."""
        security_insights = []
        
        available_schemas = platform_context.get("availableSchemas", {})
        
        # Network security analysis
        if resource_type in ["XApp", "XKubEnv"]:
            security_insights.append({
                "category": "network-security",
                "suggestion": "Implement network segmentation between environments",
                "impact": "high",
                "rationale": "Network segmentation limits blast radius of security incidents"
            })
        
        # Access control analysis
        security_insights.append({
            "category": "access-control",
            "suggestion": "Review and minimize required permissions",
            "impact": "medium",
            "rationale": "Principle of least privilege reduces security risk"
        })
        
        # Data protection analysis
        if "kubEnv" in available_schemas:
            security_insights.append({
                "category": "data-protection",
                "suggestion": "Enable encryption at rest for sensitive data",
                "impact": "high",
                "rationale": "Encryption protects data confidentiality"
            })
        
        return security_insights

    def analyze_performance_implications(
        self,
        platform_context: dict[str, Any],
        resource_type: str,
    ) -> list[dict[str, Any]]:
        """Analyze performance implications and generate performance insights."""
        performance_insights = []
        
        available_schemas = platform_context.get("availableSchemas", {})
        
        # Resource utilization analysis
        if resource_type == "XApp":
            performance_insights.append({
                "category": "resource-utilization",
                "suggestion": "Monitor resource usage patterns to optimize requests/limits",
                "impact": "medium",
                "rationale": "Proper resource allocation improves performance and reduces costs"
            })
        
        # Scaling analysis
        if "kubEnv" in available_schemas:
            performance_insights.append({
                "category": "scaling",
                "suggestion": "Configure horizontal pod autoscaling based on metrics",
                "impact": "medium",
                "rationale": "Autoscaling maintains performance under variable load"
            })
        
        return performance_insights