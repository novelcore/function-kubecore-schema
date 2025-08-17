"""Platform relationships for KubeCore resources.

This module defines the exact platform hierarchy and resource relationships
according to the KubeCore Platform Context Function specification.
"""

# Platform Hierarchy - defines which schemas are accessible to each resource type
PLATFORM_HIERARCHY: dict[str, list[str]] = {
    "XApp": [
        "XKubEnv",
        "XQualityGate",
        "XGitHubProject",
        "XGitHubApp",
        "XKubeCluster",
        "XKubeNet",
        "XKubeSystem",
    ],
    "XKubeSystem": ["XKubeCluster", "XKubEnv", "XGitHubProject", "XKubeNet", "XGitHubProvider"],
    "XKubEnv": ["XKubeCluster", "XQualityGate", "XGitHubProject", "XKubeNet"],
    "XKubeCluster": ["XGitHubProject", "XKubeNet", "XGitHubProvider"],
    "XGitHubProject": ["XGitHubProvider"],
    "XGitHubApp": ["XGitHubProject", "XGitHubProvider"],
    "XQualityGate": [
        # Quality gates are referenced by other resources, not the other way around
    ],
    "XKubeNet": [
        # Network resources are used by clusters, not the other way around
    ],
    "XGitHubProvider": [
        # Top-level provider resource
    ],
}

# Resource Relationships - defines ownership and usage patterns
RESOURCE_RELATIONSHIPS: dict[str, dict[str, list[str]]] = {
    "XGitHubProvider": {"owns": ["XGitHubProject"]},
    "XGitHubProject": {
        "belongsTo": ["XGitHubProvider"],
        "owns": ["XKubeCluster", "XGitHubApp"],
    },
    "XKubeNet": {"supports": ["XKubeCluster"]},
    "XKubeCluster": {
        "belongsTo": ["XGitHubProject"],
        "uses": ["XKubeNet"],
        "hosts": ["XKubeSystem", "XKubEnv"],
    },
    "XKubeSystem": {"runsOn": ["XKubeCluster"]},
    "XKubEnv": {"runsOn": ["XKubeCluster"], "uses": ["XQualityGate"]},
    "XQualityGate": {"appliesTo": ["XKubEnv", "XApp"]},
    "XGitHubApp": {"belongsTo": ["XGitHubProject"], "sources": ["XApp"]},
    "XApp": {
        "belongsTo": ["XGitHubProject"],
        "sourcedBy": ["XGitHubApp"],
        "deploysTo": ["XKubEnv"],
    },
}

# Cardinality rules for relationships
RELATIONSHIP_CARDINALITY: dict[str, dict[str, str]] = {
    "XGitHubProvider": {"XGitHubProject": "1:N"},
    "XGitHubProject": {"XKubeCluster": "1:1", "XGitHubApp": "1:N"},
    "XKubeNet": {"XKubeCluster": "1:N"},
    "XKubeCluster": {"XKubeSystem": "1:1", "XKubEnv": "1:N"},
    "XGitHubApp": {"XApp": "1:1"},
    "XApp": {"XKubEnv": "N:N"},
    "XQualityGate": {"XKubEnv": "N:N", "XApp": "N:N"},
}

# Resource descriptions for documentation and insights
RESOURCE_DESCRIPTIONS: dict[str, str] = {
    "XGitHubProvider": "Contains credentials and semantics for GitHub organization",
    "XGitHubProject": "Software product with GitOps repository, teams, and permissions",
    "XKubeNet": "Network infrastructure (VPC, DNS) shared across multiple projects",
    "XKubeCluster": "Kubernetes cluster (1:1 with GitHubProject, references KubeNet)",
    "XKubeSystem": "Platform tools runtime (ArgoCD, Crossplane, etc.) on KubeCluster",
    "XKubEnv": "Deployment environment with app node groups on KubeCluster",
    "XQualityGate": "Reusable validation workflows applicable to environments/apps",
    "XGitHubApp": "Source control for software component (1:1 with App)",
    "XApp": "Kubernetes application deployment semantic (references multiple KubEnvs)",
}


def get_accessible_schemas(resource_type: str) -> list[str]:
    """Get schemas accessible to a resource type."""
    return PLATFORM_HIERARCHY.get(resource_type, [])


def get_relationship_cardinality(from_type: str, to_type: str) -> str:
    """Get the cardinality of a relationship between two resource types."""
    return RELATIONSHIP_CARDINALITY.get(from_type, {}).get(to_type, "unknown")


def get_resource_description(resource_type: str) -> str:
    """Get the description of a resource type."""
    return RESOURCE_DESCRIPTIONS.get(resource_type, "No description available")
